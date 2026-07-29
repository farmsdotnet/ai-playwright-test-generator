from playwright.sync_api import sync_playwright, expect

from page_objects.tr46_verify_inventory_products_sort_functionality_page import (
    InventoryPage,
    LoginPage,
)

BASE_URL = "https://www.saucedemo.com/"


def test_tr46_verify_inventory_products_sort_functionality():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()

        login_page = LoginPage(page)
        inventory_page = InventoryPage(page)

        # step 1: Navigate to https://www.saucedemo.com -> login page displayed with associated elements
        login_page.navigate(BASE_URL)
        expect(page.get_by_role("button", name="Login")).to_be_visible()

        # step 2: Enter the username "standard_user" into the username field -> input accepted into field
        login_page.enter_username("standard_user")
        expect(page.get_by_role("textbox", name="Username")).to_have_value("standard_user")

        # step 3: Enter the password "secret_sauce" into the password field -> input accepted into field
        login_page.enter_password("secret_sauce")
        expect(page.get_by_role("textbox", name="Password")).to_have_value("secret_sauce")

        # step 4: Click the Login button -> Products Inventory page displayed at https://www.saucedemo.com/inventory.html
        login_page.click_login()
        expect(page).to_have_url("https://www.saucedemo.com/inventory.html")

        # step 5: Click the Sort Products Dropdown 'Name [Z to A]' -> second item displayed contains text 'Sauce Labs Onesie'
        inventory_page.select_sort_option("Name (Z to A)")
        expect(inventory_page.second_item_name_locator()).to_have_text("Sauce Labs Onesie")

        browser.close()
