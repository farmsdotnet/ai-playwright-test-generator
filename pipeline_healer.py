import os
import sys
import json
import subprocess
import requests

BASE_DIR = r"C:\Dev Projects 2026 Local\GIT\ai_qa_framework"
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from manifest_generator import generate_pom_manifest
from mcp_engine.browser_agent import LocalPlaywrightMcpServer

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:7b"


class SelfHealingCompiler:
    def __init__(self):
        # Initialize the Stateful Local Playwright MCP Server instance
        self.mcp = LocalPlaywrightMcpServer(BASE_DIR)

    def execute_and_heal_plan(self, issue_id):
        issue_clean = issue_id.upper().strip().lower().replace('-', '_')
        plan_path = os.path.join(BASE_DIR, "tests", "pending_review", f"plan_{issue_clean}.json")
        trial_script_path = os.path.join(BASE_DIR, "tests", "pending_review", f"test_{issue_clean}.py")

        if not os.path.exists(plan_path):
            print(f"❌ No JSON execution plan found at: {plan_path}")
            return False

        max_attempts = 3
        healed_any = False

        try:
            for attempt in range(1, max_attempts + 1):
                print(f"\n🔬 Running execution verification trial (Attempt {attempt}/{max_attempts})...")

                python_exe = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
                result = subprocess.run(
                    [python_exe, "-m", "pytest", trial_script_path, "-v", "--tb=short"],
                    capture_output=True, text=True
                )

                if result.returncode == 0:
                    if healed_any:
                        print("✨ Test execution successfully STABILIZED via local MCP server operations!")
                    else:
                        print("🎯 Test execution returned clean status code on first pass. No healing required.")
                    return True

                print(f"⚠️ Runtime execution failure detected. Intercepting trace errors for healing...")
                healed_any = True

                self.heal_codebase(result.stdout + "\n" + result.stderr, trial_script_path, issue_clean)

                from pipeline import compile_test_from_json_plan
                compile_test_from_json_plan(issue_id, plan_path, trial_script_path)
        finally:
            self.mcp.shutdown()

        return False

    def heal_codebase(self, error_trace, script_path, issue_clean):
        """Commands the Local Playwright MCP Server to execute infrastructure prerequisites before AI discovery."""
        print("🧠 Analyzing error signatures using local context mappings...")
        print(f"🎯 Target script error tracking scope assigned: {os.path.basename(script_path)}")

        manifest = generate_pom_manifest()

        # 1. Boot up the browser through the stateful MCP controller
        self.mcp.execute_mcp_tool("playwright_launch", {"url": "https://saucedemo.com"})

        # 2. --- PREREQUISITE BASELINE CONTROL LAYER ---
        # Execute the absolute baseline prerequisite authentication sequence using standard tools
        # This shifts the browser's viewport PAST the landing gate onto the true target starting screen
        print("🔑 Framework Prerequisite Gate: Executing mandatory authentication sequence to unlock target views...")
        self.mcp.execute_mcp_tool("playwright_fill", {"selector": '[data-test="username"]', "text": "standard_user"})
        self.mcp.execute_mcp_tool("playwright_fill", {"selector": '[data-test="password"]', "text": "secret_sauce"})
        self.mcp.execute_mcp_tool("playwright_click", {"selector": '[data-test="login-button"]'})

        # 3. Extract the real-time elements from the UNLOCKED dashboard view via MCP
        mcp_dom_data = self.mcp.execute_mcp_tool("playwright_get_selectors", {})

        system_prompt = (
            "You are an expert autonomous SDET architecture agent controlling an authenticated browser via an MCP server interface.\n"
            "Review the runtime execution traceback error and the live data elements returned by the MCP server viewport.\n\n"
            "CRITICAL ACTIONS RULES:\n"
            "1. You are looking at an inner authenticated application page view. You are STRICTLY FORBIDDEN from generating or modifying LoginPage selectors.\n"
            "2. Set action_mode to 'CREATE_NEW_PAGE' to construct the missing inner page class module required by the Acceptance Criteria.\n"
            "3. Map selectors dictionary keys to exact data-test or CSS attributes visible inside the live MCP elements array.\n"
            "4. Define clean action methods targeting those properties to satisfy the script flow sequence."
        )

        user_prompt = (
            f"ACTUAL RUNTIME ERROR LOG:\n{error_trace}\n\n"
            f"LIVE DISCOVERED DOM METRICS FROM INNER VIEWPORT OVER MCP:\n{json.dumps(mcp_dom_data, indent=2)}\n\n"
            f"CURRENT CODEBASE MANIFEST STRUCTURAL INVENTORY:\n{json.dumps(manifest, indent=2)}"
        )

        structured_json_schema = {
            "type": "object",
            "properties": {
                "action_mode": {
                    "type": "string",
                    "enum": ["CREATE_NEW_PAGE", "EDIT_EXISTING_SELECTOR"]
                },
                "target_page_file": {
                    "type": "string",
                    "description": "The lowercase snake_case filename to construct inside src/pages/ (e.g., 'inventory_page.py')."
                },
                "class_name": {
                    "type": "string",
                    "description": "The PascalCase class definition signature matching the target (e.g., 'InventoryPage')."
                },
                "selectors_dict": {
                    "type": "object",
                    "description": "Dictionary mapping variable property name keys to valid locator selector strings found in the MCP elements array."
                },
                "methods_list": {
                    "type": "array",
                    "description": "Array of distinct interaction methods to implement inside the new page class.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string",
                                     "description": "The lowercase descriptive function name (e.g., 'add_item_to_cart')."},
                            "param": {"type": "string",
                                      "description": "The argument input variable name string. Leave blank if none required."},
                            "selector_var": {"type": "string",
                                             "description": "The matching dictionary locator variable key property reference string."},
                            "action": {"type": "string", "enum": ["click", "fill"],
                                       "description": "The pure Playwright functional verb interaction format."}
                        },
                        "required": ["name", "selector_var", "action"]
                    }
                },
                "target_variable": {"type": "string"},
                "corrected_selector": {"type": "string"}
            },
            "required": ["action_mode", "target_page_file", "class_name", "selectors_dict", "methods_list"]
        }

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "format": structured_json_schema,
            "options": {"temperature": 0.0},
            "stream": False
        }

        try:
            resp = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=60)
            resp.raise_for_status()
            raw_content = resp.json().get("message", {}).get("content", "").strip()

            if not raw_content:
                print("❌ Critical System Error: Empty tool response map returned from model layer.")
                return

            print(f"📡 Raw Structured Payload Received: {raw_content}")
            heal_instructions = json.loads(raw_content)
            mode = heal_instructions.get("action_mode")

            raw_filename = heal_instructions.get("target_page_file", "new_page.py")
            base_name = os.path.basename(raw_filename).replace(".py", "")
            sanitized_filename = "".join(["_" + c.lower() if c.isupper() else c for c in base_name]).lstrip("_")
            sanitized_filename = sanitized_filename.replace("__", "_") + ".py"

            if mode == "CREATE_NEW_PAGE":
                print(
                    f"🏗️ Discovery Route Triggered: Constructing domain block 'src/pages/{sanitized_filename}' from scratch...")

                methods_data = []
                for m in heal_instructions.get("methods_list", []):
                    if m.get("name") != "__init__":
                        methods_data.append({str(k): str(v) for k, v in m.items()})

                result = self.mcp.tool_create_new_page_object(
                    filename=sanitized_filename,
                    class_name=heal_instructions.get("class_name"),
                    selectors_dict=heal_instructions.get("selectors_dict", {}),
                    methods_list=methods_data
                )
                print(f"📝 MCP Tool Page Composition Status: {json.dumps(result)}")

                local_plan_path = os.path.join(BASE_DIR, "tests", "pending_review", f"plan_{issue_clean}.json")
                if os.path.exists(local_plan_path):
                    with open(local_plan_path, "r", encoding="utf-8") as f:
                        execution_plan = json.load(f)

                    target_class = heal_instructions.get("class_name", "InventoryPage")
                    chosen_method = methods_data[-1].get("name",
                                                         "add_item_to_cart") if methods_data else "add_item_to_cart"

                    updated_plan = []
                    for step in execution_plan:
                        if "MISSING_" in str(step.get("class")) or step.get("class") == "InventoryPage":
                            step["class"] = target_class
                            step["method"] = chosen_method
                        updated_plan.append(step)

                    with open(local_plan_path, "w", encoding="utf-8") as f:
                        json.dump(updated_plan, f, indent=2)
                    print(
                        f"🔄 Plan Synchronization Complete: Updated plan mapping references to '{target_class}.{chosen_method}' safely.")

            elif mode == "EDIT_EXISTING_SELECTOR":
                print(
                    f"🔧 Surgery Route Triggered: Patching broken structural locator property in '{sanitized_filename}'...")
                result = self.mcp.tool_edit_page_object(
                    filename=sanitized_filename,
                    target_var=heal_instructions.get("target_variable"),
                    new_selector=heal_instructions.get("corrected_selector")
                )
                print(f"📝 MCP Tool Variable Modification Status: {json.dumps(result)}")

        except requests.RequestException as req_err:
            print(f"❌ Self-healing mutation network call failed: {req_err}")
        except json.JSONDecodeError as json_err:
            print(f"❌ Self-healing structure decoding failed: {json_err}")
        except Exception as general_err:
            print(f"❌ Self-healing mutation run encountered unexpected system error: {general_err}")

