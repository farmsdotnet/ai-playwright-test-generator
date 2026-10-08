#!/usr/bin/env python3
"""Stand-in for the `claude` CLI, used only by test_cli_dry_run.py. It reads the task prompt cli.py
passes with -p, pulls out the file paths it was told to write, writes plausible generated files
for whichever language the prompt asks for, and prints stream-json events (one MCP snapshot
tool_result plus a final result event) exactly where the real Claude Code would.

FAKE_CLAUDE_MODE:
  good          - correct files on the first turn
  bad_then_good - a hallucinated locator on the first turn, fixed on the --resume retry turn
"""
import json
import os
import re
import sys

SNAPSHOT = '- textbox "Username" [ref=e1]\n- button "Login" [ref=e2]\n- heading "Products" [level=1]'


def arg_after(flag):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else None


prompt = arg_after("-p")
resumed = "--resume" in sys.argv

if resumed:
    po, test, manifest = re.search(
        r"Re-check `([^`]+)` and `([^`]+)` against the manifest at `([^`]+)`", prompt
    ).groups()
else:
    manifest = re.search(r"(?:Write this manifest to|A step manifest already exists at) `([^`]+)`", prompt).group(1)
    po = re.search(r"Write the page object\(s\) to `([^`]+)`", prompt).group(1)
    test = re.search(r"Write the (?:pytest )?test to `([^`]+)`", prompt).group(1)
is_ts = test.endswith(".ts")

if not resumed and "Write this manifest to" in prompt:
    with open(manifest, "w", encoding="utf-8") as f:
        json.dump({"scenario_name": "login", "base_url": "https://www.saucedemo.com", "steps": [
            {"step_id": 1, "step_type": "action", "description": "Navigate",
             "target_element_description": None, "expected_result": None},
            {"step_id": 2, "step_type": "action", "description": "Click Login",
             "target_element_description": "Login button", "expected_result": None},
            {"step_id": 3, "step_type": "assertion", "description": "Products header shown",
             "target_element_description": "header", "expected_result": "Products"},
        ]}, f)

mode = os.environ.get("FAKE_CLAUDE_MODE", "good")
login_name = "Log in now" if (mode == "bad_then_good" and not resumed) else "Login"

if is_ts:
    spec = re.search(r"from '([^']+)';` \(no `\.ts` extension\)", prompt)
    import_from = spec.group(1) if spec else "../pageObjects/login.page"  # retry turn: same file
    page_code = f"""import {{ Page }} from '@playwright/test';

export class LoginPage {{
  constructor(private readonly page: Page) {{}}

  async clickLogin(): Promise<void> {{
    // step 2: click login
    await this.page.getByRole('button', {{ name: '{login_name}' }}).click();
  }}
}}
"""
    test_code = f"""import {{ test, expect }} from '@playwright/test';
import {{ LoginPage }} from '{import_from}';

const BASE_URL = 'https://www.saucedemo.com';

test('login', async ({{ page }}) => {{
  // step 1: navigate
  await page.goto(BASE_URL);
  await new LoginPage(page).clickLogin();
  // step 3: header
  await expect(page.getByRole('heading', {{ name: 'Products' }})).toBeVisible();
}});
"""
else:
    page_code = f"""from playwright.sync_api import Page


class LoginPage:
    def __init__(self, page: Page):
        self.page = page

    def click_login(self):
        # step 2: click login
        self.page.get_by_role("button", name="{login_name}").click()
"""
    test_code = """from playwright.sync_api import expect

from page_objects.login_page import LoginPage


def test_login(page):
    # step 1: navigate
    page.goto("https://www.saucedemo.com")
    LoginPage(page).click_login()
    # step 3: header
    expect(page.get_by_role("heading", name="Products")).to_be_visible()
"""

if not resumed or mode == "bad_then_good":
    for path, code in ((po, page_code), (test, test_code)):
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)

events = [
    {"type": "system", "subtype": "init", "session_id": "sess-1"},
    {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": SNAPSHOT}]}
    ]}},
    {"type": "result", "subtype": "success", "is_error": False, "session_id": "sess-1",
     "total_cost_usd": 0.0123, "result": "done"},
]
for e in events:
    print(json.dumps(e))
