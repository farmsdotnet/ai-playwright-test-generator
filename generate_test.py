import os
import json
import requests
import re

BASE_DIR = r"C:\Dev Projects 2026 Local\GIT\ai_qa_framework"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5:7b"


def load_context_files(issue_id):
    """Reads the dynamic Child Context Acceptance Criteria file directly from disk."""
    issue_id_upper = issue_id.upper().strip()
    child_context_path = os.path.join(BASE_DIR, "context_store", "child_contexts", f"{issue_id_upper}_ac.md")

    if not os.path.exists(child_context_path):
        return None

    with open(child_context_path, "r", encoding="utf-8") as f:
        return f.read()


def generate_playwright_test(issue_id):
    """
    DETERMINISTIC AC TO JSON TRANSLATOR:
    Parses raw ticket markdown steps directly into strict JSON execution objects.
    Forces explicit placeholders for non-existent code segments to trigger downstream MCP creation.
    """
    issue_id_upper = issue_id.upper().strip()
    child_criteria = load_context_files(issue_id_upper)

    if not child_criteria:
        print(f"❌ Target Acceptance Criteria file missing for issue reference: {issue_id_upper}")
        return False

    system_prompt = (
        "You are a strict requirements parsing engine.\n"
        "Convert every user behavior step described in the provided criteria text into a structured JSON array token.\n"
        "Output ONLY the valid, parseable JSON array of objects. Do not include notes, markdown fences, or padding text."
    )

    user_prompt = (
        f"THE CRITERIA TEXT TO COMPLY WITH AND CONVERT:\n"
        f"\"\"\"\n{child_criteria}\n\"\"\"\n\n"
        f"COMPILATION RULES:\n"
        f"1. Create a distinct object block for every behavioral action outlined in the text.\n"
        f"2. You are FORBIDDEN from truncating or stopping the sequence after the initial authentication lines.\n"
        f"3. Since the login page handles the prerequisite, assign the downstream catalog dashboard steps (like clicking catalog buttons or locating elements) to a placeholder class named 'MISSING_InventoryPage'.\n\n"
        f"EXACT OUTPUT SCHEMA FORMAT PATTERN REQUIRED:\n"
        f"[\n"
        f"  {{\"class\": \"LoginPage\", \"method\": \"login\", \"args\": [\"standard_user\", \"secret_sauce\"]}},\n"
        f"  {{\"class\": \"MISSING_InventoryPage\", \"method\": \"add_item_to_cart\", \"args\": [\"sauce-labs-backpack\"]}}\n"
        f"]"
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

        json_clean = raw_output.replace("```json", "").replace("```", "").strip()

        import re
        json_match = re.search(r"\[.*\]", json_clean, re.DOTALL)
        if json_match:
            json_clean = json_match.group(0)

        execution_plan = json.loads(json_clean)

        pending_dir = os.path.join(BASE_DIR, "tests", "pending_review")
        os.makedirs(pending_dir, exist_ok=True)
        checkpoint_path = os.path.join(pending_dir, f"plan_{issue_id_upper.lower().replace('-', '_')}.json")

        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(execution_plan, f, indent=2)

        print(f"💾 Universal Plan Snapshot Saved to Disk: {checkpoint_path}")
        return True

    except Exception as e:
        print(f"❌ Plan snapshot orchestration failed: {e}")
        return False
