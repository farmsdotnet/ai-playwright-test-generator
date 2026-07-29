from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

from config import load_settings
from mcp_client import PlaywrightMCPSession
from md_parser import parse_ac_md
from models import StepManifest
from step_planner import plan_steps
from test_generator import GeneratedTest, TestGenerator
from validator import validate


def _render_scaffold(manifest: StepManifest) -> str:
    """Step 1's output: a human-readable, ordered step scaffold - not runnable code yet, just the
    plan the rest of the pipeline is held accountable to."""
    lines = [
        f'"""Step scaffold for scenario: {manifest.scenario_name}',
        f"Base URL: {manifest.base_url}",
        '"""',
        "",
    ]
    for step in manifest.steps:
        lines.append(f"# step {step.step_id} [{step.step_type}]: {step.description}")
        if step.target_element_description:
            lines.append(f"#   target: {step.target_element_description}")
        if step.expected_result:
            lines.append(f"#   expected: {step.expected_result}")
        lines.append("")
    return "\n".join(lines)


async def run(ac_md_path: str) -> None:
    settings = load_settings()
    parsed = parse_ac_md(ac_md_path)
    print(f"Parsed AC ({len(parsed.ac_lines)} lines) - base URL: {parsed.base_url}")

    manifest = plan_steps(settings, parsed.base_url, parsed.ac_lines)
    print(f"Step manifest ready: '{manifest.scenario_name}' ({len(manifest.steps)} steps)")

    generated_dir = Path(settings.generated_dir)
    generated_dir.mkdir(parents=True, exist_ok=True)
    scaffold_path = generated_dir / f"{manifest.scenario_name}_scaffold.py"
    scaffold_path.write_text(_render_scaffold(manifest))
    print(f"Step scaffold written: {scaffold_path}")

    generated: GeneratedTest | None = None
    feedback: str | None = None

    async with PlaywrightMCPSession(
        settings.playwright_mcp_command, list(settings.playwright_mcp_args)
    ) as mcp:
        generator = TestGenerator(settings, mcp)
        total_attempts = settings.max_generation_retries + 1
        for attempt in range(1, total_attempts + 1):
            print(f"Generating test (attempt {attempt}/{total_attempts})...")
            generated = await generator.generate(manifest, feedback=feedback)
            result = validate(manifest, generated)
            print(result.summary())
            if result.passed:
                break
            feedback = result.summary()
        else:
            print("Validation kept failing after all retries - halting for human review.")
            sys.exit(1)

    assert generated is not None
    po_path = generated_dir / generated.page_object_path
    test_path = generated_dir / generated.test_path
    po_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.parent.mkdir(parents=True, exist_ok=True)
    po_path.write_text(generated.page_object_code)
    test_path.write_text(generated.test_code)
    print(f"Page object written: {po_path}")
    print(f"Test written: {test_path}")

    choice = input("\n[e]xecute script, [c]lose app: ").strip().lower()
    if choice == "e":
        subprocess.run(["pytest", str(test_path), "-v"])
    else:
        print("Closing.")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-driven AC -> Playwright test generator")
    parser.add_argument("ac_md", help="Path to the Acceptance Criteria markdown file")
    args = parser.parse_args()
    asyncio.run(run(args.ac_md))


if __name__ == "__main__":
    main()
