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
            link = (BASE_URL + links[0].get_attribute("href") if links[0].get_attribute("href").startswith("/") else links[0].get_attribute("href")) if links else ""
            game_list.append({"rank": rank, "name": name, "link": link})
        except: continue
    return game_list

# === 融合了原版最强“轮播图备用提取”的取最大值函数 ===
def get_max_reserve_num(driver):
    def normalize_number(text):
        text = str(text).replace("人", "").replace(",", "").strip()
        try:
            if "万" in text: return int(float(re.sub(r"[^\d\.]", "", text)) * 10000)
            elif "亿" in text: return int(float(re.sub(r"[^\d\.]", "", text)) * 100000000)
            else: return int(float(re.sub(r"[^\d\.]", "", text) or 0))
        except: return 0

    def extract_current_view():
        max_current = 0
        # 主方式
        try:
            for box in driver.find_elements(By.CSS_SELECTOR, "div.single-info"):
                key = box.find_element(By.CSS_SELECTOR, ".caption-m12-w12").text.strip()
                val = box.find_element(By.CSS_SELECTOR, ".single-info__content__value").text.strip()
                if key in ["预约", "关注"]:
                    max_current = max(max_current, normalize_number(val))
        except: pass
        
        # 备用方式 (完全复刻你的逻辑)
        if max_current == 0:
            try:
                for box in driver.find_elements(By.CSS_SELECTOR, "div.swiper-slide"):
                    spans = box.find_elements(By.TAG_NAME, "span")
                    if len(spans) >= 2:
                        val = spans[0].text.strip()
                        key = spans[1].text.strip()
                        if key in ["预约", "关注"]:
                            max_current = max(max_current, normalize_number(val))
            except: pass
        return max_current

    global_max = 0
    try:
        platform_buttons = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.platform-picker-switch__item"))
        )
        for btn in platform_buttons:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1)
                global_max = max(global_max, extract_current_view())
            except: continue
    except:
        global_max = extract_current_view()
        
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

# === 完美复刻你的“展开更多”简介抓取方案 ===
def get_intro_full(driver):
    try:
        summary = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.app-intro__summary")))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", summary)
        time.sleep(0.3)
        driver.execute_script("arguments[0].click();", summary)
        time.sleep(0.5)
        try:
            summary_div = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.text-modal.paragraph-m14-w14")))
            intro_text = summary_div.text.strip()
            if intro_text: return intro_text
            
            more_button = summary_div.find_element(By.CSS_SELECTOR, "div.text-modal__more.clickable span")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_button)
            driver.execute_script("arguments[0].click();", more_button)
            time.sleep(0.5)
            
            full_intro = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, "p.text-modal__text"))).get_attribute("innerText").strip()
            return full_intro
        except: return ""
    except: return ""

def main():
    print(f"TapTap Kernel Running: Target Top {SCRAPE_LIMIT}")
    driver = init_driver()
    try:
        driver.get("https://www.taptap.cn/top/reserve")
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
                reserve_num = get_max_reserve_num(driver)

                results.append({
                    "排名": row["rank"],
                    "名称": row["name"],
                    "简介": intro[:150] + "..." if len(intro) > 150 else intro,  
                    "标签": tags_str,
                    "厂商": factory,
                    "预约/关注量": reserve_num
                })
            except Exception: continue

        if results:
            df = pd.DataFrame(results)
            cols = ["排名", "名称", "标签", "厂商", "预约/关注量", "简介"]
            df = df[[c for c in cols if c in df.columns]]
            df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
            print(f"File Saved: {OUTPUT_FILE}")
        else: print("未能抓取到任何有效数据。")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
