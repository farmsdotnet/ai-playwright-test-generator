"""Thin wrapper around the TestRail v2 REST API - just enough to fetch a single test case by ID.
Auth is HTTP Basic (email + API key), per TestRail's documented API access method.
"""
from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()


class TestRailError(Exception):
    pass


def _get_config() -> tuple[str, str, str]:
    url = os.environ.get("TESTRAIL_URL")
    email = os.environ.get("TESTRAIL_EMAIL")
    api_key = os.environ.get("TESTRAIL_API_KEY")
    missing = [
        name
        for name, val in (
            ("TESTRAIL_URL", url), ("TESTRAIL_EMAIL", email), ("TESTRAIL_API_KEY", api_key),
        )
        if not val
    ]
    if missing:
        raise TestRailError(
            f"Missing TestRail config: {', '.join(missing)}. Set these in .env - see "
            ".env."
        )
    return url.rstrip("/"), email, api_key


def fetch_case(case_id: int) -> dict:
    """Fetch a single test case by ID via GET /index.php?/api/v2/get_case/{case_id}."""
    url, email, api_key = _get_config()
    endpoint = f"{url}/index.php?/api/v2/get_case/{case_id}"
    try:
        response = requests.get(
            endpoint,
            auth=(email, api_key),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise TestRailError(f"Couldn't reach TestRail at {url}: {exc}") from exc

    if response.status_code == 401:
        raise TestRailError(
            "TestRail rejected the credentials (401) - check TESTRAIL_EMAIL/TESTRAIL_API_KEY."
        )
    if response.status_code == 400:
        raise TestRailError(
            f"TestRail returned 400 for case {case_id} - it likely doesn't exist: {response.text}"
        )
    if response.status_code != 200:
        raise TestRailError(f"TestRail returned HTTP {response.status_code}: {response.text}")

    return response.json()
