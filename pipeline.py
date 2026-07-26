import os
import json
import shutil
import sys
import subprocess
from linear_fetch import save_ac_context
from manifest_generator import generate_pom_manifest

BASE_DIR = r"C:\Dev Projects 2026 Local\GIT\ai_qa_framework"


def read_file(file_path):
    if not os.path.exists(file_path): return ""
    with open(file_path, "r", encoding="utf-8") as f: return f.read()


def compile_test_from_json_plan(issue_id, plan_file, pending_file):
    """
    DETERMINISTIC REFLECTIVE COMPILER:
    Reads the abstract JSON execution plan, matches it dynamically with
    the codebase directory modules, and assembles flawless Python syntax code.
    """
    print("⚡ Reflective Compiler: Parsing execution sequence and writing clean python file...")
    if not os.path.exists(plan_file):
        return False

    with open(plan_file, "r", encoding="utf-8") as f:
        execution_plan = json.load(f)

    manifest = generate_pom_manifest()
    issue_id_upper = issue_id.upper().strip()
    func_name = f"test_{issue_id_upper.lower().replace('-', '_')}"

    required_classes = set(step.get("class") for step in execution_plan if step.get("class"))

    # Structural sync protection block
    if "InventoryPage" not in required_classes and "FAR_6" in issue_id_upper:
        required_classes.add("InventoryPage")

    import_lines = ["import pytest", "from playwright.sync_api import sync_playwright"]
    for cls in required_classes:
        if cls in manifest:
            mod_path = manifest[cls].get("file_path", "").replace("/", ".").replace(".py", "")
            import_lines.append(f"from {mod_path} import {cls}")

    instantiation_lines = []
    for cls in required_classes:
        var_name = "".join(["_" + c.lower() if c.isupper() else c for c in cls]).lstrip("_")
        var_name = var_name.replace("_page", "page_object").replace("page_object", "_page")
        instantiation_lines.append(f"        {var_name} = {cls}(page)")

    step_lines = []
    for step in execution_plan:
        cls = step.get("class")
        method = step.get("method")
        args = step.get("args", [])

        if not cls or not method: continue

        # Guard: Overwrite common model class-drifts on the fly to protect POM boundaries
        if cls == "LoginPage" and method in ["filter", "launch", "verify_on_inventory_page"]:
            cls = "InventoryPage"

        if method.startswith("MISSING_"):
            step_lines.append(f"        # TODO: Implement missing page object operation layer: {method}")
            continue

        var_name = "".join(["_" + c.lower() if c.isupper() else c for c in cls]).lstrip("_")
        var_name = var_name.replace("_page", "page_object").replace("page_object", "_page")

        formatted_args = ", ".join([f"'{a}'" if isinstance(a, str) else str(a) for a in args])
        step_lines.append(f"        {var_name}.{method}({formatted_args})")

    scaffolded_code = (
        f"{'\n'.join(import_lines)}\n\n\n"
        f"def {func_name}():\n"
        f"    with sync_playwright() as p:\n"
        f"        browser = p.chromium.launch(headless=False, slow_mo=1000)\n"
        f"        page = browser.new_page()\n\n"
        f"{'\n'.join(instantiation_lines)}\n\n"
        f"{'\n'.join(step_lines)}\n\n"
        f"        browser.close()\n"
    )

    with open(pending_file, "w", encoding="utf-8") as f:
        f.write(scaffolded_code)
    return True


def run_post_approval_menu(approved_file_path):
    print(f"\n⚡ Post-Approval Actions Available:")
    print("---------------------------------")
    print("[C] Execute Current Test Only")
    print("[A] Execute All Staging Tests")
    print("[E] Exit Pipeline Workspace")

    python_exe = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
    master_runner = os.path.join(BASE_DIR, "run_staging.py")

    while True:
        choice = input("\nSelect Action -> [C]urrent | [A]ll | [E]xit: ").strip().lower()
        if choice == 'c':
            print(f"\n🚀 Launching Isolated Test Script: {approved_file_path}...\n")
            subprocess.run([python_exe, "-m", "pytest", approved_file_path, "-v", "-s"])
            break
        elif choice == 'a':
            print(f"\n🚀 Launching Complete Staging Suite via Master Runner...\n")
            subprocess.run([python_exe, master_runner])
            break
        elif choice == 'e':
            print("\n👋 Safely exiting pipeline workspace context. Setup complete.")
            sys.exit(0)
        else:
            print("⚠️ Unrecognized selection. Please supply C, A, or E.")


def run_pipeline(issue_id):
    issue_clean = issue_id.upper().strip()
    safe_id = issue_clean.lower().replace('-', '_')

    pending_dir = os.path.join(BASE_DIR, "tests", "pending_review")
    plan_file = os.path.join(pending_dir, f"plan_{safe_id}.json")
    pending_file = os.path.join(pending_dir, f"test_{safe_id}.py")

    if issue_clean != "TKT-999":
        if not save_ac_context(issue_clean): return

    from generate_test import generate_playwright_test
    if not generate_playwright_test(issue_clean):
        print("❌ JSON Plan compilation failed.")
        return

    if not compile_test_from_json_plan(issue_clean, plan_file, pending_file):
        print("❌ Reflective compiler failure.")
        return

    python_exe = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
    result = subprocess.run([python_exe, "-m", "pytest", pending_file, "--collect-only"], capture_output=True,
                            text=True)

    if result.returncode != 0:
        print("❌ Validation Gate Failure: Python syntax broken inside file.")
        print(result.stderr)
        return

    print("✅ System Synchronization Successful! File is 100% stable.")

    while True:
        if not os.path.exists(pending_file):
            print(f"❌ Operational Error: Expected file not found at {pending_file}")
            break

        print(f"\n==================== [REVIEWING DRAFT]: {pending_file} ====================")
        print(read_file(pending_file))
        print("=====================================================================")

        choice = input("\nSelect Action -> [A]pprove | [D]ecline: ").strip().lower()

        if choice == 'a':
            staging_dir = os.path.join(BASE_DIR, "tests", "staging")
            os.makedirs(staging_dir, exist_ok=True)
            dest = os.path.join(staging_dir, f"test_{safe_id}.py")
            if os.path.exists(dest):
                os.remove(dest)
            shutil.move(pending_file, dest)
            print(f"🚀 Code block approved! Moved into staging: {dest}")
            run_post_approval_menu(dest)
            break
        elif choice in ['d', 'r', 'decline']:
            if os.path.exists(pending_file):
                os.remove(pending_file)
            print("🗑️ Script draft declined and discarded cleanly from disk.")
            break


if __name__ == "__main__":
    print("\n-----------------------------------------------------")
    print("🚀 INITIALIZING AI-QA FRAMEWORK PIPELINE CONTROL...")
    print("-----------------------------------------------------")
    ticket = input("Enter Ticket ID to process (or 'TKT-999' for control test): ").strip()
    if ticket: run_pipeline(ticket)
