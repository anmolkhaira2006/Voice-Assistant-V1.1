import time
from web_automation import _get_driver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException

driver = _get_driver(headless=True)
driver.get("https://gemini.google.com/app")

print("Waiting for input box...")
input_box = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "div.ql-editor[contenteditable='true'], textarea"))
)
input_box.clear()
input_box.send_keys("hello world in python")
input_box.send_keys(Keys.RETURN)

print("Sent query. Waiting 12 seconds...")
time.sleep(12)

messages = driver.find_elements(By.CSS_SELECTOR, "message-content, .message-content, sn-message-content")
print(f"Found {len(messages)} message content nodes")
if messages:
    print("Last message text:")
    print(repr(messages[-1].text.strip()))
else:
    print("No messages found. Taking screenshot of result.")
    driver.save_screenshot("error_result.png")
