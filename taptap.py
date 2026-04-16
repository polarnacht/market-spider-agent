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
    for game in games[:SCRAPE_LIMIT]:
        try:
            rank = game.find_element(By.CSS_SELECTOR, "span.rank-index").text.strip()
            name = game.find_element(By.CSS_SELECTOR, "div.text-with-tags.app-title span.text-default--size").text.strip()
            links = game.find_elements(By.CSS_SELECTOR, "a[href^='/app/']")
            link = get_absolute_link(links[0].get_attribute("href")) if links else ""
            game_list.append({"rank": rank, "name": name, "link": link})
        except: continue
    return game_list

# === 恢复最强提取逻辑：遍历所有端，取最大值 ===
def get_max_reserve_num(driver):
    def normalize_number(text):
        if not text: return 0
        text = text.replace(" ", "").replace(",", "").replace("人", "").strip()
        try:
            if "万" in text:
                num = re.search(r"[\d\.]+", text).group()
                return int(float(num) * 10000)
            elif "亿" in text:
                num = re.search(r"[\d\.]+", text).group()
                return int(float(num) * 100000000)
            else:
                num = re.sub(r"[^\d]", "", text)
                return int(num) if num else 0
        except: return 0

    def scrape_current_stats():
        max_val = 0
        try:
            boxes = driver.find_elements(By.CSS_SELECTOR, ".single-info__content")
            for box in boxes:
                txt = box.text.strip()
                if "预约" in txt or "关注" in txt:
                    try:
                        val_str = box.find_element(By.CSS_SELECTOR, ".single-info__content__value").text.strip()
                        val = normalize_number(val_str)
                        if val > max_val: max_val = val
                    except: continue
        except: pass
        return max_val

    # 先等元素渲染
    try: WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".single-info__content")))
    except: pass

    global_max = 0
    try: btns = driver.find_elements(By.CSS_SELECTOR, "div.platform-picker-switch__item")
    except: btns = []

    if btns:
        for btn in btns:
            try:
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.5)
                current_val = scrape_current_stats()
                if current_val > global_max: global_max = current_val
            except: pass
    else:
        global_max = scrape_current_stats()
        
    return global_max

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
                time.sleep(1)
                
                tags_str = get_additional_info(driver)
                factory = get_publisher(driver)
                intro = get_intro_full(driver)
                
                # === 直接调用新融合的获取最高预约量函数 ===
                reserve_num = get_max_reserve_num(driver)

                results.append({
                    "排名": row["rank"],
                    "名称": row["name"],
                    "简介": intro[:150] + "..." if len(intro) > 150 else intro,  
                    "标签": tags_str,
                    "厂商": factory,
                    "预约/关注量": reserve_num if reserve_num > 0 else "暂无数据"
                })
            except Exception: continue

        if results:
            df = pd.DataFrame(results)
            cols = ["排名", "名称", "标签", "厂商", "预约/关注量", "简介"]
            df = df[[c for c in cols if c in df.columns]]
            df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
            print(f"File Saved: {OUTPUT_FILE}")
        else:
            print("未能抓取到任何有效数据。")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
