"""Non-LLM validation gate. This is what actually enforces the non-negotiables:
every locator must be traceable to a real accessibility-tree snapshot captured
during generation, and every generated test step must map 1:1 to a step in the
manifest - no drift, no gaps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from models import StepManifest
from test_generator import GeneratedTest

LOCATOR_PATTERN = re.compile(
    r"\.get_by_(role|label|text|test_id|placeholder|alt_text|title)\(\s*(?:\"([^\"]+)\"|'([^']+)')"
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


def _extract_snapshot_text(transcript: list[dict]) -> str:
    """Pull every MCP tool_result out of the transcript so we have real page data - snapshots,
    but also nav/click confirmations - to check generated locators against."""
    chunks = []
    for msg in transcript:
        if msg.get("role") != "user" or not isinstance(msg.get("content"), list):
            continue
        for item in msg["content"]:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                chunks.append(str(item.get("content", "")))
    return "\n".join(chunks)


def validate(manifest: StepManifest, generated: GeneratedTest) -> ValidationResult:
    issues: list[str] = []
    snapshot_text = _extract_snapshot_text(generated.transcript)
    combined_code = generated.page_object_code + "\n" + generated.test_code

    # 1. Locator grounding - reject anything that doesn't trace back to something Claude actually
    #    observed via an MCP tool call this run.
    for match in LOCATOR_PATTERN.finditer(combined_code):
        locator_kind = match.group(1)
        locator_value = match.group(2) or match.group(3)
        if locator_value and locator_value not in snapshot_text:
            issues.append(
                f"Locator value '{locator_value}' (get_by_{locator_kind}) was not found in any "
                f"captured MCP tool result - likely hallucinated."
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
