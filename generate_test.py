import os
import json
import requests
from manifest_generator import generate_pom_manifest

# Framework System Constants - LOCKED BACK TO STABLE QWEN 2.5
BASE_DIR = r"C:\Dev Projects 2026 Local\GIT\ai_qa_framework"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:7b"


def load_context_files(issue_id):
    """Reads and aggregates the Main Skill and the dynamic Child Skill files."""
    issue_id_upper = issue_id.upper().strip()
    global_rules_path = os.path.join(BASE_DIR, "context_store", "global_domain_rules.md")
    child_context_path = os.path.join(BASE_DIR, "context_store", "child_contexts", f"{issue_id_upper}_ac.md")

    if not os.path.exists(global_rules_path) or not os.path.exists(child_context_path):
        return None, None

    with open(global_rules_path, "r", encoding="utf-8") as f:
        global_rules = f.read()
    with open(child_context_path, "r", encoding="utf-8") as f:
        child_criteria = f.read()

    return global_rules, child_criteria


def clean_model_output(raw_text):
    """Strips out markdown code fence wrappers from the string payload cleanly."""
    clean_text = raw_text.replace("```json", "").replace("```python", "").replace("```", "").strip()
    return clean_text


def extract_abstract_actions(child_criteria):
    """
    PASS 1: THE REQ STRIPPER LAYER:
    Converts raw technical ticket criteria into pure high-level user actions.
    Strips raw DOM/HTML selector hints so the downstream test generator is completely blind to selectors.
    """
    print("🧠 Pass 1: Extracting high-level abstract actions from ticket...")
    system_prompt = (
        "You are a business analysis extraction engine.\n"
        "Convert raw technical ticket criteria into an abstract step-by-step list of user behaviors.\n"
        "CRITICAL RULES:\n"
        "1. Strip out any mentions of raw CSS selectors, hashtags (#), classes (.), or IDs.\n"
        "2. Translate actions into semantic language. Example: 'Click #submit-btn' becomes 'Submit the form'.\n"
        "3. Output ONLY the step-by-step checklist. No descriptions, no code blocks."
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Target Criteria to Abstract:\n{child_criteria}"}
        ],
        "options": {"temperature": 0.0},
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=60)
        return response.json().get("message", {}).get("content", "").strip()
    except Exception:
        return child_criteria


def generate_playwright_test(issue_id):
    """
    UNIVERSAL JSON ORCHESTRATION ROUTER:
    Queries Qwen 2.5 to output a strict execution sequence plan mapping
    the AC directly to the physical codebase manifest signatures.
    """
    issue_id_upper = issue_id.upper().strip()
    func_name_clean = f"test_{issue_id_upper.lower().replace('-', '_')}"
    global_rules, child_criteria = load_context_files(issue_id_upper)

    if not global_rules or not child_criteria:
        return False

    # Pull the codebase properties map snapshot
    current_manifest = generate_pom_manifest()

    # Abstract the criteria to protect the compiler from raw selectors
    abstract_actions = extract_abstract_actions(child_criteria)

    system_prompt = (
        f"{global_rules}\n\n"
        f"UNIVERSAL JSON COMPILATION CONTRACT:\n"
        f"1. Your job is to output a strict step-by-step user execution sequence matching the AC requirements.\n"
        f"2. You are completely FORBIDDEN from generating raw Python or JavaScript lines. Do not use code blocks.\n"
        f"3. STRICT CLASS BOUNDARY RULES (POM ENFORCEMENT):\n"
        f"   - Authentication steps (entering username/password, clicking login) belong strictly to 'LoginPage'.\n"
        f"   - Product catalog steps (sorting, filtering, checking product text, inventory details) belong strictly to 'InventoryPage'.\n"
        f"   - NEVER assign inventory catalog methods to the 'LoginPage' block.\n"
        f"4. If a required method does not exist in the manifest layouts, use the method signature string field name: 'MISSING_<action_description>'.\n"
        f"5. Output ONLY a valid, parseable JSON array of objects following this exact schema layout structure:\n"
        f"[\n"
        f"  {{\"class\": \"LoginPage\", \"method\": \"login\", \"args\": [\"standard_user\", \"secret_sauce\"]}},\n"
        f"  {{\"class\": \"InventoryPage\", \"method\": \"filter\", \"args\": [\"lohi\"]}}\n"
        f"]\n"
        f"6. Absolutely zero introductory explanations, notes, or commentary summaries text."
    )

    user_prompt = (
        f"Review these high-level user actions:\n{abstract_actions}\n\n"
        f"Map out the exact execution plan array selecting strictly from these available manifest structures:\n"
        f"{json.dumps(current_manifest, indent=2)}"
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "options": {"temperature": 0.0},
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=90)
        response.raise_for_status()
        raw_output = response.json().get("message", {}).get("content", "").strip()

        json_clean = clean_model_output(raw_output)
        execution_plan = json.loads(json_clean)

        pending_dir = os.path.join(BASE_DIR, "tests", "pending_review")
        os.makedirs(pending_dir, exist_ok=True)
        checkpoint_path = os.path.join(pending_dir, f"plan_{issue_id_upper.lower().replace('-', '_')}.json")

        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(execution_plan, f, indent=2)

        print(f"💾 Universal Plan Snapshot Saved to Disk: {checkpoint_path}")
        return True

    except Exception as e:
        print(f"❌ Structural JSON routing sequence failure: {e}")
        return False
