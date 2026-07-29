"""Builds the task prompts handed to `claude -p`. Under the old architecture this was two separate
Claude API calls (step_planner.py for AC -> manifest, test_generator.py for the MCP-grounded
generation). Claude Code does both in a single session now - it reasons through the manifest,
drives Playwright MCP itself, and writes all three output files directly via its own file tools.

Two entry points build the FIRST turn's prompt, depending on where the manifest comes from:
- build_task_prompt: AC.md source - Claude Code builds the manifest itself (Step 1 below), then
  grounds locators and generates code (Steps 2-3).
- build_task_prompt_from_manifest: TestRail (Steps-template) source - the manifest is already
  written to disk deterministically by testrail_adapter.py before this is ever called, so this
  skips straight to Steps 2-3.

Both share _grounding_and_generation_instructions() for those steps, so locator-strategy rules
only need updating in one place - the AC.md and TestRail paths drifting out of sync with each
other is exactly the kind of stale-copy bug this project hit earlier with duplicated logic.
build_retry_prompt (used by both paths on a validation-failure retry turn) repeats the same rules
in its own words for the same reason - it's a follow-up message, not a rebuild of the main prompt,
so it can't just call the same helper without restating context Claude Code already has.
"""
from __future__ import annotations


def _grounding_and_generation_instructions(page_object_path: str, test_path: str) -> str:
    return f"""## Ground every locator in the real page
Use the Playwright MCP tools to navigate to the base URL and capture an accessibility-tree \
snapshot before writing any locators. If a later step requires interacting with the page first \
to reach elements it references, use the appropriate browser tools to get there, then capture a \
fresh snapshot before writing locators for that part of the page.

An accessibility-tree snapshot shows an element's role and accessible name - it does NOT show \
`id`, `class`, or `data-testid` HTML attributes, and has no concept of CSS/XPath structural \
selectors (`:nth-child`, tag hierarchy, etc.). So `get_by_test_id(...)` and ANY raw \
`.locator("...")` call with a CSS or XPath selector string are banned outright, regardless of what \
they target - not just obvious cases like `#some-id` or `[data-testid=...]`, but also class \
selectors, structural selectors, anything. `get_by_placeholder` and `get_by_title` are also \
banned: that text only becomes the accessible name when nothing else (a `<label>`, `aria-label`, \
etc.) already claims it, so it can be invisible in the snapshot even when it looks like it should \
be there - not reliably verifiable either way. Use only `get_by_role` (with its `name` filter), \
`get_by_label`, `get_by_text`, or `get_by_alt_text` - all of which correspond directly to what a \
snapshot actually shows. If you need to disambiguate one of several matching elements, chain \
`.nth()`, `.first()`, or `.last()` onto one of those four - that narrows an already-grounded \
locator, it doesn't introduce a new ungroundable one. Every value you put into one of the four \
methods must match an element you actually observed in a snapshot during this session - never \
invent or infer one.

## Write the generated code
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


def build_task_prompt(
    base_url: str,
    ac_lines: list[str],
    manifest_path: str,
    page_object_path: str,
    test_path: str,
    feedback: str | None = None,
) -> str:
    numbered_ac = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(ac_lines))

    feedback_block = ""
    if feedback:
        feedback_block = (
            "\n## Previous attempt failed validation - fix these issues\n"
            f"{feedback}\n"
        )

    return f"""You are a senior SDET. Complete this task end-to-end using the tools available to \
you (the Playwright MCP browser tools, plus your own file read/write tools). Do not ask for \
confirmation or pause partway through - finish the whole task, then stop.

## Acceptance Criteria (in execution order)
Base URL: {base_url}

{numbered_ac}
{feedback_block}
## Step 1 - Build the step manifest
Convert the AC above into an ordered manifest of test steps: exactly one step per AC line above, \
in the same order - no merging, no skipping, no steps added beyond what's stated. For each step, \
decide:
- step_type: "action" or "assertion"
- description: the AC line, lightly cleaned up
- target_element_description: plain-language description of the UI element this step acts on or \
checks, or null
- expected_result: what should be true after this step, or null for a pure action

Write this manifest to `{manifest_path}` as JSON matching exactly this schema:
{{
  "scenario_name": "short_snake_case_name",
  "base_url": "{base_url}",
  "steps": [
    {{"step_id": 1, "step_type": "action", "description": "...",
      "target_element_description": null, "expected_result": null}}
  ]
}}

""" + _grounding_and_generation_instructions(page_object_path, test_path)


def build_task_prompt_from_manifest(
    manifest_path: str,
    page_object_path: str,
    test_path: str,
) -> str:
    """First-turn prompt for the TestRail path: the manifest already exists on disk, written
    deterministically by testrail_adapter.py from a human-authored TestRail case - not something
    Claude Code needs to infer or is allowed to second-guess."""
    return f"""You are a senior SDET. Complete this task end-to-end using the tools available to \
you (the Playwright MCP browser tools, plus your own file read/write tools). Do not ask for \
confirmation or pause partway through - finish the whole task, then stop.

## Step manifest
A step manifest already exists at `{manifest_path}` - read it now. It was written by a human, via \
a TestRail test case, not by you - treat it as the source of truth for this run exactly as if \
you'd built it yourself from Acceptance Criteria text. Do not modify it, reorder its steps, or \
add/remove steps.

""" + _grounding_and_generation_instructions(page_object_path, test_path)


def build_retry_prompt(feedback: str, manifest_path: str, page_object_path: str, test_path: str) -> str:
    """Follow-up prompt for a `claude --resume` retry turn. Claude Code already has the original
    task and its own file-write history in this session, so this doesn't restate the whole task -
    just what failed and where to fix it. Shared by both the AC.md and TestRail paths - the retry
    concern (bad locator, drifted step) is identical regardless of where the manifest came from."""
    return f"""The test you just wrote failed an automated validation check. Fix it in place.

## Validation failures
{feedback}

Re-check `{page_object_path}` and `{test_path}` against the manifest at `{manifest_path}`. If a \
locator was flagged as ungrounded, re-navigate and capture a fresh Playwright MCP snapshot before \
correcting it - don't guess a replacement, and don't fall back to get_by_test_id, get_by_placeholder, \
get_by_title, or any raw `.locator(...)` call with a CSS/XPath selector string, since none of \
those are reliably verifiable from a snapshot; use get_by_role, get_by_label, get_by_text, or \
get_by_alt_text instead. If a step was flagged as missing or drifted, fix the `# step <id>` \
comments and the step coverage itself, not just the wording. Update the files directly, then stop \
- no further explanation needed.
"""
