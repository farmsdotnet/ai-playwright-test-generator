"""Non-LLM validation gate. This is what actually enforces the non-negotiables:
every locator must be traceable to a real accessibility-tree snapshot captured
during generation, and every generated test step must map 1:1 to a step in the
manifest - no drift, no gaps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from models import GeneratedTest, StepManifest

GROUNDABLE_LOCATOR_PATTERN = re.compile(
    r"\.get_by_(role|label|text|alt_text)\(\s*(?:\"([^\"]+)\"|'([^']+)')"
)
# get_by_test_id checks an HTML attribute an accessibility-tree snapshot never exposes (it shows
# role + accessible name only) - so it can never be honestly grounded, and a naive substring match
# against snapshot text can pass by coincidence when a guessed value merely resembles the
# accessible name. Seen in practice: get_by_test_id("username") passed because "username" also
# showed up as the accessible name, while the real attribute was id="user-name" - a completely
# different string.
TEST_ID_LOCATOR_PATTERN = re.compile(r"\.get_by_test_id\(\s*(?:\"([^\"]+)\"|'([^']+)')")
# Raw .locator() calls with a CSS/XPath string are banned outright, not just ones matching a
# specific list of risky attributes (id, data-testid, ...). A blocklist of attribute patterns can
# never be complete - a class selector (".btn-primary") or a structural one
# ("div > span:nth-child(2)") is exactly as ungroundable from a snapshot as an id selector, just
# not on whatever list we'd thought to write down. Chaining .nth()/.first()/.last() onto an
# already-grounded get_by_* locator is unaffected - that narrows a real locator, it doesn't
# introduce a new ungroundable one.
RAW_LOCATOR_CALL_PATTERN = re.compile(r"\.locator\(\s*(?:\"([^\"]*)\"|'([^']*)')")
# get_by_placeholder and get_by_title are a subtler version of the same problem: placeholder/title
# text only becomes the ARIA accessible name when nothing higher in the accessible-name-computation
# order (a <label>, aria-label, etc.) already claims it. If a label exists, the placeholder/title
# text never appears in the snapshot at all - so a locator built on it can pass today's substring
# check by the same kind of coincidence that let get_by_test_id("username") through, without ever
# actually being verifiable. Banned outright rather than trusted case-by-case.
RISKY_ATTR_LOCATOR_PATTERN = re.compile(
    r"\.get_by_(placeholder|title)\(\s*(?:\"([^\"]+)\"|'([^']+)')"
)
STEP_COMMENT_PATTERN = re.compile(r"#\s*step\s+(\d+)", re.IGNORECASE)


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


def validate(manifest: StepManifest, generated: GeneratedTest) -> ValidationResult:
    issues: list[str] = []
    snapshot_text = _extract_snapshot_text(generated.stream_events)
    combined_code = generated.page_object_code + "\n" + generated.test_code

    # 1a. Groundable locators (role/label/text/alt_text) - these correspond to what an
    #     accessibility snapshot actually shows, so a substring check against captured snapshot
    #     text is a legitimate grounding check.
    for match in GROUNDABLE_LOCATOR_PATTERN.finditer(combined_code):
        locator_kind = match.group(1)
        locator_value = match.group(2) or match.group(3)
        if locator_value and locator_value not in snapshot_text:
            issues.append(
                f"Locator value '{locator_value}' (get_by_{locator_kind}) was not found in any "
                f"captured MCP tool result - likely hallucinated."
            )

    # 1b. get_by_test_id is banned outright (never groundable, see pattern comment above), and any
    #     raw .locator() with a CSS/XPath string is banned entirely regardless of what it targets -
    #     an allowlist of the four groundable methods is complete by construction; a blocklist of
    #     specific "risky" selector patterns never can be.
    for match in TEST_ID_LOCATOR_PATTERN.finditer(combined_code):
        value = match.group(1) or match.group(2)
        issues.append(
            f"get_by_test_id('{value}') is not verifiable from an accessibility-tree snapshot - "
            "use get_by_role, get_by_label, get_by_text, or get_by_alt_text instead."
        )
    for match in RAW_LOCATOR_CALL_PATTERN.finditer(combined_code):
        selector = match.group(1) or match.group(2)
        issues.append(
            f"locator('{selector}') is a raw CSS/XPath selector, which is not verifiable from an "
            "accessibility-tree snapshot regardless of what it targets - use get_by_role, "
            "get_by_label, get_by_text, or get_by_alt_text instead (chain .nth()/.first()/.last() "
            "onto one of those if you need to disambiguate a repeated element)."
        )

    # 1c. get_by_placeholder / get_by_title - banned for the same reason, see pattern comment
    #     above: only sometimes visible in a snapshot, depending on ARIA accessible-name
    #     precedence, so a pass here can't be trusted either way.
    for match in RISKY_ATTR_LOCATOR_PATTERN.finditer(combined_code):
        kind, value = match.group(1), match.group(2) or match.group(3)
        issues.append(
            f"get_by_{kind}('{value}') only sometimes appears in an accessibility snapshot "
            "(depends on whether a label/aria-label already claims the accessible name) - not "
            "reliably verifiable, so it's banned - use get_by_role, get_by_label, get_by_text, or "
            "get_by_alt_text instead."
        )

    # 2. Step coverage - every manifest step_id must be referenced, and nothing extra. Comments can
    #    live in the test file OR inside a page-object method (e.g. a login() convenience method
    #    legitimately bundles the steps for entering credentials and clicking submit) - so this
    #    scans both files combined rather than requiring every step to appear in the flat test body.
    referenced_ids = {int(m.group(1)) for m in STEP_COMMENT_PATTERN.finditer(combined_code)}
    manifest_ids = {s.step_id for s in manifest.steps}
    missing = manifest_ids - referenced_ids
    extra = referenced_ids - manifest_ids
    if missing:
        issues.append(f"Steps missing from generated test: {sorted(missing)}")
    if extra:
        issues.append(f"Generated test references step ids not in the manifest (drift): {sorted(extra)}")

    return ValidationResult(passed=not issues, issues=issues)
