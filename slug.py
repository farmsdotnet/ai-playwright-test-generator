"""Shared slug generation, used by both the AC.md filename path (cli.py) and the TestRail
case-title path (testrail_adapter.py), so scenario names are normalized the same way regardless
of which front door produced them.
"""
from __future__ import annotations

import re


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return slug or "scenario"
