import time
import re
import pandas as pd
import os
import sys
import warnings
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 彻底屏蔽所有干扰日志
warnings.filterwarnings("ignore")
if sys.stdout.encoding != 'utf-8':
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 5))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "Steam_Result.csv")


def get_stealth_driver():
    options = webdriver.ChromeOptions()
    # 云端运行必备：headless
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    # 模拟真实的高分屏和显卡渲染特征
    options.add_argument("--force-device-scale-factor=1")
    options.add_argument("--disable-gpu")  # 有些 Cloudflare 版本会检查 GPU 指纹，禁用它反而更安全

    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    options.add_argument(f'user-agent={ua}')

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

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

        # === 核心策略 1：多段式等待，给 Cloudflare 渲染时间 ===
        time.sleep(10)

        # === 核心策略 2：智能查找验证框 ===
        try:
            # 查找所有可能的 Turnstile iframe
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for frame in iframes:
                if "challenges" in frame.get_attribute("src"):
                    print("Found Cloudflare challenge iframe, attempting to click...")
                    driver.switch_to.frame(frame)
                    # 尝试点击复选框 (Turnstile 的 checkbox 通常是 div 模拟的)
                    try:
                        checkbox = driver.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                        driver.execute_script("arguments[0].click();", checkbox)
                        print("✨ Checkbox clicked successfully!")
                    except:
                        # 另一种可能的结构：直接点击 body 区域
                        driver.find_element(By.TAG_NAME, "body").click()
                        print("✨ Clicked frame body as fallback.")

                    driver.switch_to.default_content()
                    time.sleep(5)  # 等待跳转
                    break
        except Exception as e:
            driver.switch_to.default_content()
            pass

        # === 核心策略 3：检测表格是否出现 ===
        wait = WebDriverWait(driver, 30)
        try:
            # 如果表格还没出来，尝试最后一次强刷
            if "table-products" not in driver.page_source:
                print("Table not found, performing a force refresh...")
                driver.refresh()
                time.sleep(10)

            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table-products")))
        except:
            driver.save_screenshot("steam_debug.png")
            print(f"❌ Failed to bypass. Title: {driver.title}")
            return

        # 解析数据
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.find('table', class_='table-products')
        rows = table.find('tbody').find_all('tr')[:SCRAPE_LIMIT]

        results = []
        for i, row in enumerate(rows):
            cols = row.find_all('td')
            if len(cols) < 5: continue
            name = cols[2].get_text(strip=True)
            print(f"[{i + 1}/{SCRAPE_LIMIT}] Processing: {name}")
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