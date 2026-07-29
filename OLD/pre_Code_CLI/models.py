"""Shared data models for the AC -> test-step -> generated-test pipeline."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Literal, Optional

StepType = Literal["action", "assertion"]


@dataclass
class Step:
    step_id: int
    step_type: StepType
    description: str
    target_element_description: Optional[str] = None
    expected_result: Optional[str] = None


@dataclass
class StepManifest:
    """The source of truth for a single generated test.

    Produced once by step_planner.py from the AC, then passed unchanged into
    test_generator.py and validator.py. Nothing downstream is allowed to add,
    remove, or re-order steps - only implement them.
    """

    scenario_name: str
    base_url: str
    steps: list[Step] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "scenario_name": self.scenario_name,
                "base_url": self.base_url,
                "steps": [asdict(s) for s in self.steps],
            },
            indent=2,
        )

    @classmethod
    def from_json(cls, raw: str) -> "StepManifest":
        raw = _strip_code_fence(raw)
        data = json.loads(raw)
        steps = [Step(**s) for s in data["steps"]]
        return cls(scenario_name=data["scenario_name"], base_url=data["base_url"], steps=steps)


def _strip_code_fence(text: str) -> str:
    """Defensive cleanup in case the model wraps its JSON in ```json ... ``` anyway."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()
