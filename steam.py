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

# 屏蔽所有干扰
warnings.filterwarnings("ignore")
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 5))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "Steam_Result.csv")

def get_stealth_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # 模拟真实用户的硬件环境
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7")
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    options.add_argument(f'user-agent={ua}')
    
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # 路径锁定
    chrome_bin = "/usr/bin/chromium"
    driver_bin = "/usr/bin/chromedriver"
    if not os.path.exists(chrome_bin):
        chrome_bin = shutil.which("chromium") or shutil.which("chromium-browser")
    if not os.path.exists(driver_bin):
        driver_bin = shutil.which("chromedriver")

    options.binary_location = chrome_bin
    service = Service(executable_path=driver_bin)
    driver = webdriver.Chrome(service=service, options=options)

    # 注入高级隐身脚本 (抹除硬件加速、插件等指纹)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """
    })
    return driver

def bypass_cloudflare(driver):
    """
    专门针对 Cloudflare Turnstile 的自动过盾逻辑
    """
    print("正在尝试穿透 Cloudflare 防护层...")
    for attempt in range(2): # 尝试 2 次
        time.sleep(12) 
        if "table-products" in driver.page_source:
            return True
        
        try:
            # 搜索验证框 iframe
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for frame in iframes:
                src = frame.get_attribute("src") or ""
                if "challenges" in src or "turnstile" in src:
                    print(f"发现验证框，尝试第 {attempt+1} 次模拟点击...")
                    driver.switch_to.frame(frame)
                    # 尝试多种可能的复选框选择器
                    for selector in ["input[type='checkbox']", "#challenge-stage", "body"]:
                        try:
                            target = driver.find_element(By.CSS_SELECTOR, selector)
                            driver.execute_script("arguments[0].click();", target)
                            break
                        except: continue
                    driver.switch_to.default_content()
                    time.sleep(8)
                    break
            
            # 模拟轻微滚动（诱导检测）
            driver.execute_script("window.scrollBy(0, 100);")
            
            if "table-products" in driver.page_source:
                return True
            else:
                print("未见表格，尝试刷新页面...")
                driver.refresh()
        except:
            driver.switch_to.default_content()
    return False

def scrape_steamdb():
    print(f"Steam Kernel Running: Target Top {SCRAPE_LIMIT}")
    driver = get_stealth_driver()
    try:
        driver.get("https://steamdb.info/topsellers/")
        
        if not bypass_cloudflare(driver):
            # 最后的挣扎：强制等待并检测
            time.sleep(15)

        wait = WebDriverWait(driver, 20)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-products")))
        except:
            driver.save_screenshot("steam_debug.png")
            print(f"❌ 穿透失败。当前页面标题: {driver.title}")
            return

        print("✨ 穿透成功，正在提取结构化数据...")
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.find('table', class_='table-products')
        rows = table.find('tbody').find_all('tr')[:SCRAPE_LIMIT]
        
        results = []
        for i, row in enumerate(rows):
            cols = row.find_all('td')
            if len(cols) < 6: continue
            name = cols[2].get_text(strip=True)
            print(f"[{i+1}/{len(rows)}] Processing: {name}")
            results.append({
                "Rank": cols[0].get_text(strip=True).replace('.', ''),
                "Game Name": name,
                "Price": cols[3].get_text(strip=True),
                "Developer": cols[5].get_text(strip=True)
            })

        if results:
            pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
            print(f"File Saved: {OUTPUT_FILE}")
    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_steamdb()
