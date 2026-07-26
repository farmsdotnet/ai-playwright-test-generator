from playwright.sync_api import Page
from src.pages.base_page import BasePage

class LoginPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        # Selectors using SauceDemo standard data attributes
        self.username_input = page.locator('[data-test="username"]')
        self.password_input = page.locator('[data-test="password"]')
        self.login_button = page.locator('[data-test="login-button"]')
        self.error_message = page.locator('[data-test="error"]')

    def login(self, username, password):
        self.navigate()
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.login_button.click()

    def enter_username(self, username):
        self.page.locator('[data-test="username"]').fill(username)

    def enter_password(self, password):
        self.page.locator('[data-test="password"]').fill(password)

    def click_login(self):
        self.page.locator('[data-test="login-button"]').click()
