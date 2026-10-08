import json

import pytest

from config import load_settings
from targets import TypeScriptPlaywrightTarget, get_target


@pytest.mark.parametrize("alias,expected", [
    ("python", "python"), ("py", "python"), ("PyTest", "python"),
    ("typescript", "typescript"), ("ts", "typescript"), (" TS ", "typescript"),
])
def test_aliases(alias, expected):
    assert get_target(alias).name == expected


def test_unknown_target_is_rejected():
    with pytest.raises(ValueError, match="Choose one of: python, typescript"):
        get_target("java")


def test_python_paths_are_the_v03_paths(tmp_path):
    t = get_target("python")
    root = t.generated_root(tmp_path, load_settings())
    assert t.file_paths(root, "login") == (
        tmp_path / "generated" / "login_manifest.json",
        tmp_path / "generated" / "page_objects" / "login_page.py",
        tmp_path / "generated" / "tests" / "test_login.py",
    )


def test_typescript_paths(tmp_path):
    t = get_target("typescript")
    root = t.generated_root(tmp_path, load_settings())
    assert t.file_paths(root, "login") == (
        tmp_path / "generated_ts" / "login_manifest.json",
        tmp_path / "generated_ts" / "pageObjects" / "login.page.ts",
        tmp_path / "generated_ts" / "tests" / "login.spec.ts",
    )


@pytest.mark.parametrize("po,test,expected", [
    ("generated_ts/pageObjects/login.page.ts", "generated_ts/tests/login.spec.ts", "../pageObjects/login.page"),
    (r"C:\proj\generated_ts\pageObjects\login.page.ts", r"C:\proj\generated_ts\tests\login.spec.ts", "../pageObjects/login.page"),
    ("generated_ts/tests/login.page.ts", "generated_ts/tests/login.spec.ts", "./login.page"),
])
def test_import_specifier_is_always_a_valid_posix_relative_import(po, test, expected):
    if "\\" in po and __import__("os").name != "nt":
        po, test = po.replace("\\", "/"), test.replace("\\", "/")
    assert TypeScriptPlaywrightTarget.import_specifier(po, test) == expected


def test_typescript_scaffold_is_written_once_and_never_overwritten(tmp_path):
    t = get_target("typescript")
    t.ensure_project(tmp_path)
    for name in ("package.json", "playwright.config.ts", "tsconfig.json", ".gitignore"):
        assert (tmp_path / name).exists(), name
    pkg = json.loads((tmp_path / "package.json").read_text())
    assert "@playwright/test" in pkg["devDependencies"]

    (tmp_path / "playwright.config.ts").write_text("// edited by a human")
    t.ensure_project(tmp_path)
    assert (tmp_path / "playwright.config.ts").read_text() == "// edited by a human"


def test_python_scaffold_is_the_v03_conftest(tmp_path):
    get_target("python").ensure_project(tmp_path)
    assert (tmp_path / "conftest.py").read_text() == (
        "import sys\nfrom pathlib import Path\n\nsys.path.insert(0, str(Path(__file__).parent))\n"
    )


class _Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        return type("Done", (), {"returncode": 0})()


@pytest.mark.parametrize("headed", [False, True])
def test_typescript_execute_passes_headed_through(tmp_path, monkeypatch, headed):
    import targets
    (tmp_path / "node_modules" / "@playwright" / "test").mkdir(parents=True)
    rec = _Recorder()
    monkeypatch.setattr(targets.shutil, "which", lambda _: "/usr/bin/npx")
    monkeypatch.setattr(targets.subprocess, "run", rec)
    rc = get_target("typescript").execute(tmp_path, tmp_path / "tests" / "login.spec.ts", headed=headed)
    assert rc == 0
    cmd = rec.calls[-1]
    assert cmd[-2:] == (["tests/login.spec.ts", "--headed"] if headed else ["test", "tests/login.spec.ts"])


@pytest.mark.parametrize("headed", [False, True])
def test_python_execute_passes_headed_through(tmp_path, monkeypatch, headed):
    import targets
    rec = _Recorder()
    monkeypatch.setattr(targets.subprocess, "run", rec)
    get_target("python").execute(tmp_path, tmp_path / "tests" / "test_login.py", headed=headed)
    cmd = rec.calls[-1]
    assert ("--headed" in cmd) is headed
    assert cmd[1:3] == ["-m", "pytest"]
