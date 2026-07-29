from __future__ import annotations

from anthropic import Anthropic

from config import Settings
from models import StepManifest
from prompts.step_planner_prompt import SYSTEM_PROMPT, build_user_prompt


def plan_steps(settings: Settings, base_url: str, ac_lines: list[str]) -> StepManifest:
    client = Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.model,
        max_tokens=settings.max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(base_url, ac_lines)}],
    )
    raw = "".join(block.text for block in response.content if block.type == "text")
    return StepManifest.from_json(raw)
