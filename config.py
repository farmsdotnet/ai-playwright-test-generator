"""Settings for the Claude Code + Playwright MCP architecture. No API key here - Claude Code
authenticates itself (via the Pro subscription login it already has), so there's nothing for this
project to hold a credential for anymore.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    max_generation_retries: int = 2  # total attempts = this + 1
    generated_dir: str = "generated"  # Python + pytest output (--target python, the default)
    generated_ts_dir: str = "generated_ts"  # TypeScript + Playwright Test output (--target typescript)
    claude_timeout_seconds: int = 900  # generous ceiling for a single claude -p run


def load_settings() -> Settings:
    return Settings()
