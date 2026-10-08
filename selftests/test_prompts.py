"""The Python prompts must be exactly what v0.3 produced (that path is proven end to end against
saucedemo), and the TypeScript prompts must speak TypeScript throughout."""
from pathlib import Path

import pytest

from prompts.claude_code_task_prompt import (
    build_retry_prompt,
    build_task_prompt,
    build_task_prompt_from_manifest,
)
from targets import get_target

GOLDEN = Path(__file__).parent / "golden"
ARGS = dict(
    base_url="https://www.saucedemo.com",
    ac_lines=["Navigate to https://www.saucedemo.com", "Click the Login button."],
    manifest_path="generated/login_manifest.json",
    page_object_path="generated/page_objects/login_page.py",
    test_path="generated/tests/test_login.py",
)


def golden(name: str) -> str:
    return (GOLDEN / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("target", [None, get_target("python")], ids=["default", "python"])
def test_python_prompts_are_unchanged_from_v03(target):
    assert build_task_prompt(**ARGS, target=target) == golden("v03_task_prompt.txt")
    assert build_task_prompt(**ARGS, feedback="FAILED:\n- x", target=target) == golden(
        "v03_task_prompt_feedback.txt"
    )
    assert build_task_prompt_from_manifest(
        ARGS["manifest_path"], ARGS["page_object_path"], ARGS["test_path"], target=target
    ) == golden("v03_manifest_prompt.txt")
    assert build_retry_prompt(
        "FAILED:\n- x", ARGS["manifest_path"], ARGS["page_object_path"], ARGS["test_path"],
        target=target,
    ) == golden("v03_retry_prompt.txt")


TS_ARGS = dict(
    ARGS,
    manifest_path="generated_ts/login_manifest.json",
    page_object_path="generated_ts/pageObjects/login.page.ts",
    test_path="generated_ts/tests/login.spec.ts",
)
PY_ONLY_TERMS = ["get_by_role", "get_by_label", "get_by_text", "get_by_alt_text", "get_by_test_id",
                 "get_by_placeholder", "get_by_title", "pytest", "sync_api", "`# step"]


@pytest.mark.parametrize("builder", ["task", "manifest", "retry"])
def test_typescript_prompts_use_typescript_only(builder):
    ts = get_target("typescript")
    if builder == "task":
        prompt = build_task_prompt(**TS_ARGS, target=ts)
    elif builder == "manifest":
        prompt = build_task_prompt_from_manifest(
            TS_ARGS["manifest_path"], TS_ARGS["page_object_path"], TS_ARGS["test_path"], target=ts
        )
    else:
        prompt = build_retry_prompt(
            "FAILED", TS_ARGS["manifest_path"], TS_ARGS["page_object_path"], TS_ARGS["test_path"],
            target=ts,
        )
    for term in PY_ONLY_TERMS:
        assert term not in prompt, f"Python-only term {term!r} leaked into the TypeScript prompt"
    for term in ("getByRole", "getByLabel", "getByText", "getByAltText", "getByTestId"):
        assert term in prompt
    assert "// step <id>" in prompt


def test_typescript_task_prompt_gives_exact_import_and_runner():
    prompt = build_task_prompt(**TS_ARGS, target=get_target("typescript"))
    assert "from '../pageObjects/login.page'" in prompt
    assert "@playwright/test" in prompt
    assert "npx playwright test" in prompt
    assert "`name` option" in prompt
    # the manifest step (Step 1) is language-neutral and identical for both targets
    py_step1 = build_task_prompt(**ARGS).split("## Ground every locator")[0]
    ts_step1 = prompt.split("## Ground every locator")[0]
    assert py_step1.replace("generated/login_manifest.json", "generated_ts/login_manifest.json") == ts_step1
