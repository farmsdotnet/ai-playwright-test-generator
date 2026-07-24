from playwright.sync_api import sync_playwright
from src.pages.login_page import LoginPage
# End of automated imports

def test_far_6():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        context = browser.new_context()
        page = context.new_page()
        try:
            browser = p.chromium.launch(headless=False, slow_mo=1000)
            page = browser.new_page()
            login_page = LoginPage(page)
            login_page.login('problem_user', 'secret_sauce')
            page.goto('https://saucedemo.com/inventory.html')
            assert "carry.allTheThings() with the sleek, streamlined Sly Pack that melds uncompromising style with unequaled laptop and tablet protection." in page.inner_text("div.inventory_item_description")
            browser.close()
            print("🚀 Test executed successfully!")
        finally:
            context.close()
            browser.close()
