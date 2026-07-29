"""Parses the AC markdown file format:

    Acceptance Criteria:
    - <first AC point, which embeds the base URL, e.g. "Navigate to https://www.saucedemo.com">
    - <second AC point>
    ...

Everything below the literal 'Acceptance Criteria:' heading is the ordered AC, and IS kept as-is
(including that first line) since it's a real test step in its own right - it just also happens to
carry the base URL. The base URL is taken specifically from that first AC line, not scanned for
anywhere else in the file, so a stray URL elsewhere in the document (e.g. in a comment or an
unrelated note) can't get picked up by mistake.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

AC_HEADING_PATTERN = re.compile(r"^\s*acceptance criteria:\s*$", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s)>\]]+")
BULLET_PREFIX_PATTERN = re.compile(r"^\s*[-*\d.]+\s*")


class MdParseError(Exception):
    pass


@dataclass
class ParsedAC:
    base_url: str
    ac_lines: list[str]


def parse_ac_md(path: str | Path) -> ParsedAC:
    path = Path(path)
    if not path.exists():
        raise MdParseError(f"AC file not found: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()

    heading_idx = next(
        (i for i, line in enumerate(lines) if AC_HEADING_PATTERN.match(line.strip())),
        None,
    )
    if heading_idx is None:
        raise MdParseError(
            "Could not find an 'Acceptance Criteria:' heading in the file. "
            "Expected a line that reads exactly 'Acceptance Criteria:'."
        )

    ac_block_raw = [line for line in lines[heading_idx + 1 :] if line.strip()]
    if not ac_block_raw:
        raise MdParseError("Found 'Acceptance Criteria:' heading but no AC content below it.")

    first_line = ac_block_raw[0]
    url_match = URL_PATTERN.search(first_line)
    if not url_match:
        raise MdParseError(
            "Expected the base URL to be embedded in the first line under 'Acceptance Criteria:', "
            f"but found no http(s):// URL in: {first_line!r}"
        )
    base_url = url_match.group(0).rstrip(".,)")

    ac_lines = [BULLET_PREFIX_PATTERN.sub("", line).strip() for line in ac_block_raw]

    return ParsedAC(base_url=base_url, ac_lines=ac_lines)
