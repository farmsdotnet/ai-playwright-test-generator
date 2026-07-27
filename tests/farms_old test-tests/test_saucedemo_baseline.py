from playwright.sync_api import sync_playwright
from src.pages import LoginPage


def test_valid_user_login():
    # Explicitly launch the browser session without depending on fixtures
    with sync_playwright() as p:
        # Launch headed so you can visually watch it click through fields
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        context = browser.new_context()
        page = context.new_page()

        try:
            # Execute your standard POM logic
            login_page = LoginPage(page)
            login_page.login("standard_user", "secret_sauce")

            # Assert success criteria
            assert "inventory.html" in page.url, f"❌ Redirection failed. Current URL: {page.url}"
            print("🚀 SauceDemo baseline test passed perfectly!")

        finally:
            # Clean up the local window session
            context.close()
            browser.close()
