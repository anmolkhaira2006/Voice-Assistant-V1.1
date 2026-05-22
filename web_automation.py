# ============================================================================
#  web_automation.py — "The Web Hands"
# ============================================================================
#  Chintu Voice Assistant — Selenium Browser Automation
#
#  This module uses Selenium to control a real browser instance and perform
#  interactive web tasks that the user requests via voice:
#
#    • Check Gmail and read the latest email subject/sender
#    • Search YouTube and play a video
#    • Open any website and interact with it
#    • Perform Google searches and read results
#    • Check WhatsApp Web notifications
#
#  IMPORTANT: This module uses the user's EXISTING browser profile, so
#  they are already logged in to their accounts.  No credentials are
#  stored or handled by Chintu.
#
#  On Kali Linux, Firefox ESR is the default browser, so we use
#  GeckoDriver (Firefox) as the primary driver, with Chrome as fallback.
# ============================================================================

import os
import sys
import time
import shutil
import subprocess
from typing import Optional

# Selenium imports — graceful fallback if not installed
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException, NoSuchElementException, WebDriverException
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


# ============================================================================
#  CONFIGURATION
# ============================================================================

# Maximum time to wait for page elements (seconds)
WAIT_TIMEOUT = 12

# Browser window size for automation
BROWSER_WIDTH  = 1280
BROWSER_HEIGHT = 900


# ============================================================================
#  BROWSER DRIVER MANAGEMENT
# ============================================================================

# Module-level driver instance — reused across calls to avoid repeatedly
# opening and closing browser windows.
_driver: Optional[object] = None


def _get_driver(headless: bool = False):
    """
    Get or create a Selenium WebDriver instance.

    Strategy:
      1. Try Firefox (default on Kali Linux) with user's existing profile
      2. Fall back to Chrome/Chromium

    The driver is cached at module level and reused for subsequent calls.
    """
    global _driver

    if not SELENIUM_AVAILABLE:
        return None

    # Reuse existing driver if it's still alive (and matches headless mode roughly)
    if _driver is not None:
        try:
            _ = _driver.title  # Quick health check
            return _driver
        except Exception:
            _driver = None  # Driver is dead, create a new one

    # ── Try Firefox first (Kali Linux default) ──────────────────────────
    _driver = _try_firefox(headless=headless)
    if _driver:
        return _driver

    # ── Try Chrome/Chromium as fallback ─────────────────────────────────
    _driver = _try_chrome(headless=headless)
    return _driver


def _try_firefox(headless: bool = False):
    """
    Attempt to create a Firefox WebDriver using the user's default profile.
    This preserves login sessions so the user doesn't need to re-authenticate.
    """
    try:
        options = FirefoxOptions()

        # Use the user's existing Firefox profile to preserve logins
        # On Kali, the default profile is usually in ~/.mozilla/firefox/
        firefox_dir = os.path.expanduser("~/.mozilla/firefox")
        if os.path.isdir(firefox_dir):
            # Find the default profile directory
            for entry in os.listdir(firefox_dir):
                full_path = os.path.join(firefox_dir, entry)
                if os.path.isdir(full_path) and entry.endswith(".default-esr"):
                    options.profile = full_path
                    break
                elif os.path.isdir(full_path) and ".default" in entry:
                    options.profile = full_path
                    break

        options.add_argument(f"--width={BROWSER_WIDTH}")
        options.add_argument(f"--height={BROWSER_HEIGHT}")
        if headless:
            options.add_argument("--headless")

        driver = webdriver.Firefox(options=options)
        driver.set_page_load_timeout(30)
        return driver

    except Exception:
        return None


def _try_chrome(headless: bool = False):
    """
    Attempt to create a Chrome/Chromium WebDriver with user profile.
    """
    try:
        options = ChromeOptions()

        # Use existing Chrome/Chromium profile
        chrome_profile = os.path.expanduser("~/.config/google-chrome")
        chromium_profile = os.path.expanduser("~/.config/chromium")

        if os.path.isdir(chrome_profile):
            options.add_argument(f"--user-data-dir={chrome_profile}")
        elif os.path.isdir(chromium_profile):
            options.add_argument(f"--user-data-dir={chromium_profile}")

        options.add_argument(f"--window-size={BROWSER_WIDTH},{BROWSER_HEIGHT}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        if headless:
            options.add_argument("--headless")

        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        return driver

    except Exception:
        return None


def close_driver():
    """Gracefully close the browser driver if it's open."""
    global _driver
    if _driver is not None:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None


# ============================================================================
#  WEB TASK ROUTER
# ============================================================================

def perform_web_task(task_description: str) -> str:
    """
    Route a web task description to the appropriate handler function.

    Parameters
    ----------
    task_description : str
        Lowercase description of the web task to perform.

    Returns
    -------
    str
        Result message for UI display.
    """
    if not SELENIUM_AVAILABLE:
        return ("[ERROR] Selenium not installed. "
                "Run: pip install selenium")

    task = task_description.strip().lower()

    # ── Gmail ───────────────────────────────────────────────────────────
    if _match(task, ["check gmail", "check my gmail", "check email",
                     "check my email", "read email", "read my email",
                     "gmail check karo", "email check karo",
                     "gmail kholo", "email dikhao",
                     "read last email", "last email",
                     "latest email", "new email",
                     "inbox check karo"]):
        return _task_check_gmail()

    # ── YouTube ─────────────────────────────────────────────────────────
    if _starts(task, ["youtube search ", "youtube pe ", "youtube par ",
                      "play on youtube ", "youtube me dhundho ",
                      "youtube pe chalao "]):
        query = _after(task, ["youtube search ", "youtube pe ",
                              "youtube par ", "play on youtube ",
                              "youtube me dhundho ",
                              "youtube pe chalao "])
        return _task_youtube_search(query)

    if _match(task, ["open youtube", "youtube kholo"]):
        return _task_open_url("https://www.youtube.com", "YouTube")

    # ── WhatsApp Web ────────────────────────────────────────────────────
    if _match(task, ["check whatsapp", "whatsapp check karo",
                     "whatsapp kholo", "open whatsapp",
                     "whatsapp messages"]):
        return _task_open_url("https://web.whatsapp.com", "WhatsApp Web")

    # ── Twitter / X ─────────────────────────────────────────────────────
    if _match(task, ["check twitter", "open twitter", "twitter kholo",
                     "check x", "open x"]):
        return _task_open_url("https://x.com", "X (Twitter)")

    # ── Instagram ───────────────────────────────────────────────────────
    if _match(task, ["check instagram", "open instagram",
                     "instagram kholo"]):
        return _task_open_url("https://www.instagram.com", "Instagram")

    # ── GitHub ──────────────────────────────────────────────────────────
    if _match(task, ["open github", "github kholo", "check github"]):
        return _task_open_url("https://github.com", "GitHub")

    # ── Google Search ───────────────────────────────────────────────────
    if _starts(task, ["google search ", "google pe dhundho ",
                      "google pe search "]):
        query = _after(task, ["google search ", "google pe dhundho ",
                              "google pe search "])
        return _task_google_search(query)

    # ── Open arbitrary URL ──────────────────────────────────────────────
    if _starts(task, ["open website ", "open site ", "go to ",
                      "navigate to ", "website kholo "]):
        url = _after(task, ["open website ", "open site ", "go to ",
                            "navigate to ", "website kholo "])
        # Add https:// if no protocol specified
        if not url.startswith("http"):
            url = "https://" + url
        return _task_open_url(url, url)

    # ── Fallback: open the task description as a Google search ──────────
    return _task_google_search(task)


# ============================================================================
#  TASK IMPLEMENTATIONS
# ============================================================================

def _task_check_gmail() -> str:
    """
    Open Gmail in the browser and attempt to read the subject and sender
    of the most recent email.

    Relies on the user being logged in via their browser profile.
    """
    driver = _get_driver()
    if not driver:
        return "[ERROR] Could not start browser. Check driver installation."

    try:
        driver.get("https://mail.google.com/mail/u/0/#inbox")
        time.sleep(3)  # Allow Gmail to fully load (JS-heavy)

        # Wait for the inbox table to appear
        try:
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "tr.zA"))
            )
        except TimeoutException:
            # Might be a login page or different layout
            if "accounts.google.com" in driver.current_url:
                return ("[WEB] Gmail opened — please log in. "
                        "Your browser window is ready.")
            return "[WEB] Gmail opened. Could not auto-read inbox layout."

        # Find the first (latest) email row
        email_rows = driver.find_elements(By.CSS_SELECTOR, "tr.zA")
        if not email_rows:
            return "[WEB] Gmail inbox is empty."

        first_row = email_rows[0]

        # Extract sender name
        try:
            sender_el = first_row.find_element(By.CSS_SELECTOR, "span.bA4 span")
            sender = sender_el.get_attribute("name") or sender_el.text
        except NoSuchElementException:
            try:
                sender_el = first_row.find_element(By.CSS_SELECTOR, ".yX.xY span")
                sender = sender_el.text
            except NoSuchElementException:
                sender = "Unknown"

        # Extract subject
        try:
            subject_el = first_row.find_element(By.CSS_SELECTOR, "span.bog")
            subject = subject_el.text
        except NoSuchElementException:
            try:
                subject_el = first_row.find_element(By.CSS_SELECTOR, ".y6 span")
                subject = subject_el.text
            except NoSuchElementException:
                subject = "(no subject)"

        # Extract snippet / preview
        try:
            snippet_el = first_row.find_element(By.CSS_SELECTOR, "span.y2")
            snippet = snippet_el.text.strip(" -–—")
        except NoSuchElementException:
            snippet = ""

        # Check if unread
        is_unread = "zE" in (first_row.get_attribute("class") or "")
        status = "📩 UNREAD" if is_unread else "📧 Read"

        result = f"[GMAIL] {status} | From: {sender} | Subject: {subject}"
        if snippet:
            result += f" | {snippet[:50]}"

        return result

    except WebDriverException as exc:
        return f"[ERROR] Browser error: {str(exc)[:80]}"
    except Exception as exc:
        return f"[ERROR] Gmail check failed: {str(exc)[:80]}"


def _task_youtube_search(query: str) -> str:
    """
    Open YouTube and search for the given query.

    Parameters
    ----------
    query : str
        Search query for YouTube.
    """
    driver = _get_driver()
    if not driver:
        return "[ERROR] Could not start browser."

    try:
        import urllib.parse
        encoded = urllib.parse.quote_plus(query)
        driver.get(f"https://www.youtube.com/results?search_query={encoded}")

        # Wait for results to load
        try:
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "ytd-video-renderer, ytd-rich-item-renderer")
                )
            )
        except TimeoutException:
            return f"[WEB] YouTube opened for '{query}' — results loading..."

        # Get the title of the first result
        try:
            first_video = driver.find_element(
                By.CSS_SELECTOR,
                "ytd-video-renderer #video-title, ytd-rich-item-renderer #video-title"
            )
            title = first_video.text
            return f"[YOUTUBE] Top result: '{title}' for '{query}'"
        except NoSuchElementException:
            return f"[YOUTUBE] Searching for: '{query}'"

    except Exception as exc:
        return f"[ERROR] YouTube search failed: {str(exc)[:80]}"


def _task_google_search(query: str) -> str:
    """Perform a Google search and return the first result title."""
    driver = _get_driver()
    if not driver:
        return "[ERROR] Could not start browser."

    try:
        import urllib.parse
        encoded = urllib.parse.quote_plus(query)
        driver.get(f"https://www.google.com/search?q={encoded}")

        # Wait for results
        try:
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#search"))
            )
        except TimeoutException:
            return f"[WEB] Google search opened for: '{query}'"

        # Get the first result heading
        try:
            first_result = driver.find_element(By.CSS_SELECTOR, "#search h3")
            return f"[GOOGLE] Top result: '{first_result.text}' for '{query}'"
        except NoSuchElementException:
            return f"[GOOGLE] Searching for: '{query}'"

    except Exception as exc:
        return f"[ERROR] Search failed: {str(exc)[:80]}"


def _task_open_url(url: str, name: str) -> str:
    """
    Open a URL in the Selenium-controlled browser.

    Parameters
    ----------
    url : str
        The URL to navigate to.
    name : str
        Human-readable name for the site (for status display).
    """
    driver = _get_driver()
    if not driver:
        return f"[ERROR] Could not start browser for {name}."

    try:
        driver.get(url)

        # Wait for the page to have a title
        try:
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                lambda d: d.title and len(d.title) > 0
            )
            page_title = driver.title
            return f"[WEB] Opened {name} — {page_title}"
        except TimeoutException:
            return f"[WEB] Opened {name} — loading..."

    except Exception as exc:
        return f"[ERROR] Could not open {name}: {str(exc)[:80]}"


def scrape_gemini_command(query: str) -> str:
    """
    Invisibly scrape Gemini for a terminal command.
    Returns the extracted code block, or an error message.
    """
    # Force close any existing visible driver to avoid profile lock issues,
    # or just use the existing one if it's open.
    driver = _get_driver(headless=True)
    if not driver:
        return "[ERROR] Could not initialize WebDriver (check internet or browser installation)."

    try:
        driver.get("https://gemini.google.com/app")
        time.sleep(3) # Let UI settle

        # 1. Find input box and type query
        try:
            # Gemini's input is typically a rich-textarea div
            input_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.ql-editor[contenteditable='true'], textarea"))
            )
            input_box.clear()
            # Force the prompt to be strict
            strict_query = f"I need a linux terminal command. Reply ONLY with the raw bash code block, no markdown outside of it, no explanation. Task: {query}"
            input_box.send_keys(strict_query)
            input_box.send_keys(Keys.RETURN)
        except TimeoutException:
            return "[ERROR] Timeout waiting for Gemini input box. (Is Gemini blocked or asking for login?)"

        # 2. Wait for generation to finish. 
        # We wait for the generating animation to disappear, or just wait 12 seconds.
        time.sleep(12)

        # 3. Extract the last code block
        try:
            # Find all message contents
            messages = driver.find_elements(By.CSS_SELECTOR, "message-content, .message-content, sn-message-content")
            if not messages:
                return ""
            
            last_message = messages[-1]
            # Try to find a code block
            code_blocks = last_message.find_elements(By.CSS_SELECTOR, "pre code, code")
            if code_blocks:
                # Return the longest code block (avoids inline code snippets)
                code_text = max([cb.text for cb in code_blocks], key=len)
                return code_text.strip()
            
            # Fallback: return the whole text if no code block
            return last_message.text.strip()
            
        except NoSuchElementException:
            return "[ERROR] Could not find code block in Gemini response."

    except Exception as exc:
        return f"[ERROR] Unexpected scraping error: {str(exc)[:100]}"

def scrape_gemini_text(query: str) -> str:
    """
    Invisibly scrape Gemini for a general text response.
    Returns the extracted text, or an error message.
    """
    driver = _get_driver(headless=True)
    if not driver:
        return "[ERROR] Could not initialize WebDriver (check internet or browser installation)."

    try:
        driver.get("https://gemini.google.com/app")
        time.sleep(3) # Let UI settle

        # 1. Find input box and type query
        try:
            input_box = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.ql-editor[contenteditable='true'], textarea"))
            )
            input_box.clear()
            # Send the exact query without forcing it to be a bash script
            input_box.send_keys(query)
            input_box.send_keys(Keys.RETURN)
        except TimeoutException:
            return "[ERROR] Timeout waiting for Gemini input box. (Is Gemini blocked or asking for login?)"

        # 2. Wait for generation to finish. 
        time.sleep(15) # Increased wait time to 15s for slower connections

        # 3. Extract the last message block
        try:
            messages = driver.find_elements(By.CSS_SELECTOR, "message-content, .message-content, sn-message-content")
            if not messages:
                return ""
            last_message = messages[-1]
            return last_message.text.strip()
        except NoSuchElementException:
            return "[ERROR] Could not find the response text in Gemini's UI."

    except Exception as exc:
        return f"[ERROR] Unexpected scraping error: {str(exc)[:100]}"


# ============================================================================
#  MATCHING UTILITIES (local to this module)
# ============================================================================

def _match(text: str, patterns: list[str]) -> bool:
    """Return True if any pattern is a substring of text."""
    return any(p in text for p in patterns)


def _starts(text: str, prefixes: list[str]) -> bool:
    """Return True if text starts with any prefix."""
    return any(text.startswith(p) for p in prefixes)


def _after(text: str, prefixes: list[str]) -> str:
    """Extract text after the first matching prefix."""
    for prefix in prefixes:
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text.strip()
