# Utils.py
# Robust Selenium table extractors + Windows-safe filenames
# (drop-in replacement for the earlier Utils.py)

import re
import os
import csv
import glob
import time
import shutil
import pandas as pd
from logging.config import fileConfig  # left as-is for compatibility
from requests.adapters import HTTPAdapter  # unused, kept for compatibility
from urllib3.util import Retry  # unused, kept for compatibility

from selenium import webdriver  # noqa: F401 (imported elsewhere in the project)
from selenium.common.exceptions import NoSuchElementException  # noqa: F401
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

MAX_RELOADS = 3
SLEEP_TIME = 5

# ---- Windows-safe filename sanitizer ----
# Removes illegal characters and control chars; trims/truncates long names.
_ILLEGAL = r'[<>:"/\\|?*\x00-\x1f]'
def _sanitize_filename(s: str, max_len: int = 150) -> str:
    s = re.sub(_ILLEGAL, '', str(s))
    s = re.sub(r'\s+', ' ', s).strip().rstrip('. ')
    return s[:max_len]


class SeleniumScrappingUtils(object):
    def __init__(self):
        pass

    # ---------- Generic helpers ----------

    @staticmethod
    def get_tender_id(path):
        """Return tender ids where stage == 'AOC' from a CSV."""
        dataframe = pd.read_csv(path)
        tender_id = dataframe["tender.id"][dataframe['tender.stage'] == "AOC"]
        return tender_id

    @staticmethod
    def get_multiple_page_elements(browser, xpath=None):
        """Return list of elements located by the given XPath."""
        return WebDriverWait(browser, SLEEP_TIME).until(
            EC.presence_of_all_elements_located((By.XPATH, xpath))
        )

    @staticmethod
    def get_page_element(browser, xpath=None):
        """Return a single element located by the given XPath."""
        return WebDriverWait(browser, SLEEP_TIME).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )

    @staticmethod
    def input_text_box(browser, select_element, text=None):
        """Type text into an <input> or <textarea> element."""
        select_element.send_keys(text)

    @staticmethod
    def save_image_as_png(image_element):
        """Save a web element (e.g., captcha) as PNG."""
        with open('captcha_image.png', 'wb') as file:
            file.write(image_element.screenshot_as_png)

    @staticmethod
    def get_text_from_element(elements):
        """Return .text for each element in a list."""
        return [el.text for el in elements]

    # ---------- Table extractors ----------

    @staticmethod
    def extract_vertical_table(table_section, name_of_file, skip_header_number=None):
        """
        Extract vertical tables (each row already has columns).
        Writes all <tr> rows, capturing both <th> and <td>.
        """
        safe = _sanitize_filename(name_of_file)
        start = skip_header_number or 0

        with open(f"{safe}.csv", 'w', newline='', encoding='utf-8-sig') as csvfile:
            wr = csv.writer(csvfile)
            rows = table_section.find_elements(By.CSS_SELECTOR, 'tr')
            for row in rows[start:]:
                cells = row.find_elements(By.CSS_SELECTOR, 'th,td')
                wr.writerow([c.get_attribute('textContent').strip() for c in cells])

    @staticmethod
    def extract_horizontal_table(table_section, name_of_file, skip_header_number=None):
        """
        Extract horizontal key/value tables of the form:
            key1, value1, key2, value2, ...
        Robust to:
          - mixed <th>/<td>
          - multiple <tbody> blocks
          - odd number of cells (pads last value)
        Output CSV has 2 rows: first row = keys, second row = values.
        """
        safe = _sanitize_filename(name_of_file)
        start = skip_header_number or 0

        keys, vals = [], []

        # Some pages wrap rows in <tbody>, some don't.
        bodies = table_section.find_elements(By.CSS_SELECTOR, "tbody")
        if not bodies:
            bodies = [table_section]

        for body in bodies:
            trs = body.find_elements(By.CSS_SELECTOR, "tr")
            for tr in trs[start:]:
                cells = tr.find_elements(By.CSS_SELECTOR, "th,td")
                buff = [c.get_attribute('textContent').strip() for c in cells]

                # Pair successive cells into (key, value)
                if len(buff) % 2 == 1:
                    buff.append('')  # pad missing value
                for i in range(0, len(buff), 2):
                    keys.append(buff[i])
                    vals.append(buff[i + 1])

        # Normalize lengths just in case
        if len(vals) < len(keys):
            vals += [''] * (len(keys) - len(vals))
        elif len(keys) < len(vals):
            keys += [''] * (len(vals) - len(keys))

        with open(f"{safe}.csv", 'w', newline='', encoding='utf-8-sig') as csvfile:
            wr = csv.writer(csvfile)
            wr.writerow(keys)
            wr.writerow(vals)

    # ---------- CSV post-processing ----------

    @staticmethod
    def concatinate_csvs(path_to_save, name_of_file, tender_status):
        """
        Combine all CSVs in the current working directory into one wide CSV (axis=1),
        append a 'Tender Stage' column, and save to `path_to_save/name_of_file.csv`.
        """
        all_filenames = [i for i in glob.glob('*.csv')]
        if not all_filenames:
            raise FileNotFoundError("No CSVs found to concatenate in the current directory.")

        combined_csv = pd.concat([pd.read_csv(f) for f in all_filenames], axis=1)
        combined_csv['Tender Stage'] = tender_status

        os.makedirs(path_to_save, exist_ok=True)
        out_path = os.path.join(path_to_save, f"{_sanitize_filename(name_of_file)}.csv")
        combined_csv.to_csv(out_path, index=False, encoding='utf-8-sig')

    @staticmethod
    def remove_csvs(directory):
        """Delete all CSV files in `directory`."""
        for file in os.listdir(directory):
            if file.endswith(".csv"):
                os.remove(os.path.join(directory, file))

    @staticmethod
    def is_file_downloaded(filename_glob, timeout=500):
        """
        Wait (up to timeout seconds) until a file matching `filename_glob` appears.
        Example: r'C:\\Downloads\\tender_*.pdf'
        """
        end_time = time.time() + timeout
        while not glob.glob(filename_glob):
            time.sleep(1)
            if time.time() > end_time:
                print("File not found within time")
                return False
        print("File found")
        return True

    @staticmethod
    def select_drop_down(browser, xpath, value):
        """Select an <option> by value from a <select> found via XPath."""
        selected_element = Select(browser.find_element(By.XPATH, xpath))
        selected_element.select_by_value(value)
