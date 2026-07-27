import pytest
from playwright.sync_api import sync_playwright
from src.pages.m_i_s_sorting_page import MISSortingPage
from src.pages.login_page import LoginPage


def test_far_6():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        page = browser.new_page()

        m_i_s_sorting_page = MISSortingPage(page)
        login_page = LoginPage(page)

        login_page.login('standard_user', 'secret_sauce')
        m_i_s_sorting_page.sort_items_by_price('Low to High')
        m_i_s_sorting_page.verify_first_item('Sauce Labs Onesie', '$7.99')

        browser.close()
