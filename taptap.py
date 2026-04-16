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

# === 屏蔽警告并强制 UTF-8 输出 ===
import warnings
warnings.filterwarnings("ignore")
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 5))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "TapTap_Result.csv")
BASE_URL = "https://www.taptap.cn"

def init_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")

    chromium_path = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    chromedriver_path = shutil.which("chromedriver")

    if chromium_path: options.binary_location = chromium_path
    service = Service(executable_path=chromedriver_path) if chromedriver_path else Service()
    
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
    })
    return driver

def scroll_to_bottom_then_top(driver, wait_time=1):
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height: break
        last_height = new_height
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(wait_time)

def get_absolute_link(href, base_url=BASE_URL):
    return base_url + href if href.startswith("/") else href

def get_game_list(driver):
    print("正在滚动加载首页榜单数据...")
    scroll_to_bottom_then_top(driver)
    games = driver.find_elements(By.CSS_SELECTOR, "div.rank-game-cell")
    game_list = []

    for i, game in enumerate(games[:SCRAPE_LIMIT]):
        try:
            rank = game.find_element(By.CSS_SELECTOR, "span.rank-index").text.strip()
            name = game.find_element(By.CSS_SELECTOR, "div.text-with-tags.app-title span.text-default--size").text.strip()
            links = game.find_elements(By.CSS_SELECTOR, "a[href^='/app/']")
            link = get_absolute_link(links[0].get_attribute("href")) if links else ""
            game_list.append({"rank": rank, "name": name, "link": link})
        except Exception: continue
    return game_list

def get_single_metric(driver):
    """加入强制等待机制，解决异步渲染抓空问题"""
    def normalize_number(text):
        text = text.replace("人", "").replace(",", "").strip()
        try:
            if "万" in text: return int(float(re.sub(r"[^\d\.]", "", text)) * 10000)
            else: return int(float(re.sub(r"[^\d\.]", "", text)))
        except: return 0

    def grab_data():
        try:
            for box in driver.find_elements(By.CSS_SELECTOR, "div.single-info"):
                key = box.find_element(By.CSS_SELECTOR, ".caption-m12-w12").text.strip()
                val = box.find_element(By.CSS_SELECTOR, ".single-info__content__value").text.strip()
                if key in ["预约", "关注"]: return normalize_number(val)
        except: pass
        return 0

    try:
        # === 核心修复：等平台按钮出来，点一下并缓冲 ===
        btns = WebDriverWait(driver, 4).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.platform-picker-switch__item"))
        )
        driver.execute_script("arguments[0].click();", btns[0])
        time.sleep(1) # 等待数据加载
    except:
        try:
            # === 如果单平台没有按钮，直接等数值框渲染 ===
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.single-info"))
            )
        except: pass

    return grab_data()

def get_additional_info(driver):
    try: return ", ".join([tag.text.strip() for tag in driver.find_elements(By.CSS_SELECTOR, "a.app-intro__tag-item")])
    except: return ""

def get_publisher(driver):
    try:
        for el in driver.find_elements(By.XPATH, "//*[contains(text(), '供应商') or contains(text(), '发行商') or contains(text(), '开发商')]"):
            text = el.text.strip()
            if 2 < len(text) < 40: 
                for prefix in ["供应商", "发行商", "开发商", "厂商", ":", "：", " "]: text = text.replace(prefix, "")
                if text: return text.strip()
    except: pass
    try: return driver.find_element(By.XPATH, "//div[contains(text(),'发行') or contains(text(),'厂商') or contains(text(),'开发')]/following-sibling::div").text.strip()
    except: pass
    try: return driver.find_element(By.CSS_SELECTOR, "a.developer-name, span.developer-text").text.strip()
    except: pass
    return "暂无信息"

def get_intro_full(driver):
    try:
        summary = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.app-intro__summary")))
        driver.execute_script("arguments[0].click();", summary)
        time.sleep(0.5)
        return WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.text-modal.paragraph-m14-w14"))).text.strip()
    except: return ""

def save_detailed_data_to_csv(data):
    df = pd.DataFrame(data)
    cols = ["排名", "名称", "标签", "厂商", "预约/关注量", "简介"]
    df = df[[c for c in cols if c in df.columns]]
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"File Saved: {OUTPUT_FILE}")

def main():
    print(f"TapTap Kernel Running: Target Top {SCRAPE_LIMIT}")
    driver = init_driver()
    url = "https://www.taptap.cn/top/reserve"
    
    try:
        driver.get(url)
        time.sleep(3)

        games = get_game_list(driver)
        results = []
        total_games = len(games)

        for i, row in enumerate(games):
            try:
                print(f"[{i+1}/{total_games}] Processing Detail: {row['name']}")
                
                driver.get(row["link"])
                # 这里无需额外 sleep，因为 get_single_metric 里面已经加了智能等待
                
                tags_str = get_additional_info(driver)
                factory = get_publisher(driver)
                intro = get_intro_full(driver)
                reserve_num = get_single_metric(driver)

                results.append({
                    "排名": row["rank"],
                    "名称": row["name"],
                    "简介": intro[:150] + "..." if len(intro) > 150 else intro,  
                    "标签": tags_str,
                    "厂商": factory,
                    "预约/关注量": reserve_num if reserve_num > 0 else "暂无数据"
                })
            except Exception: continue

        if results: save_detailed_data_to_csv(results)
        else: print("未能抓取到任何有效数据。")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
