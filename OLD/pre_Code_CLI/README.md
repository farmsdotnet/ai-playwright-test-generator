# Saucedemo AI QA Pipeline (v0.1)

AC markdown -> Claude Sonnet 5 (Playwright-MCP-grounded) -> validated Playwright/pytest POM test.

## How it fits together

```
samples/login_AC.md            (Acceptance Criteria: heading, AC point 1 embeds the base URL)
      │
      ▼
md_parser.py ──────────► parsed base_url + ordered AC lines
      │
      ▼
step_planner.py ───────► Claude call #1: AC -> StepManifest (models.py)
      │                  also rendered to generated/<scenario>_scaffold.py (human-readable plan)
      ▼
mcp_client.py + test_generator.py
      │        Claude call #2 (agentic): navigates + snapshots via the real
      │        Playwright MCP server, then emits a page object + pytest test
      │        grounded in what it actually saw.
      ▼
validator.py ──────────► deterministic gate:
      │                    1. every locator must trace to a captured MCP snapshot
      │                    2. every manifest step must be covered, no drift
      ▼
cli.py ────────────────► on failure: retry with feedback (config.max_generation_retries)
                          on success: write files, then [e]xecute / [c]lose
```

## Setup

1. `pip install -r requirements.txt`
2. Node.js 18+ on PATH (tested against v22.22.2). No global npm install needed - `mcp_client.py`
   spawns the Playwright MCP server itself via `npx -y @playwright/mcp@latest` on demand.
3. `cp .env.example .env` and add your `ANTHROPIC_API_KEY`
4. Run `python check_mcp_setup.py` - this spawns the real MCP server, lists its tools, navigates to
   saucedemo, and captures a live accessibility snapshot, so you catch any environment problems
   (Node not on PATH, missing browser binary, etc.) before running the full pipeline. If it reports
   a missing browser, it prints the exact `npx @playwright/mcp install-browser <name>` command to
   fix it - in our own test run no extra browser install was needed at all with the default config.

## Run

```
python cli.py samples/login_AC.md
```

Output lands in `generated/`: the step scaffold, the page object, and the test file.

## Open items / things to sanity-check together on the first real run

- **Retry-on-failure default**: currently auto-retries generation up to
  `Settings.max_generation_retries` (2) times, feeding the validator's failure summary back to
  Claude, before halting for human review. Adjust in `config.py` if you'd rather it halt on the
  first failure.
- **Single vs. split output files**: generated code is written as two files (a page object +
  a test file) per standard POM, not one combined file - matches your confirmed POM decision, flag
  if you actually want the "new python test file" from step 1 of the flow to be the *only* file
  produced.
- Model calls currently use no prompt caching / streaming - fine for a single scenario at a time,
  worth revisiting once we're batching multiple AC files.
- Tool names (`browser_navigate`, `browser_snapshot`, `browser_click`, etc.) referenced in
  `prompts/test_generator_prompt.py` were confirmed live against the real MCP server, not guessed -
  if a future `@playwright/mcp` release renames any of these, `check_mcp_setup.py`'s tool listing
  will surface the mismatch immediately.
