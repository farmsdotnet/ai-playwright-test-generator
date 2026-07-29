"""One-off diagnostic for the Claude Code + Playwright MCP architecture. Run this once when
setting up on a new machine, before trying cli.py:

    python check_claude_code_setup.py

Checks, in order: Claude Code is installed and on PATH, `claude doctor` reports a healthy
install, and the Playwright MCP server declared in .mcp.json actually connects.
"""
from __future__ import annotations

import subprocess
import sys


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    # Without an explicit encoding, subprocess falls back to the OS's default locale codec to
    # decode captured output - on Windows that's typically cp1252, not UTF-8. Claude Code's CLI
    # output uses UTF-8 (styled characters, arrows, etc.), so without this it can crash a
    # background reader thread with a UnicodeDecodeError and leave stdout/stderr as None.
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def main() -> None:
    print("Checking `claude --version` ...")
    try:
        version = _run(["claude", "--version"])
    except FileNotFoundError:
        print(
            "\nCouldn't find 'claude' on PATH. Install Claude Code first:\n"
            "  Windows (PowerShell): irm https://claude.ai/install.ps1 | iex\n"
            "  or: winget install Anthropic.ClaudeCode\n"
            "  macOS/Linux:          curl -fsSL https://claude.ai/install.sh | bash\n"
            "Then open a NEW terminal and re-run this script."
        )
        sys.exit(1)
    if version.returncode != 0:
        print(f"`claude --version` failed:\n{(version.stderr or '').strip()}")
        sys.exit(1)
    print(f"  {(version.stdout or '').strip()}")

    print("\nRunning `claude doctor` ...")
    doctor = _run(["claude", "doctor"])
    print((doctor.stdout or "").strip() or (doctor.stderr or "").strip())
    if doctor.returncode != 0:
        print("\n`claude doctor` reported a problem - fix that before continuing.")
        sys.exit(1)

    print("\nChecking MCP servers configured in .mcp.json ...")
    mcp_list = _run(["claude", "mcp", "list"])
    output = (mcp_list.stdout or "").strip() or (mcp_list.stderr or "").strip()
    print(output)
    if "playwright" not in output.lower():
        print(
            "\nDidn't see a 'playwright' MCP server listed. Confirm you're running this from the "
            "project root (where .mcp.json lives) and that Node.js is installed - Playwright MCP "
            "is spawned via npx, which needs Node.js 18+ on PATH."
        )
        sys.exit(1)
    if "failed" in output.lower() or "error" in output.lower():
        print(
            "\nThe playwright server is listed but may not be connected cleanly - check the "
            "output above. On Windows, .mcp.json already wraps npx with `cmd /c`, which is "
            "required (see README) - if you're not on Windows, drop that wrapper."
        )
        sys.exit(1)

    print("\nSetup looks good - you're ready to run: python cli.py samples/login_AC.md")


if __name__ == "__main__":
    main()
