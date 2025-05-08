from Utils import SeleniumScrappingUtils
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException
from captcha import captcha
import time 
import os
import warnings
import re
import sys
warnings.filterwarnings("ignore", category=DeprecationWarning) 
import pytesseract



# Alert handling function
def handle_alert(driver):
    try:
        alert = driver.switch_to.alert
        print("Alert text:", alert.text)  # Print the alert text

        alert.dismiss()  # alert.accept() #or 
        print("Alert dismissed.")
    except NoAlertPresentException:
        print("No alert present.")

# Set up Firefox options and Tesseract path
firefox_options = Options()
firefox_options.headless = True

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Initialize WebDriver
service = Service(r"C:\Users\saura\anaconda3\Scripts\geckodriver.exe")
browser = webdriver.Firefox(service=service)

# Open the portal
browser.get("https://hpsdma.nic.in/admnis/app/login.aspx")

def captcha_input(captcha_image_xpath, xpath_input_text):
    captcha_text = captcha(browser, captcha_image_xpath)
    captcha_input_element = SeleniumScrappingUtils.get_page_element(browser, xpath_input_text)
    SeleniumScrappingUtils.input_text_box(browser, captcha_input_element, captcha_text)
    time.sleep(3)
    button = browser.find_element(By.XPATH, "//*[@id='Button1']")
    
    button.click()
    time.sleep(3)
    # Handle alert if present
    handle_alert(browser)
    
    invalid_string = browser.find_elements(By.CLASS_NAME, "error")
    print(invalid_string)
    
    if len(invalid_string) == 0:
        pass
    else:
        while 'Please Enter Valid Security Code !!' in invalid_string[0].text:
            captcha_text = captcha(browser, captcha_image_xpath)
            captcha_input_element = SeleniumScrappingUtils.get_page_element(browser, xpath_input_text)
            SeleniumScrappingUtils.input_text_box(browser, captcha_input_element, captcha_text)
            time.sleep(3)
            
            button = browser.find_element(By.XPATH, "//*[@id='Button1']")
            WebDriverWait(browser, 10)
            button.click()
            
            # Handle alert if present
            handle_alert(browser)
            
            invalid_string = browser.find_elements(By.CLASS_NAME, "error")
            if len(invalid_string) == 0:
                break
            elif 'Invalid Captcha!' not in invalid_string[0].text:
                break

# Log in process
try:
    username = WebDriverWait(browser, 2).until(EC.presence_of_element_located((By.ID, "Uname")))
    password = browser.find_element(By.ID, "Pwd")
    
    # Enter credentials
    username.send_keys("hpsdma-hod@gmail.com")
    password.send_keys("ADMIN!@12")
    captcha_input('//*[@id="imgCaptcha"]', '//*[@id="CodeNumberTextBox"]')
    
    # Wait for login completion
    WebDriverWait(browser, 20).until(EC.presence_of_element_located((By.ID, "nav navbar-nav")))

    # Step 2: Navigate to the losses and damages page
    losses_damages_page = browser.find_element(By.LINK_TEXT, "Disaster ")
    losses_damages_page.click()

    # Step 3: Enter date range
    from_date = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "from_date_field")))
    to_date = browser.find_element(By.ID, "to_date_field")
    from_date.send_keys("2023-01-01")
    to_date.send_keys("2023-12-31")
    to_date.send_keys(Keys.RETURN)

    # Step 4: Download the file
    download_button = WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.ID, "download_icon")))
    download_button.click()

    # Wait for download completion
    time.sleep(5)

finally:
    browser.quit()  # Close the driver

print("Download complete!")
