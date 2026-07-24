import os
import re
import requests

OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
BASE_PATH = r"C:\Dev Projects 2026 Local\GIT\ai_qa_framework"


def read_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: return f.read()
    return ""


def get_pom_references():
    pages_dir = os.path.join(BASE_PATH, "src", "pages")
    reference_string = "Available Page Objects and Methods:\n"
    if os.path.exists(pages_dir):
        for file in os.listdir(pages_dir):
            if file.endswith(".py") and not file.startswith("__"):
                content = read_file(os.path.join(pages_dir, file))
                structure = "\n".join(
                    [line.strip() for line in content.splitlines() if "class " in line or "def " in line])
                reference_string += f"\n--- File: {file} ---\n{structure}\n"
    return reference_string


def build_final_script(issue_id, raw_ai_output):
    """Cleanly extracts python lines and wraps them inside the strict template wrapper."""
    if "```python" in raw_ai_output:
        code = re.search(r"```python(.*?)```", raw_ai_output, re.DOTALL).group(1).strip()
    elif "```" in raw_ai_output:
        code = re.search(r"```(.*?)```", raw_ai_output, re.DOTALL).group(1).strip()
    else:
        code = raw_ai_output

    clean_body_lines = []
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped or any(
                stripped.startswith(x) for x in ["def test_", "import ", "from ", "with sync_playwright"]):
            continue

        # Automated safety handler replacing hallucinated .navigate definitions
        if "page.navigate(" in stripped:
            stripped = stripped.replace("page.navigate(", "page.goto(")

        clean_body_lines.append(stripped)

    indented_body = "\n".join([f"            {line}" for line in clean_body_lines])
    safe_func_id = issue_id.lower().replace("-", "_")

    return f"""from playwright.sync_api import sync_playwright
from src.pages.login_page import LoginPage
# End of automated imports

def test_{safe_func_id}():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        context = browser.new_context()
        page = context.new_page()
        try:
{indented_body}
            print("🚀 Test executed successfully!")
        finally:
            context.close()
            browser.close()
"""


def generate_test_case(issue_id):
    main_skill = read_file(os.path.join(BASE_PATH, "context_store", "global_domain_rules.md"))
    child_skill = read_file(
        os.path.join(BASE_PATH, "context_store", "child_contexts", f"{issue_id.upper().strip()}_ac.md"))
    pom_reference = get_pom_references()

    # Structural Chat Payload Message Arrays
    messages = [
        {
            "role": "system",
            "content": f"You are a strict QA Test Automation Engineer. You write python test steps using pre-written Page Objects. Instructions:\n{main_skill}\nAvailable objects:\n{pom_reference}"
        },
        {
            "role": "user",
            "content": f"Write the exact python test code lines to satisfy these criteria. Remember to NEVER use example.com, ALWAYS use saucedemo.com, and do NOT write function defs or imports:\n{child_skill}"
        },
        {
            "role": "assistant",
            "content": "```python\nlogin_page = LoginPage(page)\nlogin_page.login('standard_user', 'secret_sauce')\npage.goto('https://saucedemo.com')\n```"
        },
        {
            "role": "user",
            "content": f"Now write the clean code steps for this specific target ticket requirements:\n{child_skill}"
        }
    ]

    payload = {
        "model": "qwen2.5:7b",
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.0,  # Zero out creativity to eliminate hallucinations completely
            "num_ctx": 8192
        }
    }

    try:
        response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=60)
        if response.status_code == 200:
            ai_text = response.json().get("message", {}).get("content", "")
            final_code = build_final_script(issue_id, ai_text)

            pending_dir = os.path.join(BASE_PATH, "tests", "pending_review")
            os.makedirs(pending_dir, exist_ok=True)

            clean_id = issue_id.upper().strip().replace("-", "_").lower()
            pending_path = os.path.join(pending_dir, f"test_{clean_id}.py")

            with open(pending_path, "w", encoding="utf-8") as f:
                f.write(final_code)
            return pending_path
    except Exception as e:
        print(f"❌ Generation failure: {e}")
    return None
