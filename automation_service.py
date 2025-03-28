# automation_service.py
# Uses Playwright to log in to OTF Portal and get attendance.

import os
import logging
import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from urllib.parse import urljoin

# --- Configuration ---
OTF_LOGIN_START_URL = os.environ.get("OTF_LOGIN_START_URL", "https://myapplications.microsoft.com/")
EXPECTED_POST_LOGIN_URL_PATTERN = os.environ.get("OTF_POST_LOGIN_URL_PATTERN", "**/myapplications.microsoft.com/**") # Adjust pattern!
STUDIO_PERFORMANCE_URL = os.environ.get("OTF_STUDIO_PERFORMANCE_URL", "") # IMPORTANT: Find direct link if possible.  Start with empty and update.

# --- SELECTORS (CRITICAL - MUST BE FOUND MANUALLY VIA BROWSER INSPECT) ---
EMAIL_INPUT_SELECTOR = os.environ.get("SELECTOR_EMAIL_INPUT", "#i0116") # Placeholder - VERIFY
NEXT_BUTTON_SELECTOR = os.environ.get("SELECTOR_NEXT_BUTTON", "#idSIButton9") # Placeholder - VERIFY
PASSWORD_INPUT_SELECTOR = os.environ.get("SELECTOR_PASSWORD_INPUT", "#i0118") # Placeholder - VERIFY
SIGNIN_BUTTON_SELECTOR = os.environ.get("SELECTOR_SIGNIN_BUTTON", "#idSIButton9") # Placeholder - VERIFY
POST_LOGIN_CONFIRM_SELECTOR = os.environ.get("SELECTOR_POST_LOGIN_CONFIRM", "#mectrl_main_body") # Placeholder - VERIFY

STUDIO_DROPDOWN_SELECTOR = os.environ.get("SELECTOR_STUDIO_DROPDOWN", "") # Placeholder - VERIFY
CLASS_ATTENDANCE_TAB_SELECTOR = os.environ.get("SELECTOR_ATTENDANCE_TAB", "") # Placeholder - VERIFY
DATE_RANGE_SELECTOR_YESTERDAY = os.environ.get("SELECTOR_DATE_RANGE_YESTERDAY", "") # Placeholder - VERIFY
TOTAL_ATTENDANCE_VALUE_SELECTOR = os.environ.get("SELECTOR_ATTENDANCE_VALUE", "") # Placeholder - VERIFY
STUDIO_SELECT_VALUE = os.environ.get("STUDIO_SELECT_VALUE", "0134")
# ------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def get_attendance_via_playwright(username, password, studio_id, target_date):
    """
    Uses Playwright to log in to OTF Portal, navigate to the Studio Performance
    section, and extract the total attendance for a given date.

    Args:
        username (str): The username for the OTF portal.
        password (str): The password for the OTF portal.
        studio_id (str): The ID of the studio to retrieve attendance for.
        target_date (datetime.date): The date for which to retrieve attendance.

    Returns:
        int: The total attendance for the specified studio and date.

    Raises:
        ValueError: If username or password is not provided, or if the STUDIO_PERFORMANCE_URL is not configured.
        ConnectionError: If there is an error during the Playwright automation process,
                         including login failures, navigation issues, or if the attendance
                         data cannot be found.
    """
    if not username or not password:
        raise ValueError("Username and Password are required.")
    if not STUDIO_PERFORMANCE_URL:
        raise ValueError("STUDIO_PERFORMANCE_URL configuration is missing.  Please set the OTF_STUDIO_PERFORMANCE_URL environment variable.")

    date_str = target_date.strftime('%Y-%m-%d') # Or format needed by portal
    logging.info(f"Requesting attendance: Studio {studio_id}, Date {date_str}")

    # Check if critical selectors have been updated from placeholders
    if any(not sel or sel.startswith("#") for sel in [
        EMAIL_INPUT_SELECTOR, NEXT_BUTTON_SELECTOR, PASSWORD_INPUT_SELECTOR, SIGNIN_BUTTON_SELECTOR,
        POST_LOGIN_CONFIRM_SELECTOR, STUDIO_DROPDOWN_SELECTOR, CLASS_ATTENDANCE_TAB_SELECTOR,
        DATE_RANGE_SELECTOR_YESTERDAY, TOTAL_ATTENDANCE_VALUE_SELECTOR
    ]):
        logging.warning("Critical selectors may be missing or placeholders. Update them by inspecting the OTF Portal pages.  Automation may fail.")

    with sync_playwright() as p:
        browser = None
        try:
            # Launch browser
            browser = p.chromium.launch(headless=True, timeout=60000)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",  # Realistic UA
            )
            page = context.new_page()
            page.set_default_navigation_timeout(60000)  # 60 seconds
            page.set_default_timeout(30000)  # 30 seconds for most actions

            logging.info(f"Navigating to login: {OTF_LOGIN_START_URL}")
            page.goto(OTF_LOGIN_START_URL, wait_until='domcontentloaded')

            # --- Login ---
            logging.info("Entering username...")
            page.locator(EMAIL_INPUT_SELECTOR).wait_for(state='visible')
            page.locator(EMAIL_INPUT_SELECTOR).fill(username)
            page.locator(NEXT_BUTTON_SELECTOR).click()

            logging.info("Entering password...")
            page.locator(PASSWORD_INPUT_SELECTOR).wait_for(state='visible')
            page.locator(PASSWORD_INPUT_SELECTOR).fill(password)
            page.locator(SIGNIN_BUTTON_SELECTOR).click()

            # --- Login Confirmation / MFA Handling ---
            logging.info("Waiting for post-login confirmation...")
            try:
                page.locator(POST_LOGIN_CONFIRM_SELECTOR).wait_for(state='visible')
                logging.info("Login successful.")
            except PlaywrightTimeoutError:
                #  Handle MFA if needed.  This is a complex area, and may require manual intervention
                #  or more sophisticated logic (e.g., checking for specific MFA prompts).
                logging.error("Timeout waiting for confirmation after login.  MFA may be required, or login failed.")
                raise ConnectionError("Login failed or timed out.  Check credentials and MFA handling.")

            # --- Navigate to Studio Performance ---
            logging.info(f"Navigating to Studio Performance: {STUDIO_PERFORMANCE_URL}")
            page.goto(STUDIO_PERFORMANCE_URL, wait_until='domcontentloaded')

            # --- Interact with Studio Performance page ---
            logging.info("Interacting with Studio Performance page...")

            # Select Studio from dropdown
            page.locator(STUDIO_DROPDOWN_SELECTOR).wait_for(state='visible')
            page.select_option(STUDIO_DROPDOWN_SELECTOR, value=studio_id)
            logging.info(f"Selected studio: {studio_id}")

            # Select "Class Attendance" tab
            page.locator(CLASS_ATTENDANCE_TAB_SELECTOR).wait_for(state='visible')
            page.click(CLASS_ATTENDANCE_TAB_SELECTOR)
            logging.info("Clicked 'Class Attendance' tab")

            # Select date range: 'Yesterday'
            page.locator(DATE_RANGE_SELECTOR_YESTERDAY).wait_for(state='visible')
            page.click(DATE_RANGE_SELECTOR_YESTERDAY)
            logging.info("Selected date range: 'Yesterday'")

            # Wait for the attendance value to be visible and extract it
            attendance_element = page.locator(TOTAL_ATTENDANCE_VALUE_SELECTOR)
            attendance_element.wait_for(state='visible')
            attendance_text = attendance_element.text_content()
            logging.info(f"Extracted attendance text: '{attendance_text}'")

            # Clean and convert the extracted text to an integer
            cleaned_text = ''.join(filter(str.isdigit, attendance_text))
            if not cleaned_text:
                raise ValueError(f"Could not extract a valid attendance number from the page.  Text found: '{attendance_text}'")
            attendance_figure = int(cleaned_text)
            logging.info(f"Extracted attendance: {attendance_figure}")
            return attendance_figure

        except PlaywrightTimeoutError as te:
            logging.error(f"Playwright timeout: {te}")
            raise ConnectionError(f"Timeout during browser automation: {te}")
        except PlaywrightError as pe:
            logging.error(f"Playwright error: {pe}")
            raise ConnectionError(f"Error during browser automation: {pe}")
        except Exception as e:
            logging.exception(f"Unexpected error: {e}")
            raise ConnectionError(f"An unexpected error occurred during automation: {e}")
        finally:
            if browser:
                logging.info("Closing browser.")
                browser.close()

