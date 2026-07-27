import os
import re
from playwright.sync_api import sync_playwright


class LocalPlaywrightMcpServer:
    """A localized implementation of the Playwright MCP Server architecture.
    Forces the AI to interact via standardized Playwright tool commands."""

    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.p_instance = None
        self.browser = None
        self.context = None
        self.page = None

    def execute_mcp_tool(self, tool_name, arguments):
        """Standardized MCP Tool execution router."""
        if tool_name == "playwright_launch":
            return self._tool_launch(arguments.get("url"))
        elif tool_name == "playwright_click":
            return self._tool_click(arguments.get("selector"))
        elif tool_name == "playwright_fill":
            return self._tool_fill(arguments.get("selector"), arguments.get("text"))
        elif tool_name == "playwright_get_selectors":
            return self._tool_get_selectors()
        return {"status": "ERROR", "message": f"Unknown MCP tool: {tool_name}"}

    def _tool_launch(self, url):
        if not self.p_instance:
            self.p_instance = sync_playwright().start()
            self.browser = self.p_instance.chromium.launch(headless=False, slow_mo=500)
            self.context = self.browser.new_context()
            self.page = self.context.new_page()
        self.page.goto(url)
        return {"status": "SUCCESS", "current_url": self.page.url}

    def _tool_click(self, selector):
        if not self.page: return {"status": "ERROR", "message": "No active browser context."}
        try:
            self.page.locator(selector).wait_for(state="visible", timeout=3000)
            self.page.locator(selector).click()
            return {"status": "SUCCESS", "message": f"Clicked element: {selector}"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def _tool_fill(self, selector, text):
        if not self.page: return {"status": "ERROR", "message": "No active browser context."}
        try:
            self.page.locator(selector).wait_for(state="visible", timeout=3000)
            self.page.locator(selector).fill(str(text))
            return {"status": "SUCCESS", "message": f"Filled element: {selector}"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    def _tool_get_selectors(self):
        """Natively scans the live viewport page state and returns interactive Playwright-ready elements."""
        if not self.page: return {"status": "ERROR", "message": "No active browser context."}
        elements = self.page.evaluate("""
            () => {
                let items = [];
                document.querySelectorAll('input, button, a, [data-test]').forEach(el => {
                    items.push({
                        tagName: el.tagName.toLowerCase(),
                        id: el.id ? '#' + el.id : '',
                        testId: el.getAttribute('data-test') ? '[data-test="' + el.getAttribute('data-test') + '"]' : '',
                        placeholder: el.getAttribute('placeholder') || '',
                        text: el.innerText || el.value || ''
                    });
                });
                return items;
            }
        """)
        return {"status": "SUCCESS", "elements": elements[:15]}

    def tool_edit_page_object(self, filename, target_var, new_selector):
        """Tool: Writes updates cleanly into local POM python files under src/pages."""
        file_path = os.path.join(self.base_dir, "src", "pages", filename)
        if not os.path.exists(file_path):
            return {"status": "ERROR", "message": f"POM file {filename} not found at {file_path}."}

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        pattern = rf"(self\.{target_var}\s*=\s*['\"])(.*?)(['\"])"
        if not re.search(pattern, content):
            return {"status": "ERROR", "message": f"Variable reference '{target_var}' missing in file."}

        updated_content = re.sub(pattern, rf"\1{new_selector}\3", content)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated_content)
        return {"status": "SUCCESS", "message": f"Successfully healed {target_var} in {filename}."}

    def tool_create_new_page_object(self, filename, class_name, selectors_dict, methods_list):
        """Tool: Dynamically generates a brand new Python Page Object class file from scratch under src/pages."""
        file_path = os.path.join(self.base_dir, "src", "pages", filename)
        if os.path.exists(file_path):
            return {"status": "ERROR", "message": f"File {filename} already exists. Use edit tools instead."}

        code_lines = [
            "from playwright.sync_api import Page",
            "from src.pages.base_page import BasePage\n",
            f"class {class_name}(BasePage):",
            "    def __init__(self, page: Page):",
            "        super().__init__(page)"
        ]

        for key, val in selectors_dict.items():
            code_lines.append(f"        self.{key} = '{val}'")

        for m in methods_list:
            param_str = f", {m['param']}" if m.get('param') else ""
            code_lines.extend([f"\n    def {m['name']}(self{param_str}):"])
            if m['action'] == "fill":
                code_lines.append(f"        self.page.locator(self.{m['selector_var']}).fill({m['param']})")
            elif m['action'] == "click":
                code_lines.append(f"        self.page.locator(self.{m['selector_var']}).click()")

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(code_lines))
        return {"status": "SUCCESS", "message": f"Created new Page Object {class_name} at src/pages/{filename}"}

    def shutdown(self):
        if self.browser: self.browser.close()
        if self.p_instance: self.p_instance.stop()
