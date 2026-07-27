import os
import re
import shutil
import requests
import sys
import subprocess
from linear_fetch import save_ac_context
from generate_test import generate_test_case, read_file, get_pom_references, build_final_script, OLLAMA_CHAT_URL

BASE_PATH = r"C:\Dev Projects 2026 Local\GIT\ai_qa_framework"


def regenerate_with_feedback(issue_id, feedback_text, current_code):
    main_skill = read_file(os.path.join(BASE_PATH, "context_store", "2_OLD_glob_dom_rules.md"))
    child_skill = read_file(
        os.path.join(BASE_PATH, "context_store", "child_contexts", f"{issue_id.upper().strip()}_ac.md"))
    pom_reference = get_pom_references()

    messages = [
        {
            "role": "system",
            "content": f"You are correcting Playwright code based on peer review feedback. Rules:\n{main_skill}\nPOM:\n{pom_reference}"
        },
        {
            "role": "user",
            "content": f"Criteria:\n{child_skill}\n\nPrevious Code Draft:\n{current_code}\n\nFEEDBACK TO APPLY INSTANTLY:\n{feedback_text}\n\nWrite ONLY the executable code lines. No function definitions or imports allowed."
        }
    ]

    payload = {
        "model": "qwen2.5:7b",
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.0}
    }

    response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=60)
    if response.status_code == 200:
        ai_text = response.json().get("message", {}).get("content", "")
        return build_final_script(issue_id, ai_text)
    raise Exception("Local model disconnected.")


def run_post_approval_menu(approved_file_path):
    """Prompts the user to instantly execute tests right after approval without thread lock."""
    print(f"\n⚡ Post-Approval Actions Available:")
    print("---------------------------------")
    print("[C] Execute Current Test Only")
    print("[A] Execute All Staging Tests")
    print("[E] Exit Pipeline")

    python_exe = os.path.join(BASE_PATH, ".venv", "Scripts", "python.exe")
    master_runner = os.path.join(BASE_PATH, "run_staging.py")

    while True:
        choice = input("\nSelect Action -> [C]urrent | [A]ll | [E]xit: ").strip().lower()

        if choice == 'c':
            print(f"\n🚀 Launching Current Test: {approved_file_path}...\n")
            # Uses isolated system subprocess targeting the local python executable directly
            subprocess.run([python_exe, "-m", "pytest", approved_file_path, "-v", "-s"])
            break

        elif choice == 'a':
            print(f"\n🚀 Launching Complete Staging Suite via Master Runner...\n")
            # Directly triggers your master runner script at the OS level
            subprocess.run([python_exe, master_runner])
            break

        elif choice == 'e':
            print("\n👋 Safely exiting pipeline workspace context. Good night!")
            sys.exit(0)
        else:
            print("⚠️ Unrecognized choice. Please type C, A, or E.")


def run_pipeline(issue_id):
    issue_clean = issue_id.upper().strip()
    safe_id = issue_clean.lower().replace('-', '_')

    if issue_clean != "TKT-999":
        if not save_ac_context(issue_clean):
            print(f"❌ Aborting. Could not sync criteria for {issue_clean}")
            return

    pending_file = generate_test_case(issue_clean)
    if not pending_file:
        print("❌ Generation failed. No script was compiled.")
        return

    while True:
        print(f"\n==================== [REVIEWING]: {pending_file} ====================")
        print(read_file(pending_file))
        print("=====================================================================")

        choice = input("\nSelect Action -> [A]pprove | [D]ecline | [S]uggest Changes: ").strip().lower()

        if choice == 'a':
            staging_dir = os.path.join(BASE_PATH, "tests", "staging")
            os.makedirs(staging_dir, exist_ok=True)
            dest = os.path.join(staging_dir, f"test_{safe_id}.py")
            if os.path.exists(dest): os.remove(dest)
            shutil.move(pending_file, dest)
            print(f"🚀 Approved! Saved to live suite: {dest}")

            # Trigger our non-blocking menu
            run_post_approval_menu(dest)
            break

        elif choice in ['d', 'r', 'decline']:
            if os.path.exists(pending_file): os.remove(pending_file)
            print("🗑️ Script declined and deleted.")
            break

        elif choice == 's':
            feedback = input("\n📝 Enter adjustments for the AI: ").strip()
            if feedback:
                try:
                    updated_code = regenerate_with_feedback(issue_clean, feedback, read_file(pending_file))
                    with open(pending_file, "w", encoding="utf-8") as f:
                        f.write(updated_code)
                except Exception as e:
                    print(f"❌ Refinement failed: {e}")


if __name__ == "__main__":
    print("\n-----------------------------------------------------")
    print("🚀 INITIALIZING AI-QA FRAMEWORK RUNNER SCRIPT...")
    print("-----------------------------------------------------")
    ticket = input("Enter Linear Ticket ID to process (or 'TKT-999' for control test): ").strip()
    if ticket:
        run_pipeline(ticket)
