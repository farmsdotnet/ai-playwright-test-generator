"""Output targets: which language + runner the generated Page Object Model test is written in.

v0.1-v0.3 could only emit Python + pytest. v0.4 adds TypeScript + Playwright Test as a second
target, selected with `python cli.py <AC file> --target typescript`.

What is language-specific lives here, and ONLY here:
  - where generated files are written, and what they're called
  - the Playwright method names the prompt tells Claude Code to use (get_by_role vs getByRole)
  - the "write the generated code" instructions (pytest vs @playwright/test)
  - the regexes validator.py uses to pull locators and step comments back out of the code
  - how a generated test is executed ([e]xecute)

What is NOT language-specific, and so is untouched by adding a target: md_parser.py,
testrail_client.py, testrail_adapter.py, the StepManifest schema, the Claude Code invocation and
retry loop, and the grounding logic itself. Grounding checks the four strategy CONCEPTS (role,
label, text, alt text) against the accessibility-tree snapshot - the snapshot doesn't care whether
the code that will use the locator is Python or TypeScript.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocatorPatterns:
    """Compiled regexes validator.py runs over generated code. Group conventions are the same for
    every target so validator.py can stay language-agnostic:
      groundable    -> group 1: strategy name as written, remaining groups: first string arg
      role_name     -> any group: the `name` value passed alongside a role
      test_id       -> any group: the value
      raw_locator   -> any group: the selector string
      risky_attr    -> group 1: strategy name as written, remaining groups: the value
      selector_api  -> group 1: the method called with a raw selector string
      step_comment  -> group 1: the step id
    """
    groundable: re.Pattern
    role_name: re.Pattern
    test_id: re.Pattern
    raw_locator: re.Pattern
    risky_attr: re.Pattern
    selector_api: re.Pattern
    step_comment: re.Pattern


@dataclass(frozen=True)
class MethodNames:
    """How each locator strategy is spelled in this target's Playwright binding."""
    role: str
    label: str
    text: str
    alt_text: str
    test_id: str
    placeholder: str
    title: str
    role_name_term: str      # 'filter' (Python keyword arg) vs 'option' (TS options object)
    raw_locator_example: str
    chain_hint: str

    @property
    def allowed(self) -> str:
        return f"{self.role}, {self.label}, {self.text}, or {self.alt_text}"


class Target(ABC):
    name: str
    display_name: str
    methods: MethodNames
    patterns: LocatorPatterns
    step_comment_token: str  # what precedes "step <id>:" in a code comment

    # ---- file layout --------------------------------------------------------------------------
    @abstractmethod
    def generated_root(self, project_root: Path, settings) -> Path: ...

    @abstractmethod
    def file_paths(self, generated_root: Path, scenario: str) -> tuple[Path, Path, Path]:
        """(manifest_path, page_object_path, test_path)"""

    @abstractmethod
    def ensure_project(self, generated_root: Path) -> None:
        """Write any one-time scaffolding the generated code needs to run. Only writes files
        that are missing - never overwrites something a human has edited."""

    # ---- prompt -------------------------------------------------------------------------------
    @abstractmethod
    def code_writing_instructions(self, page_object_path: str, test_path: str) -> str:
        """The '## Write the generated code' section of the task prompt."""

    # ---- execution ----------------------------------------------------------------------------
    @abstractmethod
    def execute(self, generated_root: Path, test_path: Path, headed: bool = False) -> int:
        """Run one generated test. headed=True shows the browser window (cli.py --headed)."""


# =============================================================================================
# Python + pytest (the original target - behaviour is unchanged from v0.3)
# =============================================================================================

_PY_STR = r"(?:\"([^\"]+)\"|'([^']+)')"


class PythonPytestTarget(Target):
    name = "python"
    display_name = "Python + pytest"
    step_comment_token = "#"

    methods = MethodNames(
        role="`get_by_role`",
        label="`get_by_label`",
        text="`get_by_text`",
        alt_text="`get_by_alt_text`",
        test_id="`get_by_test_id(...)`",
        placeholder="`get_by_placeholder`",
        title="`get_by_title`",
        role_name_term="filter",
        raw_locator_example='`.locator("...")`',
        chain_hint="`.nth()`, `.first()`, or `.last()`",
    )

    patterns = LocatorPatterns(
        groundable=re.compile(r"\.get_by_(role|label|text|alt_text)\(\s*" + _PY_STR),
        role_name=re.compile(
            r"\.get_by_role\(\s*(?:\"[^\"]+\"|'[^']+')\s*,[^)]*?\bname\s*=\s*" + _PY_STR
        ),
        test_id=re.compile(r"\.get_by_test_id\(\s*" + _PY_STR),
        raw_locator=re.compile(r"\.locator\(\s*(?:\"([^\"]*)\"|'([^']*)')"),
        risky_attr=re.compile(r"\.get_by_(placeholder|title)\(\s*" + _PY_STR),
        # Page-level shortcuts that take a raw CSS/XPath/text= selector string instead of a
        # Locator - the same ungroundable escape hatch as .locator("..."), just spelled differently.
        selector_api=re.compile(
            r"\bpage\.(click|dblclick|fill|type|press|check|uncheck|hover|tap|focus|"
            r"select_option|wait_for_selector|query_selector_all|query_selector|"
            r"is_visible|is_hidden|text_content|inner_text|get_attribute)\(\s*[\"']"
        ),
        step_comment=re.compile(r"#\s*step\s+(\d+)", re.IGNORECASE),
    )

    def generated_root(self, project_root: Path, settings) -> Path:
        return project_root / settings.generated_dir

    def file_paths(self, generated_root: Path, scenario: str) -> tuple[Path, Path, Path]:
        return (
            generated_root / f"{scenario}_manifest.json",
            generated_root / "page_objects" / f"{scenario}_page.py",
            generated_root / "tests" / f"test_{scenario}.py",
        )

    def ensure_project(self, generated_root: Path) -> None:
        """`page_objects/` and `tests/` are sibling directories under `generated/`, so a generated
        test's `from page_objects.<x> import <Y>` has nothing to resolve `page_objects` against
        unless `generated/` itself is on sys.path. pytest discovers and loads every conftest.py
        between its rootdir and the test file being run, regardless of package structure or
        import-mode settings, so a conftest.py right here is the standard, version-agnostic fix -
        it just needs to exist once, not be regenerated per scenario."""
        conftest_path = generated_root / "conftest.py"
        if conftest_path.exists():
            return
        conftest_path.write_text(
            "import sys\n"
            "from pathlib import Path\n\n"
            "sys.path.insert(0, str(Path(__file__).parent))\n",
            encoding="utf-8",
        )

    def code_writing_instructions(self, page_object_path: str, test_path: str) -> str:
        # Verbatim v0.3 text - selftests/test_prompts.py asserts the Python prompt is unchanged.
        return f"""## Write the generated code
Follow standard Page Object Model:
- Write the page object(s) to `{page_object_path}`
- Write the pytest test to `{test_path}`, using plain `playwright.sync_api` - the generated test \
must run standalone and must not reference MCP anywhere; MCP is only for your exploration in this \
session, not part of the runtime test.
- A page object must not expose any method the manifest doesn't need.
- The test must implement every step in the manifest, in order, nothing extra. Precede each step \
(or tight logical group of steps) with a comment `# step <id>: <short description>` referencing \
the manifest step_id(s) it implements. That comment can live in the test function itself, or \
inside a page-object method the test calls, whichever is where that step actually happens - e.g. \
a login() method that performs several AC steps should carry each of their step comments \
internally, rather than forcing the test to call one page-object method per step.

When all three files are written, stop - no further explanation needed.
"""

    def execute(self, generated_root: Path, test_path: Path, headed: bool = False) -> int:
        # sys.executable -m pytest, not bare "pytest" - avoids relying on whatever pytest.exe
        # happens to resolve to on PATH, which on Windows can be a stale/broken launcher stub
        # (the same "Fatal error in launcher" class of issue as pip.exe).
        cmd = [sys.executable, "-m", "pytest", str(test_path), "-v"]
        if headed:
            # pytest-playwright's flag. It applies to tests that use its `page` fixture; a test
            # that launches its own browser with sync_playwright() decides headless itself.
            cmd.append("--headed")
        return subprocess.run(cmd).returncode


# =============================================================================================
# TypeScript + Playwright Test (new in v0.4)
# =============================================================================================

# TS string literal: single, double, or a backtick template with no ${} interpolation (an
# interpolated template can't be checked statically, same as a Python variable or f-string).
_TS_STR = r"(?:'([^']+)'|\"([^\"]+)\"|`([^`$]+)`)"

TS_PACKAGE_JSON = """{
  "name": "generated-playwright-ts",
  "version": "1.0.0",
  "private": true,
  "description": "TypeScript Page Object Model tests generated by the AI QA pipeline (cli.py --target typescript)",
  "scripts": {
    "test": "playwright test",
    "test:headed": "playwright test --headed",
    "report": "playwright show-report",
    "typecheck": "tsc --noEmit"
  },
  "devDependencies": {
    "@playwright/test": "^1.56.0",
    "@types/node": "^22.0.0",
    "typescript": "~5.9.3"
  }
}
"""

TS_PLAYWRIGHT_CONFIG = """import { defineConfig, devices } from '@playwright/test';

// Generated once by the AI QA pipeline; safe to edit - cli.py never overwrites this file.
export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
"""

TS_TSCONFIG = """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "moduleResolution": "node",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "noEmit": true,
    "types": ["node"]
  },
  "include": ["pageObjects/**/*.ts", "tests/**/*.ts", "playwright.config.ts"]
}
"""

TS_GITIGNORE = """node_modules/
test-results/
playwright-report/
blob-report/
"""


def node_command(*args: str) -> list[str]:
    """npm/npx are installed as .cmd batch scripts on Windows, which subprocess can't launch
    directly - same issue (and same `cmd /c` fix) as the npx entry in .mcp.json."""
    if os.name == "nt":
        return ["cmd", "/c", *args]
    return list(args)


class TypeScriptPlaywrightTarget(Target):
    name = "typescript"
    display_name = "TypeScript + Playwright Test"
    step_comment_token = "//"

    methods = MethodNames(
        role="`getByRole`",
        label="`getByLabel`",
        text="`getByText`",
        alt_text="`getByAltText`",
        test_id="`getByTestId(...)`",
        placeholder="`getByPlaceholder`",
        title="`getByTitle`",
        role_name_term="option",
        raw_locator_example="`.locator('...')`",
        chain_hint="`.nth()`, `.first()`, or `.last()`",
    )

    patterns = LocatorPatterns(
        groundable=re.compile(r"\.getBy(Role|Label|Text|AltText)\(\s*" + _TS_STR),
        role_name=re.compile(
            r"\.getByRole\(\s*(?:'[^']+'|\"[^\"]+\"|`[^`]+`)\s*,\s*\{[^}]*?\bname\s*:\s*"
            + _TS_STR
        ),
        test_id=re.compile(r"\.getByTestId\(\s*" + _TS_STR),
        raw_locator=re.compile(r"\.locator\(\s*(?:'([^']*)'|\"([^\"]*)\"|`([^`]*)`)"),
        risky_attr=re.compile(r"\.getBy(Placeholder|Title)\(\s*" + _TS_STR),
        selector_api=re.compile(
            r"\bpage\.(click|dblclick|fill|type|press|check|uncheck|hover|tap|focus|"
            r"selectOption|waitForSelector|isVisible|isHidden|textContent|innerText|"
            r"getAttribute|\$\$eval|\$eval|\$\$|\$)\(\s*['\"`]"
        ),
        step_comment=re.compile(r"//\s*step\s+(\d+)", re.IGNORECASE),
    )

    def generated_root(self, project_root: Path, settings) -> Path:
        return project_root / settings.generated_ts_dir

    def file_paths(self, generated_root: Path, scenario: str) -> tuple[Path, Path, Path]:
        return (
            generated_root / f"{scenario}_manifest.json",
            generated_root / "pageObjects" / f"{scenario}.page.ts",
            generated_root / "tests" / f"{scenario}.spec.ts",
        )

    def ensure_project(self, generated_root: Path) -> None:
        generated_root.mkdir(parents=True, exist_ok=True)
        for filename, content in (
            ("package.json", TS_PACKAGE_JSON),
            ("playwright.config.ts", TS_PLAYWRIGHT_CONFIG),
            ("tsconfig.json", TS_TSCONFIG),
            (".gitignore", TS_GITIGNORE),
        ):
            path = generated_root / filename
            if not path.exists():
                path.write_text(content, encoding="utf-8")

    @staticmethod
    def import_specifier(page_object_path: str, test_path: str) -> str:
        """Relative module path the spec should import the page object from - computed here so
        Claude Code doesn't have to guess it, and always with forward slashes (Windows paths would
        otherwise produce '..\\pageObjects\\x.page', which isn't a valid TS import)."""
        rel = os.path.relpath(page_object_path, os.path.dirname(test_path)).replace("\\", "/")
        if rel.endswith(".ts"):
            rel = rel[:-3]
        if not rel.startswith("."):
            rel = "./" + rel
        return rel

    def code_writing_instructions(self, page_object_path: str, test_path: str) -> str:
        spec = self.import_specifier(page_object_path, test_path)
        return f"""## Write the generated code
Follow standard Page Object Model, in TypeScript with Playwright Test (`@playwright/test`):
- Write the page object(s) to `{page_object_path}` as exported classes that take a `Page` in \
their constructor (`import {{ Page, Locator }} from '@playwright/test';`). Every method that \
touches the page is `async` and awaits each Playwright call.
- Write the test to `{test_path}` as a Playwright Test spec: \
`import {{ test, expect }} from '@playwright/test';`, a single `test(...)` using the built-in \
`{{ page }}` fixture, and the page object(s) imported with exactly \
`import {{ ... }} from '{spec}';` (no `.ts` extension). Put the base URL in a `const` in the spec \
and navigate to it explicitly - don't rely on `baseURL` from the config. The spec must run \
standalone under `npx playwright test` and must not reference MCP anywhere; MCP is only for your \
exploration in this session, not part of the runtime test.
- Use web-first assertions only (`await expect(locator).toBeVisible()`, `toHaveText()`, \
`toHaveValue()`, `toHaveCount()`, `await expect(page).toHaveURL()`) - never `waitForTimeout` or a \
fixed sleep. Also don't use page-level selector shortcuts such as `page.click('#id')`, \
`page.fill('...')` or `page.$('...')` - they take a raw selector string, so they're banned for the \
same reason as `.locator('...')`.
- Do not create or edit `package.json`, `playwright.config.ts` or `tsconfig.json` - the project \
scaffold already exists.
- A page object must not expose any method the manifest doesn't need.
- The test must implement every step in the manifest, in order, nothing extra. Precede each step \
(or tight logical group of steps) with a comment `// step <id>: <short description>` referencing \
the manifest step_id(s) it implements. That comment can live in the test itself, or inside a \
page-object method the test calls, whichever is where that step actually happens - e.g. a \
login() method that performs several AC steps should carry each of their step comments \
internally, rather than forcing the test to call one page-object method per step.

When all three files are written, stop - no further explanation needed.
"""

    def execute(self, generated_root: Path, test_path: Path, headed: bool = False) -> int:
        if shutil.which("npx") is None:
            print("Couldn't find 'npx' on PATH - install Node.js 18+ to run TypeScript tests.")
            return 1
        if not (generated_root / "node_modules" / "@playwright" / "test").exists():
            print(f"First TypeScript run - installing dependencies in {generated_root} ...")
            install = subprocess.run(node_command("npm", "install"), cwd=generated_root)
            if install.returncode != 0:
                print("npm install failed - see the output above.")
                return install.returncode
            browsers = subprocess.run(
                node_command("npx", "playwright", "install", "chromium"), cwd=generated_root
            )
            if browsers.returncode != 0:
                print("Installing the Chromium browser for Playwright failed - see above.")
                return browsers.returncode
        spec = os.path.relpath(test_path, generated_root).replace("\\", "/")
        args = ["npx", "playwright", "test", spec]
        if headed:
            # overrides `headless: true` in playwright.config.ts for this run only
            args.append("--headed")
        return subprocess.run(node_command(*args), cwd=generated_root).returncode


# =============================================================================================

TARGETS: dict[str, Target] = {
    "python": PythonPytestTarget(),
    "typescript": TypeScriptPlaywrightTarget(),
}
ALIASES = {"py": "python", "pytest": "python", "ts": "typescript"}


def get_target(name: str) -> Target:
    key = ALIASES.get(name.strip().lower(), name.strip().lower())
    if key not in TARGETS:
        raise ValueError(f"Unknown target '{name}'. Choose one of: {', '.join(TARGETS)}")
    return TARGETS[key]
