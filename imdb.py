import time
import re
import pandas as pd
import os
import sys
import shutil
import calendar
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

# === 环境变量读取 (由 app.py 指挥官传参) ===
SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 5))
YEAR = int(os.environ.get("YEAR", 2026))
MONTH = int(os.environ.get("MONTH", 2))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "IMDb_Result.csv")

def get_stealth_driver():
    """
    构造适配云端 Linux 环境的隐身驱动器
    """
    options = Options()
    # 1. 云端 Linux 必备参数
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # 2. 抹除自动化特征
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # 3. 模拟真实 User-Agent
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    options.add_argument(f'user-agent={ua}')

    # 4. 动态锁定系统 Chromium 路径 (解决 127 错误和版本冲突)
    chrome_bin = "/usr/bin/chromium"
    driver_bin = "/usr/bin/chromedriver"
    
    if not os.path.exists(chrome_bin):
        chrome_bin = shutil.which("chromium") or shutil.which("chromium-browser")
    if not os.path.exists(driver_bin):
        driver_bin = shutil.which("chromedriver")

    options.binary_location = chrome_bin
    service = Service(executable_path=driver_bin)

    driver = webdriver.Chrome(service=service, options=options)

    # 5. 执行 CDP 命令：在页面加载前抹除所有 webdriver 痕迹
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """
    })
    return driver

def scrape_imdb():
    # 构造查询周期
    _, last_day = calendar.monthrange(YEAR, MONTH)
    start_date = f"{YEAR}-{MONTH:02d}-01"
    end_date = f"{YEAR}-{MONTH:02d}-{last_day}"
    search_url = f"https://www.imdb.com/search/title/?title_type=tv_series,tv_episode&release_date={start_date},{end_date}"
    
    print(f"IMDb Kernel Running: {start_date} to {end_date} (Target: Top {SCRAPE_LIMIT})")
    
    driver = get_stealth_driver()
    results = []

    try:
        driver.get(search_url)
        # 等待页面渲染和可能的挑战
        time.sleep(10) 
        
        wait = WebDriverWait(driver, 30)
        # 寻找列表项
        items = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'li.ipc-metadata-list-summary-item')))
        
        # 只处理用户请求的前 N 个
        target_items = items[:SCRAPE_LIMIT]
        total = len(target_items)
        
        for i, item in enumerate(target_items):
            try:
                # 提取名称
                name_el = item.find_element(By.CSS_SELECTOR, 'h3.ipc-title__text')
                name = name_el.text.split('. ', 1)[-1]
                
                # 提取评分
                try:
                    rating = item.find_element(By.CSS_SELECTOR, 'span.ipc-rating-star--rating').text
                except:
                    rating = "N/A"
                
                # 提取链接
                link = item.find_element(By.CSS_SELECTOR, 'a.ipc-title-link-wrapper').get_attribute('href').split('?')[0]
                
                # 打印进度日志供 app.py 捕获
                print(f"[{i+1}/{total}] Scraping: {name}")
                
                results.append({
                    "排名": i + 1,
                    "名称": name,
                    "评分": rating,
                    "详情链接": link,
                    "日期范围": f"{start_date} ~ {end_date}"
                })
            except Exception as e:
                continue
            
    finally:
        driver.quit()

    if results:
        df = pd.DataFrame(results)
        df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        print(f"File Saved: {OUTPUT_FILE}")

if __name__ == "__main__":
    scrape_imdb()
