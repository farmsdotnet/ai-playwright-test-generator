# Contains Core Business Logic, Rules, Standards 

website info = basic retail e-commerce application which provides users ability to login, peruse the availble products and add / remove items from cart.

## Application Architecture
# Global Domain Rules & Framework Architecture

## Target Application
- Base URL: https://www.saucedemo.com/
- Core application identity: Swag Labs E-Commerce Portal

## Framework Guidelines
- Language: Python 3.x using Pytest test runner
- Library: Playwright (sync API)
- Pattern: Strict Page Object Model (POM)

## Code Generation Requirements
- Always import page classes from `src.pages.login_page` or `src.pages.base_page`.
- Use the standard `page` fixture provided natively by `pytest-playwright`.
- Never use hardcoded browser selectors inside test files.
- Tests should look structurally clean:

```python
from playwright.sync_api import Page
from src.pages import LoginPage


def test_example(page: Page):
    login_page = LoginPage(page)
    login_page.login("standard_user", "secret_sauce")
    # assert follows...
```

- Authentic login state is managed via `src/pages/login_page.py`

## Automation Constraints
- Use Page Object Model (POM) design patterns at all times.
- Never hardcode element selectors directly inside the test files. Use objects from `src.pages`.
- Assertions must use explicit, clear failure messages.

few basic details are shared below to assist the  AI test generator in getting started!
# baseurl = https://www.saucedemo.com/
## - default username = 'standard user' 
### - invalid username = 'sketchy_user' 
##  - other usernames:
###    - locked_out_user 
###    - problem_user 
###    - performance_glitch_user 
###    - error_user 
###    - visual_user

# Main Elements
- Username field
- Password Field
- Login button
- Page Title = 'Swag Labs'

-----

# Inventory_Page_URL = https://www.saucedemo.com/inventory.html
# Main Elements 
- links
- Prices ($)
- 'Add to cart' button
- pictures of each product listing
----
