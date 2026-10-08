"""Non-LLM validation gate. This is what actually enforces the non-negotiables:
every locator must be traceable to a real accessibility-tree snapshot captured
during generation, and every generated test step must map 1:1 to a step in the
manifest - no drift, no gaps.

v0.4: the gate is language-agnostic. The regexes that pull locators and step comments out of the
generated code come from the target (targets.py) - `get_by_role("button", name="Login")` in
Python, `getByRole('button', { name: 'Login' })` in TypeScript - but every rule below is the same
rule for both, checked against the same snapshot text. Why each locator kind is allowed or banned
is documented once, here, rather than per language.

- get_by_test_id / getByTestId checks an HTML attribute an accessibility-tree snapshot never
  exposes (it shows role + accessible name only) - so it can never be honestly grounded, and a
  naive substring match against snapshot text can pass by coincidence when a guessed value merely
  resembles the accessible name. Seen in practice: get_by_test_id("username") passed because
  "username" also showed up as the accessible name, while the real attribute was id="user-name".
- Raw .locator() calls with a CSS/XPath string are banned outright, not just ones matching a
  specific list of risky attributes. A blocklist of attribute patterns can never be complete - a
  class selector (".btn-primary") or a structural one ("div > span:nth-child(2)") is exactly as
  ungroundable from a snapshot as an id selector. Chaining .nth()/.first()/.last() onto an
  already-grounded locator is unaffected - that narrows a real locator, it doesn't introduce a
  new ungroundable one.
- Page-level selector shortcuts (page.click("#id"), page.fill(...), page.query_selector(...),
  page.$(...)) are the same escape hatch as .locator("...") spelled differently - banned too (v0.4).
- get_by_placeholder / get_by_title: placeholder/title text only becomes the ARIA accessible name
  when nothing higher in the accessible-name computation (a <label>, aria-label, etc.) already
  claims it, so it can be absent from the snapshot even when it looks like it should be there.
  Banned outright rather than trusted case-by-case.
- get_by_role's `name` is grounded as well as the role (v0.4). Before this, only the first string
  argument - the role itself, e.g. "button" - was checked, so get_by_role("button", name="Logn")
  passed because "button" was in the snapshot even though no element was named "Logn".
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models import GeneratedTest, StepManifest
from targets import Target, get_target

# Kept for anything importing these names from v0.3 - they are the Python target's patterns.
_PY = get_target("python").patterns
GROUNDABLE_LOCATOR_PATTERN = _PY.groundable
TEST_ID_LOCATOR_PATTERN = _PY.test_id
RAW_LOCATOR_CALL_PATTERN = _PY.raw_locator
RISKY_ATTR_LOCATOR_PATTERN = _PY.risky_attr
STEP_COMMENT_PATTERN = _PY.step_comment


@dataclass
class ValidationResult:
    passed: bool
    issues: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.passed:
            return "PASSED"
        return "FAILED:\n- " + "\n- ".join(self.issues)


def _extract_snapshot_text(stream_events: list[dict]) -> str:
    """Pull every MCP tool_result out of Claude Code's stream-json events, so we have real page
    data - snapshots, but also nav/click confirmations - to check generated locators against.

    Walks each event recursively rather than assuming one exact nesting path: Claude Code's
    stream-json schema isn't fully published, and the tool_result blocks are nested inside
    assistant/user message events in a shape that can shift between versions. A defensive walk
    finds them wherever they land instead of failing silently on a schema mismatch.
    """
    chunks: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "tool_result":
                content = node.get("content")
                if isinstance(content, str):
                    chunks.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and "text" in block:
                            chunks.append(str(block["text"]))
                        else:
                            chunks.append(str(block))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for event in stream_events:
        walk(event)

    return "\n".join(chunks)


def _first_group(match) -> str:
    return next((g for g in match.groups() if g), "")


def _value_after_kind(match) -> str:
    """For patterns whose group 1 is the strategy name: the first non-empty group after it."""
    return next((g for g in match.groups()[1:] if g), "")


def _kind(raw: str) -> str:
    """'Role' / 'AltText' / 'alt_text' -> 'role' / 'alt_text', for consistent messages."""
    return {"alttext": "alt_text"}.get(raw.lower(), raw.lower())


def validate(
    manifest: StepManifest, generated: GeneratedTest, target: Target | None = None
) -> ValidationResult:
    t = target or get_target("python")
    p, m = t.patterns, t.methods
    allowed = m.allowed.replace("`", "")
    issues: list[str] = []
    snapshot_text = _extract_snapshot_text(generated.stream_events)
    combined_code = generated.page_object_code + "\n" + generated.test_code

    # 1a. Groundable locators (role/label/text/alt_text) - these correspond to what an
    #     accessibility snapshot actually shows, so a substring check against captured snapshot
    #     text is a legitimate grounding check.
    for match in p.groundable.finditer(combined_code):
        kind = _kind(match.group(1))
        value = _value_after_kind(match)
        if value and value not in snapshot_text:
            issues.append(
                f"Locator value '{value}' ({kind} locator) was not found in any captured MCP "
                f"tool result - likely hallucinated."
            )
    for match in p.role_name.finditer(combined_code):
        name = _first_group(match)
        if name and name not in snapshot_text:
            issues.append(
                f"Role locator name '{name}' was not found in any captured MCP tool result - "
                "likely hallucinated."
            )

    # 1b. Test-id locators, raw selector strings and page-level selector shortcuts are banned
    #     entirely regardless of what they target - an allowlist of the four groundable methods
    #     is complete by construction; a blocklist of specific "risky" selectors never can be.
    for match in p.test_id.finditer(combined_code):
        issues.append(
            f"{m.test_id.strip('`').replace('...', repr(_first_group(match)))} is not verifiable "
            f"from an accessibility-tree snapshot - use {allowed} instead."
        )
    for match in p.raw_locator.finditer(combined_code):
        issues.append(
            f"locator('{_first_group(match)}') is a raw CSS/XPath selector, which is not "
            "verifiable from an accessibility-tree snapshot regardless of what it targets - use "
            f"{allowed} instead (chain .nth()/.first()/.last() onto one of those if you need to "
            "disambiguate a repeated element)."
        )
    for match in p.selector_api.finditer(combined_code):
        issues.append(
            f"page.{match.group(1)}(...) is called with a raw selector string, which is not "
            f"verifiable from an accessibility-tree snapshot - build a locator with {allowed} "
            "and act on that instead."
        )

    # 1c. Placeholder / title - only sometimes visible in a snapshot, depending on ARIA
    #     accessible-name precedence, so a pass here can't be trusted either way.
    for match in p.risky_attr.finditer(combined_code):
        kind, value = _kind(match.group(1)), _value_after_kind(match)
        issues.append(
            f"{kind} locator ('{value}') only sometimes appears in an accessibility snapshot "
            "(depends on whether a label/aria-label already claims the accessible name) - not "
            f"reliably verifiable, so it's banned - use {allowed} instead."
        )

    # 2. Step coverage - every manifest step_id must be referenced, and nothing extra. Comments can
    #    live in the test file OR inside a page-object method (e.g. a login() convenience method
    #    legitimately bundles the steps for entering credentials and clicking submit) - so this
    #    scans both files combined rather than requiring every step to appear in the flat test body.
    referenced_ids = {int(m_.group(1)) for m_ in p.step_comment.finditer(combined_code)}
    manifest_ids = {s.step_id for s in manifest.steps}
    missing = manifest_ids - referenced_ids
    extra = referenced_ids - manifest_ids
    if missing:
        issues.append(
            f"Steps missing from generated test: {sorted(missing)} (expected "
            f"'{t.step_comment_token} step <id>:' comments)"
        )
    if extra:
        issues.append(f"Generated test references step ids not in the manifest (drift): {sorted(extra)}")

    return ValidationResult(passed=not issues, issues=issues)
