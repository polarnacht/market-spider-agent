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

SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 20)) 
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "Wanjiang_Result.csv")
YEAR = os.environ.get("YEAR", "2026")
MONTH = os.environ.get("MONTH", "02")
MONTH_KEY = f"{YEAR}年{int(MONTH)}月"   
TARGET_MONTH = f"{YEAR}-{str(MONTH).zfill(2)}"  

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
    if chromium_path: options.binary_location = chromium_path
    service = Service(executable_path=chromedriver_path) if chromedriver_path else Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"})
    return driver

def clean_game_name(name):
    if not name: return ""
    original = name
    name = re.sub(r'[\(（\[【].*?[\)）\]】]', '', name)
    for word in ["测试服", "体验服", "抢先服", "正式服", "删档", "不删档", "公测", "内测", "首测", "终测"]: name = name.replace(word, "")
    name = re.split(r'[-—:：|]', name)[0]
    name = re.sub(r'\d+月\d+日.*', '', name)
    cleaned = name.strip()
    return original.split()[0] if len(cleaned) < 1 else cleaned

def get_game_list_from_16p(driver):
    print(f"[{MONTH_KEY} 开测榜] Fetching List...")
    driver.get("https://www.16p.com/newgame")
    wait = WebDriverWait(driver, 15)
    while True:
        try:
            if wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".dp-title"))).get_attribute("textContent").strip() == MONTH_KEY: break
            nav_btns = driver.find_elements(By.CSS_SELECTOR, "button.dp-nav")
            if nav_btns: driver.execute_script("arguments[0].click();", nav_btns[0]); time.sleep(0.8)
            else: break
        except: break
    try: 
        for day in driver.find_elements(By.CSS_SELECTOR, ".dp-grid--days .dp-cell"):
            if day.get_attribute("textContent").strip() == "1" and "is-empty" not in day.get_attribute("class"):
                driver.execute_script("arguments[0].click();", day); time.sleep(3); break
    except: pass
    try:
        feed = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.van-list[role='feed']")))
        for _ in range(20): driver.execute_script("window.scrollTo(0, document.body.scrollHeight);"); time.sleep(1)
    except: return []

    results = []
    seen = set()
    try:
        for item in feed.find_elements(By.CSS_SELECTOR, "div.date-item"):
            date = item.find_element(By.CSS_SELECTOR, ".date_div span").get_attribute("textContent").strip()
            if date > f"{TARGET_MONTH}-31": return results
            if not date.startswith(TARGET_MONTH): continue
            for g in item.find_elements(By.CSS_SELECTOR, "a.game-item"):
                if "上线" in g.get_attribute("textContent"): continue
                name = g.find_element(By.CSS_SELECTOR, ".game-info-1 span").get_attribute("textContent").strip()
                if name not in seen:
                    results.append({"rank": len(results)+1, "name": name, "date": date})
                    seen.add(name)
                if len(results) >= SCRAPE_LIMIT: return results
    except: pass
    return results

def get_max_reserve_num(driver):
    """【最终版】同步穿透式提取引擎"""
    def normalize_number(text):
        if not text: return 0
        text = str(text).replace(" ", "").replace(",", "").strip()
        try:
            match = re.search(r"[\d\.]+", text)
            if not match: return 0
            num = float(match.group())
            return int(num * 10000) if "万" in text else int(num * 100000000) if "亿" in text else int(num)
        except: return 0

    def extract():
        max_v = 0
        try:
            blocks = driver.find_elements(By.CSS_SELECTOR, ".single-info__content")
            for block in blocks:
                content = block.get_attribute("textContent")
                if "预约" in content or "关注" in content:
                    v_str = block.find_element(By.CSS_SELECTOR, ".single-info__content__value").get_attribute("textContent")
                    max_v = max(max_v, normalize_number(v_str))
        except: pass
        return max_v

    res = 0
    try:
        btns = driver.find_elements(By.CSS_SELECTOR, "div.platform-picker-switch__item")
        if btns:
            for i in range(len(btns)):
                fresh = driver.find_elements(By.CSS_SELECTOR, "div.platform-picker-switch__item")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", fresh[i])
                driver.execute_script("arguments[0].click();", fresh[i])
                time.sleep(1.2)
                res = max(res, extract())
        else: res = extract()
    except: res = extract()
    return res if res > 0 else "暂无数据"

def get_taptap_details(driver, game_list):
    final_data = []
    total = len(game_list)
    for idx, item in enumerate(game_list):
        search_name = clean_game_name(item['name'])
        print(f"[{idx+1}/{total}] Searching: {search_name}")
        row = {"序号": item['rank'], "开测日期": item['date'], "名称": item['name'], "标签": "", "厂商": "", "预约/关注量": "暂无数据", "简介": ""}
        try:
            driver.get(f"https://www.taptap.cn/search/{search_name}")
            try: WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.tap-router[href*="/app/"]'))).click(); time.sleep(1.5)
            except: final_data.append(row); continue
            
            try: row["厂商"] = driver.find_element(By.XPATH, "//div[contains(text(),'发行') or contains(text(),'厂商') or contains(text(),'开发')]/following-sibling::div").get_attribute("textContent").strip()
            except: pass
            try: row["标签"] = ", ".join([t.get_attribute("textContent").strip() for t in driver.find_elements(By.CSS_SELECTOR, "a.app-intro__tag-item")])
            except: pass
            row["预约/关注量"] = get_max_reserve_num(driver)
            final_data.append(row)
        except: final_data.append(row)
    return final_data

def main():
    driver = init_driver()
    try:
        list_data = get_game_list_from_16p(driver)
        if list_data:
            df = pd.DataFrame(get_taptap_details(driver, list_data))
            cols = ["序号", "开测日期", "名称", "标签", "厂商", "预约/关注量", "简介"]
            df[[c for c in cols if c in df.columns]].to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
            print(f"✅ Success: {OUTPUT_FILE}")
    finally: driver.quit()

if __name__ == "__main__": main()
