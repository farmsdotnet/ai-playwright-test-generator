from playwright.sync_api import Page
from src.pages import LoginPage

def test_invalid_login(page: Page):
    """
    Summary:
        This test case verifies that an invalid login attempt with a locked out user results in the correct error message being displayed.

    Steps:
        1. Navigate to the login page.
        2. Input 'locked_out_user' as the username and 'secret_sauce' as the password.
        3. Assert that the error container displays the expected validation message.
    """
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login("locked_out_user", "secret_sauce")
    
    # Assert that the error container displays a validation message
    error_message = page.locator(".error-button").text_content()
    assert error_message == "Epic sadface: Username and password do not match any user in this service", \
        f"Expected error message 'Epic sadface: Username and password do not match any user in this service', but got '{error_message}'"