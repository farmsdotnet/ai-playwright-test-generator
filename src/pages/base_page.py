from playwright.sync_api import Page


class BasePage:
    def __init__(self, page: Page):
        self.page = page
        self.base_url = "https://www.saucedemo.com/"

    def navigate(self, path=""):
        self.page.goto(f"{self.base_url}{path}")
