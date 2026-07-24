import os
import re
import requests
from dotenv import load_dotenv

# Absolute path declaration to ensure Windows reads the token perfectly
BASE_DIR = r"C:\Dev Projects 2026 [Local]\GIT\ai_qa_framework"
load_dotenv(os.path.join(BASE_DIR, ".env"))

LINEAR_API_URL = "https://api.linear.app/graphql"
LINEAR_TOKEN = os.getenv("LINEAR_API_TOKEN")


def fetch_linear_issue(issue_id):
    if not LINEAR_TOKEN:
        raise ValueError("❌ LINEAR_API_TOKEN is empty inside your .env file.")

    # A standard single header signature block
    headers = {
        "Content-Type": "application/json",
        "Authorization": LINEAR_TOKEN.strip()
    }

    # Flat query string mapping
    clean_id = issue_id.upper().strip()
    query_string = f'query {{ issue(id: "{clean_id}") {{ identifier title description }} }}'

    try:
        # A single, unnested POST request execution block
        response = requests.post(LINEAR_API_URL, json={"query": query_string}, headers=headers, timeout=15)

        if response.status_code == 200:
            return response.json().get("data", {}).get("issue", None)

        print(f"❌ Linear Connection Refused. Status: {response.status_code}")
        print(f"Response: {response.text}")
        return None
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None


def save_ac_context(issue_id):
    print(f"📡 Requesting data from Linear for ticket: {issue_id}")
    issue = fetch_linear_issue(issue_id)

    if not issue:
        print(f"❌ Issue data fetch returned empty result for {issue_id}.")
        return False

    body = issue.get('description', '')
    if not body:
        print(f"⚠️ Ticket description body is empty.")
        return False

    match = re.search(r'(?i)A\.C:?\s*(.*)', body, re.DOTALL)
    if match:
        ac_content = match.group(1).strip()
        output_dir = os.path.join(BASE_DIR, "context_store", "child_contexts")
        os.makedirs(output_dir, exist_ok=True)

        file_path = os.path.join(output_dir, f"{issue_id.upper().strip()}_ac.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(ac_content)

        print(f"🎯 Live Acceptance Criteria stored successfully: {file_path}")
        return True

    print(f"⚠️ Marker 'A.C:' not found inside the description of {issue_id}.")
    return False
