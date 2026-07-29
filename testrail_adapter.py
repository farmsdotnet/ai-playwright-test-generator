"""Converts a fetched TestRail case (Steps template) directly into our StepManifest - no LLM call
needed for this part, since TestRail's custom_steps_separated field is already exactly the
structured step/expected-result data our manifest schema wants. A human tester already did the
step-boundary reasoning an AC.md file would otherwise need Claude Code to infer, so this is a
plain, deterministic conversion.
"""
from __future__ import annotations

from models import Step, StepManifest
from slug import slugify


class UnsupportedCaseError(Exception):
    pass


def case_to_manifest(case: dict, base_url: str) -> StepManifest:
    steps_data = case.get("custom_steps_separated")
    if not steps_data:
        raise UnsupportedCaseError(
            f"TestRail case {case.get('id')} ('{case.get('title')}') has no "
            "custom_steps_separated data. This integration currently only supports cases written "
            "with the Steps template - a Text-template (freeform) case would need a different "
            "adapter path, not yet built."
        )

    steps: list[Step] = []
    for i, raw_step in enumerate(steps_data, start=1):
        content = (raw_step.get("content") or "").strip()
        expected = raw_step.get("expected")
        expected = expected.strip() if expected else None
        # This is a loose heuristic, not a precise classification: TestRail steps very commonly
        # combine an action (content) with a documented expected outcome, e.g. "Click submit" ->
        # "user is redirected to inventory" - which isn't purely one or the other. That's fine
        # here: step_type is informational only in the current prompt (Claude Code reads
        # description + expected_result directly regardless of this label) and validator.py never
        # checks it at all - so precision on this field isn't load-bearing today.
        steps.append(
            Step(
                step_id=i,
                step_type="assertion" if expected else "action",
                description=content,
                # Not carried by TestRail - Claude Code infers the target element from the
                # description text itself, same as it already does for AC.md-derived steps.
                target_element_description=None,
                expected_result=expected,
            )
        )

    case_id = case.get("id")
    title = case.get("title") or f"case_{case_id}"
    scenario_name = f"tr{case_id}_{slugify(title)}" if case_id else slugify(title)

    return StepManifest(scenario_name=scenario_name, base_url=base_url, steps=steps)
