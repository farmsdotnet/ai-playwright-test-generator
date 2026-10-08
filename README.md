# AI QA Pipeline (v0.4 - Python or TypeScript output)

Two front doors, one pipeline, two output languages: AC markdown **or** a TestRail test case ->
Claude Code (native Playwright MCP) -> validated Playwright Page Object Model test, written in
**Python + pytest** (the default) or **TypeScript + Playwright Test** (`--target typescript`).

v0.1 drove a hand-rolled Python agentic loop against the raw Anthropic API, billed per token.
v0.2 replaced that with Claude Code itself (billed against your Claude Pro subscription's included
usage instead), using its native MCP support to drive the same Playwright MCP server. v0.3 adds a
second, optional input source - an existing TestRail test case - without touching anything
downstream: the deterministic validation gate doesn't care who wrote the code or where the manifest
came from, only what's actually in it. v0.4 adds a second output language the same way - see
[v0.4: TypeScript target](#v04-typescript-target) below.

## v0.4: TypeScript target

```
python cli.py samples/login_AC.md --target typescript
python cli.py --testrail-case 46 --base-url https://www.saucedemo.com --target typescript
```

Same AC file, same manifest, same Playwright MCP grounding, same validator - the only thing that
changes is the language the page object and test are written in:

```
generated_ts/
  package.json, playwright.config.ts, tsconfig.json, .gitignore   (written once, never overwritten)
  <scenario>_manifest.json
  pageObjects/<scenario>.page.ts        (exported classes, async methods, getByRole/getByLabel/...)
  tests/<scenario>.spec.ts              (test() + expect() from @playwright/test, `// step <id>:` comments)
```

`[e]xecute` runs `npx playwright test tests/<scenario>.spec.ts` inside `generated_ts/`. The first
time, it runs `npm install` and `npx playwright install chromium` for you. The config keeps a
trace, screenshot and video for any failing test (`test-results/`) and writes an HTML report
(`npx playwright show-report`). `npm run typecheck` type-checks everything with `tsc --noEmit`.

**How it's built - `targets.py`.** Everything language-specific lives in one place: a `Target`
per language that owns the output paths, the one-time scaffold (conftest.py for Python,
package.json/config for TypeScript), the Playwright method names the prompt uses (`get_by_role` vs
`getByRole`), the "write the generated code" section of the prompt, the regexes the validator
uses to read the code back, and how `[e]xecute` runs it. Nothing else knows which language it is
producing:

- **Untouched:** `md_parser.py`, `testrail_client.py`, `testrail_adapter.py`, `models.py`
  (manifest schema), the Claude Code invocation / `--resume` retry loop.
- **Parameterised, not forked:** `prompts/claude_code_task_prompt.py` and `validator.py` take a
  `target`. The grounding rules are written once and spelled with each target's method names, so
  Python and TypeScript can't drift apart. With the Python target the prompts are identical,
  character for character, to v0.3 - `selftests/test_prompts.py` checks that against saved
  copies of v0.3's output, so the proven Python path is provably unchanged.
- **Why the validator didn't need rewriting:** grounding checks the four strategy *concepts*
  (role, label, text, alt text) against the accessibility-tree snapshot. The snapshot is the same
  whatever language the test is written in; only the regex that pulls `getByRole('button', {
  name: 'Login' })` out of a .ts file differs from the one for `get_by_role("button",
  name="Login")`.

Adding a third language (Java, C#) means one new `Target` subclass - nothing else changes.

### Validator hardening (applies to both languages)

Two gaps found while making the validator language-agnostic, both closed for Python and
TypeScript alike:

- **`get_by_role`'s `name` is now grounded, not just the role.** v0.3 only checked the first
  string argument - the role itself, e.g. `"button"` - so `get_by_role("button", name="Logn")`
  passed because `button` appeared in the snapshot, even though nothing was named `Logn`. That's the
  same class of bug as the original `get_by_test_id("username")` one.
- **Page-level selector shortcuts are banned**, e.g. `page.click("#login-button")`,
  `page.fill(...)`, `page.query_selector(...)`, `page.$(...)` in TypeScript. They take a raw
  selector string - the same escape hatch as `.locator("...")`, just spelled differently.

### Self-tests

```
pip install pytest
python -m pytest selftests -v
```

50 tests, no Claude login, network or browser needed. They cover: the Python prompts are
unchanged from v0.3; the TypeScript prompts contain no Python method names; every banned or
hallucinated locator kind fails in both languages; step coverage and drift in both languages;
and a full `python cli.py ... --target python|typescript` run with Claude Code replaced by
`selftests/fake_claude.py`, including a hallucinated locator being caught on attempt 1 and fixed
on the `--resume` retry. (The CLI dry-run tests skip on Windows - the fake `claude` relies on a
POSIX shebang - the rest run everywhere.)

Also verified by hand while building v0.4: a TypeScript page object and spec in exactly the shape
the prompt asks for were checked by the validator against a real Playwright accessibility
snapshot, type-checked with `tsc --noEmit`, and run through `[e]xecute`'s code path
(`npx playwright test`) - passing with correct credentials, failing with the trace and
screenshot kept with wrong ones.

### Housekeeping in v0.4

- `.gitignore` added. `.env`, `__pycache__/` and the `.playwright-mcp/` session logs are no
  longer tracked. **The repo is public and `.env` with TestRail credentials was committed in
  v0.3 - those credentials are still in git history, so revoke that API key** (the TestRail trial
  has expired, which may have done this already). Use `.env.example` as the template.

## How it fits together

```
samples/login_AC.md          (Acceptance Criteria: heading, AC point 1 embeds the base URL)
      |
      v
md_parser.py --------------> parsed base_url + ordered AC lines (unchanged from v0.1)
      |
      v
cli.py builds one task prompt (prompts/claude_code_task_prompt.py) and runs:
      claude -p "<prompt>" --output-format stream-json --allowedTools "mcp__playwright__*,Write"
      |
      |   Claude Code, in ONE session: reasons out the step manifest, uses the Playwright MCP
      |   tools (declared in .mcp.json) to navigate + snapshot + ground every locator, then
      |   writes three files directly via its own Write tool - no more text-block parsing.
      v
generated/<scenario>_manifest.json   (the step manifest, same schema as v0.1)
generated/page_objects/<scenario>_page.py   (page object)
generated/tests/test_<scenario>.py   (pytest test)
      |
      v
validator.py ---------------> same deterministic gate as v0.1:
      |                          1. every locator must trace to a real MCP tool_result captured
      |                             during the session (read from the stream-json event log)
      |                          2. every manifest step must be covered, no drift
      v
cli.py ----------------------> on failure: `claude --resume <session_id>` with the validator's
                                feedback (config.max_generation_retries)
                                on success: [e]xecute / [c]lose, same as v0.1
```

### The TestRail branch (v0.3, optional)

```
TestRail case (Steps template)
      |
      v
testrail_client.py ---------> raw case JSON (GET /api/v2/get_case/{id}, HTTP Basic auth)
      |
      v
testrail_adapter.py ---------> StepManifest, built DETERMINISTICALLY in plain Python - no LLM
      |                        call needed for this part, since TestRail's custom_steps_separated
      |                        field is already exactly our manifest's step/expected shape; a
      |                        human tester already did the step-boundary reasoning an AC.md file
      |                        would otherwise need Claude Code to infer.
      v
cli.py writes generated/<scenario>_manifest.json itself, then runs Claude Code with
build_task_prompt_from_manifest() - same as the AC.md path from here on, just skipping the
"build the manifest" step because it already exists on disk.
      |
      v
   (rejoins the same validator.py / retry / [e]xecute flow shown above)
```

## What changed from v0.1, and why

- **No more `ANTHROPIC_API_KEY` / `.env`.** Claude Code authenticates itself against your Claude
  Pro login (browser-based OAuth on first run), so there's no API key for this project to hold.
- **`mcp_client.py`, `step_planner.py`, `test_generator.py` are gone.** Claude Code has its own
  native MCP client and its own agent loop (with its own prompt caching, which our v0.1 loop
  didn't have) - our hand-rolled versions of both were pure overhead once Claude Code can do it.
- **One task prompt instead of two API calls.** `prompts/claude_code_task_prompt.py` covers what
  `step_planner_prompt.py` + `test_generator_prompt.py` used to split across two model calls,
  since Claude Code does the manifest reasoning and the MCP-grounded generation in one session.
- **`validator.py` is functionally the same**, just reading locator-grounding data out of Claude
  Code's `--output-format stream-json` event log instead of our own hand-rolled message transcript.
- **`models.py`, `md_parser.py`, `samples/login_AC.md` are untouched.** Nothing about parsing the
  AC file or the step-manifest schema needed to change.
- **`page_objects/` instead of `pages/`** (added after the first real run). The original name
  collided with an unrelated, generically-named PyPI package literally called `pages` that
  happened to be installed - PyCharm's static import resolver was matching that installed
  package's own `__init__.py` instead of the local folder, causing "Cannot find reference"
  warnings in the editor even though pytest ran the generated test fine at runtime (the two
  resolvers don't use the same rules). Renamed to something far less likely to collide with
  anything on PyPI.
- **`get_by_test_id`, raw `#id`/`[data-testid=...]` selectors, `get_by_placeholder`, and
  `get_by_title` are all banned outright** (added after the first real run surfaced a real bug:
  `get_by_test_id("username")` passed validation, but the real page attribute was `id="user-name"`
  - a timeout at test-execution time). An accessibility-tree snapshot shows an element's role and
  accessible name only - never its `id`/`data-testid` attribute, and `placeholder`/`title` text
  only becomes the accessible name when nothing higher-precedence (a `<label>`, `aria-label`)
  already claims it. The old substring-based grounding check could pass by coincidence whenever a
  guessed value merely resembled the accessible name, without the underlying attribute actually
  matching anything real - so these are now an automatic failure regardless of any textual
  coincidence, enforced in both the prompt (Claude Code is told not to use them at all) and the
  validator. Only `get_by_role`/`get_by_label`/`get_by_text`/`get_by_alt_text` are accepted, since
  those are the only locator kinds a snapshot can actually confirm.
- **Raw `.locator()` calls with any CSS/XPath selector are now banned entirely**, not just ones
  matching a specific list of risky attributes. The original fix only pattern-matched `id`/
  `data-testid` inside `.locator()` strings, which left an identical gap open for anything not on
  that list - a class selector (`.btn-primary`) or a structural one (`div > span:nth-child(2)`) is
  exactly as invisible to an accessibility snapshot as an id selector, just not one we'd thought to
  block. An allowlist of the four groundable methods (`get_by_role`/`label`/`text`/`alt_text`) is
  complete by construction; a blocklist of specific bad patterns never can be. `.nth()`/`.first()`/
  `.last()` chained onto one of those four is unaffected - that narrows an already-grounded
  locator rather than introducing a new ungroundable one.

## Setup

1. `pip install -r requirements.txt` (just `playwright`/`pytest` now - only needed to run the
   *generated* tests afterward, not to generate them).
2. **Install Claude Code** (this is the one new dependency):
   - Windows (PowerShell, no admin needed): `irm https://claude.ai/install.ps1 | iex`
   - Windows (WinGet): `winget install Anthropic.ClaudeCode`
   - macOS/Linux: `curl -fsSL https://claude.ai/install.sh | bash`
   - Open a **new** terminal afterward, then confirm: `claude --version` and `claude doctor`
   - **Git for Windows is recommended** if you're on native Windows - Claude Code uses Git Bash
     internally for shell commands even when launched from PowerShell/CMD.
   - First run triggers a browser login - sign in with the same account as your Claude Pro
     subscription. No API key needed.
3. Node.js 18+ still required - Playwright MCP itself is an npm package, spawned via `npx`, same
   as v0.1. `.mcp.json` in this project root already declares it with the `cmd /c` wrapper Windows
   needs (see the note below); non-Windows users should drop that wrapper (`"command": "npx"`).
4. Run `python check_claude_code_setup.py` - confirms Claude Code is installed, healthy, and can
   see the `playwright` MCP server declared in `.mcp.json`, before you run anything that spends
   real usage.

### Windows npx note (carried over from v0.1, still applies)
`npx` is installed as `npx.cmd` on Windows - a batch script Windows can't execute directly the way
`.mcp.json`'s config expects. `cmd /c npx ...` is the documented fix, and it's already baked into
this project's `.mcp.json`. If you're not on Windows, remove the `cmd`/`/c` wrapper.

## Run

**From an AC.md file (v0.1/v0.2 path, unchanged):**
```
python cli.py samples/login_AC.md                       # Python + pytest (default)
python cli.py samples/login_AC.md --target typescript   # TypeScript + Playwright Test (v0.4)
```

**From a TestRail case (v0.3, optional):**
```
python cli.py --testrail-case 4075 --base-url https://www.saucedemo.com
```
`--base-url` is required here - unlike an AC.md file, a TestRail case has no inherent field for
the URL of the app under test, so it has to be supplied explicitly.

Either way, output lands in `generated/` (or `generated_ts/` with `--target typescript`): the step
manifest, the page object, and the test file.

## Optional: TestRail ingestion (v0.3)

Lets an existing, human-written TestRail test case drive the same pipeline instead of an AC.md
file - built and tested against the **Steps template** specifically (structured `content`/
`expected` fields per step, TestRail's `custom_steps_separated`). A **Text-template** (freeform)
case isn't supported yet - `testrail_adapter.py` raises a clear `UnsupportedCaseError` if you point
it at one, rather than silently doing something wrong with it.

**Setup** (only needed for this path - the AC.md path needs none of this):
1. `pip install -r requirements.txt` now also installs `requests` and `python-dotenv`.
2. `cp .env.example .env` and fill in `TESTRAIL_URL`, `TESTRAIL_EMAIL`, `TESTRAIL_API_KEY` (a
   TestRail API key, not your login password, generated from your TestRail user profile).
3. Find the case ID from the TestRail UI - it's the number in the case URL/title (e.g. case
   "C4075" -> `--testrail-case 4075`, no `C` prefix).

**Scope of this first version, deliberately kept narrow:**
- Single case at a time, not a whole suite - simpler, and matches the one-scenario-per-run pattern
  the AC.md path already uses. Bulk suite ingestion (with pagination past TestRail's 250-per-page
  limit) is a natural next step if this proves out.
- Steps-template cases only. If your team's cases mix templates, this will cleanly reject anything
  written in Text template rather than guessing at freeform text - check which template a given
  case uses in TestRail before pointing this at it.
- Generated scenario names are prefixed `tr<case_id>_` (e.g. `tr4075_successfully_login`) so
  `generated/` files trace back to their TestRail source at a glance.

## Open items / things to sanity-check together on the first real run

- **Cost model**: Claude Code usage now draws from your Pro plan's included monthly credit pool
  rather than a separate pay-per-token key. `cli.py` prints the running session cost
  (`total_cost_usd` from Claude Code's own output) after each attempt so you can watch it.
- **`stream-json` event schema isn't fully published by Anthropic** - `validator.py`'s
  `_extract_snapshot_text` walks the event tree defensively (looking for `tool_result`-shaped
  dicts anywhere, rather than assuming one exact nesting path) specifically because of that. If a
  future Claude Code version changes the shape enough to break this, the symptom will be
  locator-grounding checks failing on demonstrably-real locators - that's the place to look first.
- **Retry-on-failure default**: still `Settings.max_generation_retries` (2) in `config.py`, same as
  v0.1, now implemented via `claude --resume <session_id>` instead of resending the whole
  conversation - cheaper *and* keeps Claude Code's own context intact for the fix.
- I haven't been able to run this end-to-end against a live, authenticated Claude Code session
  from my side (no Pro login available in my environment) - `cli.py`'s file-reading and
  `validator.py`'s stream-json parsing are verified against a realistic fabricated session, but the
  first real run against your actual saucedemo login scenario is the real test.
- **v0.3 TestRail integration**: `testrail_adapter.py`'s case-to-manifest conversion is verified
  against fabricated data matching TestRail's documented API response shape (including a real
  example from TestRail's own docs), and the full orchestration up to the `claude` subprocess call
  is dry-run tested end-to-end. `testrail_client.py` itself has not been run against a real
  TestRail instance - the first real `--testrail-case` run is what actually proves the HTTP
  auth/request shape holds up, same caveat as the Claude Code side above.
