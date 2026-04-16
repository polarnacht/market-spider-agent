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

# 获取调度参数
SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 100))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "Domestic_Live_Result.csv")

def init_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    options.add_argument(f'user-agent={ua}')
    chromium_path = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    chromedriver_path = shutil.which("chromedriver")
    service = Service(executable_path=chromedriver_path) if chromedriver_path else Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"})
    return driver

def scrape_domestic():
    print(f"Domestic Live Kernel Running: Target {SCRAPE_LIMIT}")
    driver = init_driver()
    url = "https://bojianger.com/category-base-statistic-month.html"
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        data_list = []
        page = 1
        
        while len(data_list) < SCRAPE_LIMIT:
            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "list")))
                time.sleep(3) # 给异步数值一点渲染时间
                items = driver.find_elements(By.CLASS_NAME, "list")
                
                for item in items:
                    if len(data_list) >= SCRAPE_LIMIT: break
                    
                    try:
                        name_tag = item.find_element(By.CSS_SELECTOR, ".text h3 a")
                        name = name_tag.get_attribute("textContent").strip()
                        
                        # 进度打印，适配 app.py 正则
                        print(f"[{len(data_list)+1}/{SCRAPE_LIMIT}] Processing: {name}")
                        
                        stats = {}
                        stat_items = item.find_elements(By.CSS_SELECTOR, ".list_rt li")
                        for li in stat_items:
                            txt = li.get_attribute("textContent")
                            val = li.find_element(By.TAG_NAME, "label").get_attribute("textContent") if li.find_elements(By.TAG_NAME, "label") else ""
                            if "活跃主播" in txt: stats["活跃主播"] = val
                            elif "活跃观众" in txt: stats["活跃观众"] = val
                            elif "礼物总值" in txt: stats["礼物总值"] = val
                            elif "平均时长" in txt: stats["平均时长"] = val

                        data_list.append({
                            "排名": len(data_list)+1,
                            "品类名称": name,
                            **stats
                        })
                    except: continue
                
                if len(data_list) < SCRAPE_LIMIT:
                    next_btn = driver.find_element(By.XPATH, "//a[contains(text(), '下一页')]")
                    if "disabled" in next_btn.get_attribute("class"): break
                    driver.execute_script("arguments[0].click();", next_btn)
                    page += 1
                    time.sleep(3)
                else: break
            except: break

        if data_list:
            df = pd.DataFrame(data_list)
            df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
            print(f"✅ Domestic Success: {OUTPUT_FILE}")
    finally: driver.quit()

if __name__ == "__main__": scrape_domestic()
