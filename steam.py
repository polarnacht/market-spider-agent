import time
import re
import pandas as pd
import os
import sys
import shutil
import warnings
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === 彻底屏蔽干扰日志并强制 UTF-8 输出 ===
warnings.filterwarnings("ignore")
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# === 环境变量读取 (由指挥官 app.py 传参) ===
SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 5))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "Steam_Result.csv")

def get_stealth_driver():
    """
    构造适配云端 Linux 环境的隐身驱动器，并强制对齐系统路径
    """
    options = Options()
    # 1. 云端运行必备参数
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # 2. 模拟真实高分屏特征
    options.add_argument("--force-device-scale-factor=1")
    
    # 3. 抹除自动化痕迹
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.experimental_options["excludeSwitches"] = ["enable-automation"]
    options.experimental_options["useAutomationExtension"] = False
    
    # 模拟最新版 Chrome User-Agent
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    options.add_argument(f'user-agent={ua}')

    # 4. 动态锁定系统路径 (关键：解决 SessionNotCreatedException)
    chrome_bin = "/usr/bin/chromium"
    driver_bin = "/usr/bin/chromedriver"
    
    # 如果路径不对，用 shutil 搜一遍
    if not os.path.exists(chrome_bin):
        chrome_bin = shutil.which("chromium") or shutil.which("chromium-browser")
    if not os.path.exists(driver_bin):
        driver_bin = shutil.which("chromedriver")

    options.binary_location = chrome_bin
    service = Service(executable_path=driver_bin)

    driver = webdriver.Chrome(service=service, options=options)

    # 5. CDP 注入抹除痕迹
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
    })
    return driver

def scrape_steamdb():
    url = "https://steamdb.info/topsellers/"
    print(f"Steam Kernel Running: Target Top {SCRAPE_LIMIT}")
    
    driver = get_stealth_driver()
    try:
        driver.get(url)
        
        # === 核心策略 1：缓冲等待 Cloudflare 5秒盾 ===
        time.sleep(10) 

        # === 核心策略 2：智能尝试点击 Turnstile 验证框 ===
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for frame in iframes:
                if "challenges" in frame.get_attribute("src"):
                    print("Found Cloudflare challenge iframe, attempting to click...")
                    driver.switch_to.frame(frame)
                    try:
                        checkbox = driver.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                        driver.execute_script("arguments[0].click();", checkbox)
                        print("✨ Checkbox clicked successfully!")
                    except:
                        driver.find_element(By.TAG_NAME, "body").click()
                        print("✨ Clicked frame body as fallback.")
                    driver.switch_to.default_content()
                    time.sleep(5)
                    break
        except:
            driver.switch_to.default_content()
            pass

        # === 核心策略 3：检测数据表格是否渲染 ===
        wait = WebDriverWait(driver, 30)
        try:
            if "table-products" not in driver.page_source:
                print("Table not found, performing a force refresh...")
                driver.refresh()
                time.sleep(10)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-products")))
        except:
            driver.save_screenshot("steam_debug.png")
            print(f"❌ Failed to bypass. Page Title: {driver.title}")
            return

        # 解析 HTML
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.find('table', class_='table-products')
        rows = table.find('tbody').find_all('tr')[:SCRAPE_LIMIT]
        
        results = []
        total = len(rows)
        for i, row in enumerate(rows):
            cols = row.find_all('td')
            if len(cols) < 5: continue
            
            name = cols[2].get_text(strip=True)
            # 配合进度条输出 [1/5] 格式
            print(f"[{i+1}/{total}] Processing: {name}")
            
            # 处理排名变化
            change_col = cols[4]
            change_val = change_col.get_text(strip=True)
            if "seller-pos-up" in str(change_col): change = f"+{change_val}"
            elif "seller-pos-down" in str(change_col): change = f"-{change_val}"
            else: change = change_val

            results.append({
                "Rank": cols[0].get_text(strip=True).replace('.', ''),
                "Game Name": name,
                "Price": cols[3].get_text(strip=True),
                "Change": change,
                "Developer": cols[5].get_text(strip=True)
            })

        if results:
            pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
            print(f"File Saved: {OUTPUT_FILE}")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_steamdb()
