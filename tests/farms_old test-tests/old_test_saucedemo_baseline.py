from playwright.sync_api import Page
from src.pages import LoginPage


def test_valid_user_login(page: Page):
    # Initialize the page object matching your structure
    login_page = LoginPage(page)

    # Execute the login flow
    login_page.login("standard_user", "secret_sauce")

    # Verify successful redirection to the inventory landing page
    assert "inventory.html" in page.url, f"❌ Redirection failed. Current URL is: {page.url}"
