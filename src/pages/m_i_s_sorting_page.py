from playwright.sync_api import Page
from src.pages.base_page import BasePage

class MISSortingPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.header_container = '[data-test="header-container"]'
        self.primary_header = '[data-test="primary-header"]'
        self.react_burger_menu_btn = '#react-burger-menu-btn'
        self.inventory_sidebar_link = '[data-test="inventory-sidebar-link"]'
        self.about_sidebar_link = '[data-test="about-sidebar-link"]'
        self.logout_sidebar_link = '[data-test="logout-sidebar-link"]'
        self.reset_sidebar_link = '[data-test="reset-sidebar-link"]'
        self.react_burger_cross_btn = '#react-burger-cross-btn'
        self.shopping_cart_link = '[data-test="shopping-cart-link"]'
        self.secondary_header = '[data-test="secondary-header"]'
        self.title = '[data-test="title"]'
        self.active_option = '[data-test="active-option"]'
        self.product_sort_container = '[data-test="product-sort-container"]'

    def __init__(self, page)(self):
        self.page.locator(self.page).click()

    def navigate_to_menu(self)(self):
        self.page.locator(self.#react-burger-menu-btn).click()

    def close_menu(self)(self):
        self.page.locator(self.#react-burger-cross-btn).click()

    def select_sort_option(self, option)(self):
        self.page.locator(self.[data-test="product-sort-container"]).click()