from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from config import load_settings
from md_parser import parse_ac_md
from models import GeneratedTest, StepManifest
from prompts.claude_code_task_prompt import (
    build_retry_prompt,
    build_task_prompt,
    build_task_prompt_from_manifest,
)
from slug import slugify
from targets import TARGETS, Target, get_target
from validator import validate


def _slugify_ac_filename(name: str) -> str:
    """AC filenames look like `login_AC.md` - turn that into a clean scenario slug like `login`."""
    stem = Path(name).stem
    stem = re.sub(r"[_-]?ac$", "", stem, flags=re.IGNORECASE)
    return slugify(stem)


def _run_claude(
    prompt: str,
    cwd: Path,
    timeout: int,
    resume_session_id: str | None = None,
) -> tuple[list[dict], dict]:
    """Invoke `claude -p` (or `claude --resume <id> -p` for a retry turn) and return the parsed
    stream-json events plus the final result event. Raises RuntimeError with the clearest message
    available on any failure - missing binary, non-zero exit, or a run that errored out."""
    cmd = ["claude"]
    if resume_session_id:
        cmd += ["--resume", resume_session_id]
    cmd += [
        "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--allowedTools", "mcp__playwright__*,Write,Read,Edit",
        "--permission-mode", "acceptEdits",
    ]

    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Couldn't find 'claude' on PATH. Install Claude Code first - see README.md - and "
            "confirm with `claude --version` before running this again."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"claude -p did not finish within {timeout}s. It may be stuck mid-task; try again, "
            "or raise Settings.claude_timeout_seconds in config.py for a slower connection."
        )

    events: list[dict] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # non-JSON noise on stdout - ignore rather than crash the whole run

    result_events = [e for e in events if e.get("type") == "result"]
    final = result_events[-1] if result_events else {}

    if result.returncode != 0 and not final:
        raise RuntimeError(
            f"claude exited with code {result.returncode} and produced no parseable result.\n"
            f"stderr:\n{result.stderr.strip()}"
        )
    if final.get("is_error"):
        raise RuntimeError(f"Claude Code reported an error: {final.get('result', '(no message)')}")

    return events, final


def _read_generated(
    manifest_path: Path, page_object_path: Path, test_path: Path, events: list[dict]
) -> tuple[StepManifest, GeneratedTest]:
    missing = [p for p in (manifest_path, page_object_path, test_path) if not p.exists()]
    if missing:
        raise RuntimeError(
            "Claude Code finished but didn't write all expected files. Missing: "
            + ", ".join(str(p) for p in missing)
        )
    manifest = StepManifest.from_json(manifest_path.read_text(encoding="utf-8"))
    generated = GeneratedTest(
        page_object_path=str(page_object_path),
        page_object_code=page_object_path.read_text(encoding="utf-8"),
        test_path=str(test_path),
        test_code=test_path.read_text(encoding="utf-8"),
        stream_events=events,
    )
    return manifest, generated


def _scenario_paths(
    project_root: Path, settings, scenario: str, target: Target
) -> tuple[Path, Path, Path]:
    """Where this scenario's manifest, page object and test go - decided by the target, e.g.
    generated/tests/test_login.py for Python, generated_ts/tests/login.spec.ts for TypeScript.
    Also makes sure the target's one-time scaffolding (conftest.py / package.json etc.) exists."""
    generated_root = target.generated_root(project_root, settings)
    manifest_path, page_object_path, test_path = target.file_paths(generated_root, scenario)
    for p in (manifest_path, page_object_path, test_path):
        p.parent.mkdir(parents=True, exist_ok=True)
    target.ensure_project(generated_root)
    return manifest_path, page_object_path, test_path


def _generate_and_validate(
    initial_prompt: str,
    manifest_path: Path,
    page_object_path: Path,
    test_path: Path,
    project_root: Path,
    settings,
    target: Target,
) -> None:
    """Shared core: run Claude Code with retries, validate, offer to execute. Used by both the
    AC.md path (where Claude Code builds the manifest itself as part of the first turn) and the
    TestRail path (where the manifest is already written to manifest_path before this is ever
    called) - from here on, the two sources are indistinguishable, since validator.py and
    everything else only cares what's actually on disk, not where it came from."""
    session_id: str | None = None
    manifest: StepManifest | None = None
    generated: GeneratedTest | None = None
    feedback: str = ""
    total_attempts = settings.max_generation_retries + 1

    for attempt in range(1, total_attempts + 1):
        print(f"Running Claude Code (attempt {attempt}/{total_attempts})...")
        turn_prompt = initial_prompt if attempt == 1 else build_retry_prompt(
            feedback, str(manifest_path), str(page_object_path), str(test_path), target=target
        )
        events, final = _run_claude(
            turn_prompt, cwd=project_root, timeout=settings.claude_timeout_seconds,
            resume_session_id=session_id,
        )
        session_id = final.get("session_id", session_id)
        cost = final.get("total_cost_usd")
        if cost is not None:
            print(f"  session cost so far: ${cost:.4f}")

        manifest, generated = _read_generated(manifest_path, page_object_path, test_path, events)
        result = validate(manifest, generated, target=target)
        print(f"  validation: {result.summary()}")
        if result.passed:
            break
        feedback = result.summary()
    else:
        print("Validation kept failing after all retries - halting for human review.")
        sys.exit(1)

    print(f"Page object written: {page_object_path}")
    print(f"Test written: {test_path}")

    choice = input("\n[e]xecute script, [c]lose app: ").strip().lower()
    if choice == "e":
        # pytest for Python, `npx playwright test` for TypeScript - see Target.execute()
        target.execute(target.generated_root(project_root, settings), test_path)
    else:
        print("Closing.")


def run(ac_md_path: str, target: Target | None = None) -> None:
    target = target or get_target("python")
    settings = load_settings()
    project_root = Path.cwd()
    parsed = parse_ac_md(ac_md_path)
    print(f"Parsed AC ({len(parsed.ac_lines)} lines) - base URL: {parsed.base_url}")
    print(f"Target: {target.display_name}")

    scenario = _slugify_ac_filename(ac_md_path)
    manifest_path, page_object_path, test_path = _scenario_paths(
        project_root, settings, scenario, target
    )

    prompt = build_task_prompt(
        base_url=parsed.base_url,
        ac_lines=parsed.ac_lines,
        manifest_path=str(manifest_path),
        page_object_path=str(page_object_path),
        test_path=str(test_path),
        target=target,
    )
    _generate_and_validate(
        prompt, manifest_path, page_object_path, test_path, project_root, settings, target
    )


def run_from_testrail(case_id: int, base_url: str, target: Target | None = None) -> None:
    from testrail_adapter import case_to_manifest
    from testrail_client import fetch_case

    target = target or get_target("python")
    settings = load_settings()
    project_root = Path.cwd()

    case = fetch_case(case_id)
    manifest = case_to_manifest(case, base_url)
    print(f"Fetched TestRail case {case_id}: '{case.get('title')}' ({len(manifest.steps)} steps)")
    print(f"Target: {target.display_name}")

    manifest_path, page_object_path, test_path = _scenario_paths(
        project_root, settings, manifest.scenario_name, target
    )
    # Written deterministically, right now, in plain Python - no LLM call needed for this part,
    # since TestRail's Steps-template data is already exactly our StepManifest shape.
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")

    prompt = build_task_prompt_from_manifest(
        manifest_path=str(manifest_path),
        page_object_path=str(page_object_path),
        test_path=str(test_path),
        target=target,
    )
    _generate_and_validate(
        prompt, manifest_path, page_object_path, test_path, project_root, settings, target
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI-driven AC/TestRail -> Playwright test generator (Python or TypeScript)"
    )
    parser.add_argument("ac_md", nargs="?", help="Path to the Acceptance Criteria markdown file")
    parser.add_argument(
        "--testrail-case", type=int, metavar="CASE_ID",
        help="TestRail case ID to ingest instead of an AC file",
    )
    parser.add_argument(
        "--base-url",
        help="Base URL of the app under test - required with --testrail-case, since TestRail "
             "cases don't carry this the way an AC.md file's first line does",
    )
    parser.add_argument(
        "--target", default="python", choices=sorted(TARGETS),
        help="Language/runner to generate: python (Playwright + pytest, the default) or "
             "typescript (Playwright Test, @playwright/test)",
    )
    args = parser.parse_args()

    if args.testrail_case and args.ac_md:
        parser.error("Provide either an AC file or --testrail-case, not both.")
    if args.testrail_case and not args.base_url:
        parser.error("--base-url is required when using --testrail-case.")
    if not args.testrail_case and not args.ac_md:
        parser.error("Provide either an AC file path or --testrail-case.")

    target = get_target(args.target)
    if args.testrail_case:
        run_from_testrail(args.testrail_case, args.base_url, target)
    else:
        run(args.ac_md, target)


if __name__ == "__main__":
    main()
