from playwright.sync_api import Page
from src.pages.base_page import BasePage


class LoginPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        # Raw locator string registry for strict programmatic AST editing
        self.username_selector = '[data-test="username"]'
        self.password_selector = '[data-test="password"]'
        self.login_button_selector = '[data-test="login-button"]'
        self.error_message_selector = '[data-test="error"]'

    def login(self, username, password):
        self.navigate()
        self.page.locator(self.username_selector).fill(username)
        self.page.locator(self.password_selector).fill(password)
        self.page.locator(self.login_button_selector).click()

    def enter_username(self, username):
        self.page.locator(self.username_selector).fill(username)

    def enter_password(self, password):
        self.page.locator(self.password_selector).fill(password)

    def click_login(self):
        self.page.locator(self.login_button_selector).click()
