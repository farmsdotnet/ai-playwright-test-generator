import os
import re
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


def read_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def get_pom_references():
    """Scans src/pages to give the AI context on available page objects."""
    pages_dir = "../src/pages"
    reference_string = "Available Page Objects and Methods:\n"

    if os.path.exists(pages_dir):
        for file in os.listdir(pages_dir):
            if file.endswith(".py") and not file.startswith("__"):
                content = read_file(os.path.join(pages_dir, file))
                # Simple regex extraction to grab class and def lines
                structure = "\n".join(
                    [line.strip() for line in content.splitlines() if "class " in line or "def " in line])
                reference_string += f"\n--- File: {file} ---\n{structure}\n"
    return reference_string


def generate_test_case(issue_id):
    main_skill = read_file("../context_store/OLD_glob_dom_rules.md")
    child_skill = read_file(f"context_store/child_contexts/{issue_id}_ac.md")
    pom_reference = get_pom_references()

    system_prompt = f"""
    You are an expert QA Automation Engineer. Generate a python Pytest script using Playwright.

    Target Application Domain Rules:
    {main_skill}

    Target Acceptance Criteria for this specific test case:
    {child_skill}

    You MUST exclusively use the existing POM structure outlined below:
    {pom_reference}

    Output ONLY a single valid Python code block enclosed in ```python ```. 
    Do not add conversational text or markdown analysis before or after the code block.
    """

    payload = {
        "model": "qwen2.5:7b",  # Or your chosen active local model
        "prompt": system_prompt,
        "stream": False
    }

    print(f"🤖 Interrogating local engine for {issue_id} codebase compilation...")
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        if response.status_code == 200:
            raw_output = response.json().get("response", "")
            code_match = re.search(r"```python(.*?)```", raw_output, re.DOTALL)
            code = code_match.group(1).strip() if code_match else raw_output.strip()

            os.makedirs("../tests/pending_review", exist_ok=True)
            pending_path = f"tests/pending_review/test_{issue_id.lower()}.py"
            with open(pending_path, "w", encoding="utf-8") as f:
                f.write(code)
            return pending_path
        else:
            print(f"❌ Ollama returned status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to reach local engine instance: {e}")
    return None
