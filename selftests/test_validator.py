"""The same grounding and coverage rules, enforced on Python and TypeScript output alike."""
from pathlib import Path

import pytest

from config import load_settings

from models import GeneratedTest, Step, StepManifest
from targets import get_target
from validator import validate

SNAPSHOT = (
    '- textbox "Username" [ref=e1]\n'
    '- textbox "Password" [ref=e2]\n'
    '- button "Login" [ref=e3]\n'
    '- heading "Products" [level=1]\n'
    '- img "Sauce Labs Backpack"\n'
    '- combobox "Sort" [ref=e9]\n'
)
EVENTS = [{"type": "user", "message": {"role": "user", "content": [
    {"type": "tool_result", "tool_use_id": "t1", "content": [{"type": "text", "text": SNAPSHOT}]}
]}}]
MANIFEST = StepManifest("login", "https://www.saucedemo.com", [
    Step(1, "action", "Navigate"),
    Step(2, "action", "Enter username"),
    Step(3, "action", "Click Login"),
    Step(4, "assertion", "Header shows Products"),
])

PY_PAGE = '''from playwright.sync_api import Page

class LoginPage:
    def __init__(self, page: Page):
        self.page = page

    def login(self, user):
        # step 2: enter username
        self.page.get_by_role("textbox", name="Username").fill(user)
        # step 3: click login
        self.page.get_by_role("button", name="Login").click()
'''
PY_TEST = '''def test_login(page):
    # step 1: navigate
    page.goto("https://www.saucedemo.com")
    LoginPage(page).login("standard_user")
    # step 4: header
    expect(page.get_by_text("Products")).to_be_visible()
'''

TS_PAGE = """import { Page } from '@playwright/test';

export class LoginPage {
  constructor(private readonly page: Page) {}

  async login(user: string): Promise<void> {
    // step 2: enter username
    await this.page.getByRole('textbox', { name: 'Username' }).fill(user);
    // step 3: click login
    await this.page.getByRole('button', { name: `Login`, exact: true }).click();
  }
}
"""
TS_TEST = """import { test, expect } from '@playwright/test';
import { LoginPage } from '../pageObjects/login.page';

const BASE_URL = 'https://www.saucedemo.com';

test('login', async ({ page }) => {
  // step 1: navigate
  await page.goto(BASE_URL);
  await new LoginPage(page).login('standard_user');
  // step 4: header
  await expect(page.getByText("Products")).toBeVisible();
  await expect(page.getByAltText('Sauce Labs Backpack').first()).toBeVisible();
});
"""

CASES = {
    "python": (PY_PAGE, PY_TEST),
    "typescript": (TS_PAGE, TS_TEST),
}

# (description, python replacement, typescript replacement, expected message fragment)
# each replaces the Login click line with something that must fail
BAD_LOGIN_CLICK = [
    ("hallucinated role name",
     'self.page.get_by_role("button", name="Sign in").click()',
     "await this.page.getByRole('button', { name: 'Sign in' }).click();",
     "Role locator name 'Sign in'"),
    ("hallucinated text",
     'self.page.get_by_text("Sign in").click()',
     "await this.page.getByText('Sign in').click();",
     "'Sign in' (text locator)"),
    ("test id",
     'self.page.get_by_test_id("login-button").click()',
     "await this.page.getByTestId('login-button').click();",
     "('login-button') is not verifiable"),
    ("raw css locator",
     'self.page.locator("#login-button").click()',
     "await this.page.locator('#login-button').click();",
     "raw CSS/XPath selector"),
    ("page-level selector shortcut",
     'self.page.click("#login-button")',
     "await this.page.click('#login-button');",
     "page.click(...) is called with a raw selector string"),
    ("query selector",
     'self.page.query_selector("#login-button").click()',
     "await (await this.page.$('#login-button'))!.click();",
     "with a raw selector string"),
    ("placeholder",
     'self.page.get_by_placeholder("Login").click()',
     "await this.page.getByPlaceholder('Login').click();",
     "placeholder locator"),
    ("title",
     'self.page.get_by_title("Login").click()',
     "await this.page.getByTitle('Login').click();",
     "title locator"),
]
GOOD_LOGIN_CLICK = {
    "python": 'self.page.get_by_role("button", name="Login").click()',
    "typescript": "await this.page.getByRole('button', { name: `Login`, exact: true }).click();",
}


def _gen(target_name, page_code, test_code):
    t = get_target(target_name)
    _, po, tp = t.file_paths(t.generated_root(Path("."), load_settings()), "login")
    return GeneratedTest(str(po), page_code, str(tp), test_code, EVENTS)


@pytest.mark.parametrize("target_name", ["python", "typescript"])
def test_happy_path_passes(target_name):
    page, test = CASES[target_name]
    result = validate(MANIFEST, _gen(target_name, page, test), target=get_target(target_name))
    assert result.passed, result.summary()


def test_python_is_the_default_target():
    page, test = CASES["python"]
    assert validate(MANIFEST, _gen("python", page, test)).passed


@pytest.mark.parametrize("target_name", ["python", "typescript"])
@pytest.mark.parametrize("desc,py_bad,ts_bad,fragment", BAD_LOGIN_CLICK, ids=[c[0] for c in BAD_LOGIN_CLICK])
def test_bad_locators_fail_in_both_languages(target_name, desc, py_bad, ts_bad, fragment):
    page, test = CASES[target_name]
    bad = py_bad if target_name == "python" else ts_bad
    page = page.replace(GOOD_LOGIN_CLICK[target_name], bad)
    assert bad in page
    result = validate(MANIFEST, _gen(target_name, page, test), target=get_target(target_name))
    assert not result.passed, f"{desc} should have failed validation"
    assert fragment in result.summary(), result.summary()


@pytest.mark.parametrize("target_name", ["python", "typescript"])
def test_missing_and_extra_steps_fail(target_name):
    page, test = CASES[target_name]
    tok = get_target(target_name).step_comment_token
    test = test.replace(f"{tok} step 4: header", f"{tok} step 5: header")
    result = validate(MANIFEST, _gen(target_name, page, test), target=get_target(target_name))
    assert not result.passed
    assert "Steps missing from generated test: [4]" in result.summary()
    assert "(drift): [5]" in result.summary()


def test_python_style_step_comments_do_not_count_in_typescript():
    page = TS_PAGE.replace("// step", "# step")
    result = validate(MANIFEST, _gen("typescript", page, TS_TEST), target=get_target("typescript"))
    assert not result.passed
    assert "Steps missing from generated test: [2, 3]" in result.summary()


def test_typescript_validator_ignores_python_syntax_and_vice_versa():
    """A TS run whose code is actually Python would have zero recognisable locators - the step
    coverage check still holds it to account, and nothing crashes."""
    result = validate(MANIFEST, _gen("typescript", PY_PAGE, PY_TEST), target=get_target("typescript"))
    assert not result.passed
    assert "Steps missing" in result.summary()


def test_nth_first_last_chaining_is_allowed():
    page = TS_PAGE.replace(
        "await this.page.getByRole('textbox', { name: 'Username' }).fill(user);",
        "await this.page.getByRole('textbox').nth(0).fill(user);",
    )
    result = validate(MANIFEST, _gen("typescript", page, TS_TEST), target=get_target("typescript"))
    assert result.passed, result.summary()


def test_interpolated_template_literal_is_not_treated_as_grounded_text():
    """`${name}` can't be checked statically - it's skipped exactly like a Python variable, not
    matched as the literal string '${name}' and flagged as hallucinated."""
    test = TS_TEST.replace(
        "await expect(page.getByText(\"Products\")).toBeVisible();",
        "const header = 'Products';\n  await expect(page.getByText(`${header}`)).toBeVisible();",
    )
    result = validate(MANIFEST, _gen("typescript", TS_PAGE, test), target=get_target("typescript"))
    assert result.passed, result.summary()
