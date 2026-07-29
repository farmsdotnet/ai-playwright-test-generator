from playwright.sync_api import Page


class LoginPage:
    def __init__(self, page: Page):
        self.page = page

    def navigate(self, base_url: str):
        # step 1: Navigate to https://www.saucedemo.com
        self.page.goto(base_url)

    def enter_username(self, username: str):
        # step 2: Enter the username "standard_user" into the username field
        self.page.get_by_role("textbox", name="Username").fill(username)

    def enter_password(self, password: str):
        # step 3: Enter the password "secret_sauce" into the password field
        self.page.get_by_role("textbox", name="Password").fill(password)

    def click_login(self):
        # step 4: Click the Login button
        self.page.get_by_role("button", name="Login").click()


class InventoryPage:
    def __init__(self, page: Page):
        self.page = page

    def select_sort_option(self, option_label: str):
        # step 5: Click the Sort Products Dropdown 'Name [Z to A]'
        self.page.get_by_role("combobox").select_option(label=option_label)

    def second_item_name_locator(self):
        # step 5: locator used to verify second item displayed contains text 'Sauce Labs Onesie'
        return self.page.get_by_role("link").nth(3)
