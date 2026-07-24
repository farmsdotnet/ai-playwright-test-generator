# Global Domain Rules & Framework Architecture

## Target Application
- ALWAYS USE the SPECIFIED Base URL here: https://saucedemo.com
- Core application identity: Swag Labs E-Commerce Portal
- Authentic login state is managed via `src/pages/login_page.py`

## Linear Board
- ALWAYS explicitly use the Acceptance Criteria (aka AC) taken from the Linear Tkt to generate ALL NEW Tests!!!!

## Framework Guidelines
- Language: Python 3.x using Pytest test runner
- Library: Playwright (sync API)
- Pattern: Strict Page Object Model (POM)

## Automation & Code Constraints
- Use Page Object Model (POM) design patterns at all times.
- Never hardcode element selectors directly inside the test files. Use objects from `src.pages`.
- Assertions must use explicit, clear failure messages.
- Always import page classes from `src.pages.login_page` or `src.pages.base_page`.

## CRITICAL FUNCTION SIGNATURE RULES
- All test functions must have a completely empty signature block.
- NEVER include parameters, fixtures, or arguments inside the test function parentheses.
- CORRECT: `def test_tkt_999():`
- INCORRECT: `def test_tkt_999(page):`
- INCORRECT: `def test_tkt_999(page: Page):`

## PLAYWRIGHT RUNTIME OBJECTS
- Do not use Pytest `page` fixtures. 
- Always instantiate the browser manually inside the function body using a `with sync_playwright() as p:` context wrapper block.
- Name the browser view variable `page` so that POM initializers like `LoginPage(page)` function correctly.
- Headless execution must be set to False: `browser = p.chromium.launch(headless=False, slow_mo=1000)`
