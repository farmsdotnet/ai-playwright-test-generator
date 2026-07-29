"""One-off diagnostic: confirms Node/npx can spawn the Playwright MCP server, that our MCP client
can talk to it, and that it can actually open a page and capture an accessibility snapshot.

Run this once when setting up on a new machine, before trying the full cli.py pipeline:

    python check_mcp_setup.py
    python check_mcp_setup.py https://www.saucedemo.com   # optional: check a specific URL
"""
from __future__ import annotations

import asyncio
import sys

from config import Settings
from mcp_client import PlaywrightMCPSession

DEFAULT_URL = "https://www.saucedemo.com"


async def main(url: str) -> None:
    settings = Settings(anthropic_api_key="unused-for-this-check")  # no Claude call in this script
    print(f"Spawning Playwright MCP server via: {settings.playwright_mcp_command} "
          f"{' '.join(settings.playwright_mcp_args)}")

    async with PlaywrightMCPSession(
        settings.playwright_mcp_command, list(settings.playwright_mcp_args)
    ) as mcp:
        tools = await mcp.anthropic_tools()
        print(f"\nConnected. {len(tools)} tools available, including:")
        for t in tools[:8]:
            print(f"  - {t['name']}")

        print(f"\nNavigating to {url} ...")
        nav_result = await mcp.call_tool("browser_navigate", {"url": url})
        if nav_result.startswith("TOOL ERROR"):
            print(f"\nNavigation failed:\n{nav_result}")
            if "not installed" in nav_result:
                print(
                    "\nLikely fix: install the browser binary the MCP server expects, e.g.\n"
                    "  npx @playwright/mcp install-browser chrome-for-testing\n"
                    "(the exact package name is printed in the error above - run that command)."
                )
            sys.exit(1)
        print("Navigation OK.")

        print("\nCapturing accessibility snapshot ...")
        snapshot = await mcp.call_tool("browser_snapshot", {})
        if snapshot.startswith("TOOL ERROR"):
            print(f"\nSnapshot failed:\n{snapshot}")
            sys.exit(1)

        print(f"Snapshot OK ({len(snapshot)} chars). First 400 chars:\n")
        print(snapshot[:400])
        print("\nSetup looks good - you're ready to run: python cli.py samples/login_AC.md")


if __name__ == "__main__":
    target_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    asyncio.run(main(target_url))
