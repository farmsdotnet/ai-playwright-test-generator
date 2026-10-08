"""End-to-end run of `python cli.py <AC file> --target ...` with Claude Code swapped for
selftests/fake_claude.py. Proves the whole orchestration - AC parsing, target paths, scaffold,
prompt, stream-json parsing, validation, retry via --resume, [c]lose - for both targets, without a
Claude login or network access."""
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="fake `claude` relies on a POSIX shebang; the logic under test is OS-neutral"
)

AC = """Acceptance Criteria:
- Navigate to https://www.saucedemo.com
- Click the Login button.
- Assert the page header displays "Products".
"""


@pytest.fixture
def workspace(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    shutil.copy(Path(__file__).parent / "fake_claude.py", fake)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "login_AC.md").write_text(AC, encoding="utf-8")
    return tmp_path


def run_cli(workspace, *args, mode="good"):
    env = dict(os.environ, PATH=f"{workspace / 'bin'}{os.pathsep}{os.environ['PATH']}",
               FAKE_CLAUDE_MODE=mode)
    return subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "cli.py"), "login_AC.md", *args],
        cwd=workspace, env=env, input="c\n", capture_output=True, text=True, timeout=60,
    )


def test_typescript_target_end_to_end(workspace):
    proc = run_cli(workspace, "--target", "typescript")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Target: TypeScript + Playwright Test" in proc.stdout
    assert "validation: PASSED" in proc.stdout

    root = workspace / "generated_ts"
    assert (root / "login_manifest.json").exists()
    spec = (root / "tests" / "login.spec.ts").read_text()
    assert "import { LoginPage } from '../pageObjects/login.page';" in spec
    assert (root / "pageObjects" / "login.page.ts").exists()
    for scaffold in ("package.json", "playwright.config.ts", "tsconfig.json", ".gitignore"):
        assert (root / scaffold).exists()
    assert not (workspace / "generated").exists(), "a TypeScript run must not touch generated/"


def test_python_target_is_still_the_default(workspace):
    proc = run_cli(workspace)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Target: Python + pytest" in proc.stdout
    assert "validation: PASSED" in proc.stdout
    root = workspace / "generated"
    assert (root / "tests" / "test_login.py").exists()
    assert (root / "page_objects" / "login_page.py").exists()
    assert (root / "conftest.py").exists()
    assert not (workspace / "generated_ts").exists()


@pytest.mark.parametrize("target", ["python", "typescript"])
def test_hallucinated_locator_is_caught_then_fixed_on_retry(workspace, target):
    proc = run_cli(workspace, "--target", target, mode="bad_then_good")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "attempt 1/3" in proc.stdout and "attempt 2/3" in proc.stdout
    assert "Role locator name 'Log in now'" in proc.stdout
    assert proc.stdout.rstrip().endswith("Closing.")
    assert proc.stdout.count("validation: PASSED") == 1


def test_unknown_target_is_rejected_by_argparse(workspace):
    proc = run_cli(workspace, "--target", "java")
    assert proc.returncode == 2
    assert "invalid choice: 'java'" in proc.stderr
