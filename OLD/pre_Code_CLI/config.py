from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _default_mcp_invocation() -> tuple[str, tuple[str, ...]]:
    """Playwright MCP is launched via npx. On Windows, npx is installed as npx.cmd - a batch
    script, not a real .exe - which Python's subprocess machinery can't exec directly; it needs to
    go through cmd.exe first (a well-documented Node-on-Windows quirk, not specific to this
    project). `cmd /c` fixes it. POSIX platforms (macOS/Linux) invoke npx directly, no wrapper
    needed."""
    if platform.system() == "Windows":
        return "cmd", ("/c", "npx", "-y", "@playwright/mcp@latest")
    return "npx", ("-y", "@playwright/mcp@latest")


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    model: str = "claude-sonnet-5"
    max_tokens: int = 4096
    # Playwright MCP server is spawned locally - requires Node.js 18+ on PATH.
    playwright_mcp_command: str = field(default_factory=lambda: _default_mcp_invocation()[0])
    playwright_mcp_args: tuple = field(default_factory=lambda: _default_mcp_invocation()[1])
    max_generation_retries: int = 2  # total attempts = this + 1
    generated_dir: str = "generated"


def load_settings() -> Settings:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Copy .env to .env and add your key."
        )
    return Settings(anthropic_api_key=key)