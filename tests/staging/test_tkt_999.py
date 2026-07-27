from playwright.sync_api import sync_playwright
from src.pages import LoginPage
# End of automated imports

def test_tkt_999():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        context = browser.new_context()
        page = context.new_page()
        try:
            # Navigate to login page
            LoginPage(page).navigate()
            # Login with invalid credentials
            LoginPage(page).login("locked_out_user", "secret_sauce")
            # Assert error message is displayed
            assert page.locator(".error-message-container").is_visible(), "Error message should be displayed"
            print("🚀 Test executed successfully!")
        finally:
            context.close()
            browser.close()
