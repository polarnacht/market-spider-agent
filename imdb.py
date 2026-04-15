import time
import re
import pandas as pd
import requests
import os
import calendar
import sys
import warnings
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 屏蔽干扰警告，保持子进程输出纯净
warnings.filterwarnings("ignore")
if sys.stdout.encoding != 'utf-8':
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- 环境变量读取 ---
SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 5))
YEAR = int(os.environ.get("YEAR", 2026))
MONTH = int(os.environ.get("MONTH", 2))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "IMDb_Result.csv")


def get_stealth_driver():
    """
    构造“隐身无头模式”：为了云端运行，必须无头；为了通过反爬，必须隐身。
    """
    options = webdriver.ChromeOptions()
    # 1. 云端必备参数
    options.add_argument("--headless=new")  # 使用最新的无头引擎
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    # 2. 核心伪装：让无头模式看起来像真机
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # 3. 设置真实的 User-Agent 和 语言环境
    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
    options.add_argument("--lang=en-US")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    # 4. CDP (Chrome DevTools Protocol) 注入：抹除 webdriver 的最后痕迹
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """
    })
    return driver


def scrape_imdb():
    # 构造 URL
    _, last_day = calendar.monthrange(YEAR, MONTH)
    start_date = f"{YEAR}-{MONTH:02d}-01"
    end_date = f"{YEAR}-{MONTH:02d}-{last_day}"
    search_url = f"https://www.imdb.com/search/title/?title_type=tv_series,tv_episode&release_date={start_date},{end_date}"

    # 统一输出格式，方便 app.py 捕获进度
    print(f"IMDb Kernel Running: {start_date} to {end_date}")

    driver = get_stealth_driver()
    results = []

    try:
        driver.get(search_url)
        # 给页面渲染和 Cloudflare 挑战预留时间
        time.sleep(12)

        wait = WebDriverWait(driver, 35)
        # 等待列表容器出现
        items = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'li.ipc-metadata-list-summary-item')))

        target_count = min(len(items), SCRAPE_LIMIT)
        for i in range(target_count):
            try:
                # 重新定位元素，防止滚动导致失效
                current_items = driver.find_elements(By.CSS_SELECTOR, 'li.ipc-metadata-list-summary-item')
                item = current_items[i]

                # 提取基本信息（名字、评分、链接）
                name_el = item.find_element(By.CSS_SELECTOR, 'h3.ipc-title__text')
                name = name_el.text.split('. ', 1)[-1]

                link_el = item.find_element(By.CSS_SELECTOR, 'a.ipc-title-link-wrapper')
                link = link_el.get_attribute('href').split('?')[0]

                try:
                    rating = item.find_element(By.CSS_SELECTOR, 'span.ipc-rating-star--rating').text
                except:
                    rating = "N/A"

                # 实时进度反馈 [当前/总数]
                print(f"[{i + 1}/{target_count}] Scraping: {name}")

                results.append({
                    "排名": i + 1,
                    "影视名称": name,
                    "IMDb评分": rating,
                    "详情链接": link,
                    "采集周期": f"{start_date} ~ {end_date}"
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