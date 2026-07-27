# Global Domain Rules & Framework Architecture

NOTE TO AI - ALL RULES IN THIS FILE MUST BE ADHERED TO WITHOUT EXCEPTION

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

## AUTOMATED DYNAMIC POM GENERATION RULES
- If a specific page view or component class does not yet exist in `src/pages/`, it must be created as a standalone file.
- All dynamically generated page classes must inherit from `BasePage` and call `super().__init__(page)`.
- Use snake_case for filenames (e.g., `inventory_page.py`) and PascalCase for class names (e.g., `InventoryPage`).
- Always leverage clear data attribute elements (such as `[data-test="..."]`) for selector layouts.
- Example structure for new page modules:
  ```python
  from playwright.sync_api import Page
  from src.pages import BasePage

  class TargetPage(BasePage):
      def __init__(self, page: Page):
          super().__init__(page)
          # Locators belong here
  ```
## CORE SELF-HEALING DETERMINATION RULES
- Your generated test scripts must pass execution with an absolute zero error and zero warning threshold.
- If a script throws a runtime exception (`AttributeError`, `TypeError`, `NameError`, etc.), you must refactor the method calls to strictly align with the physical properties defined in the Page Object source files.
- Never reference locators or class attributes that are not explicitly initialized in the `__init__` constructor of the provided POM reference block.

## CRITICAL FUNCTION SIGNATURE RULES
- All test functions must have a completely empty signature block.
- NEVER include parameters, fixtures, or arguments inside the test function parentheses.
- CORRECT: `def test_tkt_999():`
- INCORRECT: `def test_tkt_999(page):`
- INCORRECT: `def test_tkt_999(page: Page):`