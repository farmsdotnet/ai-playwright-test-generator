from playwright.sync_api import sync_playwright
from src.pages import LoginPage
# End of automated imports

def test_far_6():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        context = browser.new_context()
        page = context.new_page()
        try:
            login_page = LoginPage(page)
            login_page.login('standard_user', 'secret_sauce')
            page.goto('https://saucedemo.com/inventory.html')
            inventory_page = InventoryPage(page)
            inventory_page.sort_items_by_price_low_to_high()
            assert inventory_page.get_first_item_name() == "Sauce Labs Onesie"
            assert inventory_page.get_first_item_price() == "$7.99"
            print("🚀 Test executed successfully!")
        finally:
            context.close()
            browser.close()
