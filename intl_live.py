import time
import pandas as pd
import os
import re
import sys
import shutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import warnings

warnings.filterwarnings("ignore")
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 100))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "Intl_Live_Result.csv")

def init_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    options.add_argument(f'user-agent={ua}')
    
    chromedriver_path = shutil.which("chromedriver")
    service = Service(executable_path=chromedriver_path) if chromedriver_path else Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"})
    return driver

def scrape_intl():
    print(f"Intl Live Kernel Running (Twitch): Target {SCRAPE_LIMIT}")
    driver = init_driver()
    try:
        driver.get("https://sullygnome.com/")
        wait = WebDriverWait(driver, 20)
        
        # 导航流程
        btn_games = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@href='/games']")))
        driver.execute_script("arguments[0].click();", btn_games)
        
        btn_30_days = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'SubheaderLinkContainer')]//a[contains(text(), '30 days')]")))
        driver.execute_script("arguments[0].click();", btn_30_days)
        
        btn_more = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'More most watched games')]")))
        driver.execute_script("arguments[0].click();", btn_more)
        
        data_list = []
        while len(data_list) < SCRAPE_LIMIT:
            wait.until(EC.presence_of_element_located((By.ID, "tblControl")))
            time.sleep(3)
            rows = driver.find_elements(By.CSS_SELECTOR, "#tblControl tbody tr")
            
            for row in rows:
                if len(data_list) >= SCRAPE_LIMIT: break
                cols = row.find_elements(By.TAG_NAME, "td")
                if not cols: continue
                
                name = cols[2].get_attribute("textContent").strip()
                print(f"[{len(data_list)+1}/{SCRAPE_LIMIT}] Processing Intl: {name}")
                
                data_list.append({
                    "排名": cols[0].get_attribute("textContent").strip(),
                    "游戏名称": name,
                    "观看时长(小时)": cols[3].get_attribute("textContent").strip(),
                    "峰值观众": cols[5].get_attribute("textContent").strip(),
                    "主播人数": cols[7].get_attribute("textContent").strip(),
                    "平均观众": cols[8].get_attribute("textContent").strip()
                })
            
            if len(data_list) < SCRAPE_LIMIT:
                try:
                    next_btn = driver.find_element(By.ID, "tblControl_next")
                    if "disabled" in next_btn.get_attribute("class"): break
                    driver.execute_script("arguments[0].click();", next_btn)
                    time.sleep(3)
                except: break
            else: break

        if data_list:
            pd.DataFrame(data_list).to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
            print(f"✅ Intl Success: {OUTPUT_FILE}")
    finally: driver.quit()

if __name__ == "__main__": scrape_intl()
