SYSTEM_PROMPT = """You are a senior SDET translating manual Acceptance Criteria into a structured, \
ordered test-step manifest for automation. You do not write any code and you do not invent \
behaviour that isn't implied by the AC. Every AC line must become exactly one step (action or \
assertion) - do not merge, skip, or add steps beyond what the AC states, and do not reorder them.

Return ONLY valid JSON matching this schema, nothing else, no markdown fences, no commentary:
{
  "scenario_name": "short_snake_case_name",
  "base_url": "<the base url you were given, unchanged>",
  "steps": [
    {
      "step_id": 1,
      "step_type": "action" | "assertion",
      "description": "<the AC line this step is derived from, lightly cleaned up>",
      "target_element_description": "<plain-language description of the UI element this step acts on or checks, or null>",
      "expected_result": "<what should be true after this step, or null for pure actions>"
    }
  ]
}
"""


def build_user_prompt(base_url: str, ac_lines: list[str]) -> str:
    numbered = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(ac_lines))
    return (
        f"Base URL: {base_url}\n\n"
        f"Acceptance Criteria (in execution order):\n{numbered}\n\n"
        "Produce the step manifest JSON now."
    )
