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

# === 屏蔽警告并强制 UTF-8 输出 ===
warnings.filterwarnings("ignore")
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 9999)) # 默认极大值
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "Wanjiang_Result.csv")
YEAR = os.environ.get("YEAR", "2026")
MONTH = os.environ.get("MONTH", "02")

MONTH_KEY = f"{YEAR}年{int(MONTH)}月"   
TARGET_MONTH = f"{YEAR}-{str(MONTH).zfill(2)}"  

# ================= 核心工具函数 =================

def init_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # 强制伪装真实用户的 User-Agent
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    options.add_argument(f'user-agent={ua}')

    chromium_path = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    chromedriver_path = shutil.which("chromedriver")

    if chromium_path: options.binary_location = chromium_path
    service = Service(executable_path=chromedriver_path) if chromedriver_path else Service()
    
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
    })
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

def normalize_number(text):
    if not text: return 0
    text = text.replace(" ", "").replace(",", "").replace("人", "").strip()
    try:
        if "万" in text: return int(float(re.search(r"[\d\.]+", text).group()) * 10000)
        elif "亿" in text: return int(float(re.search(r"[\d\.]+", text).group()) * 100000000)
        else: return int(re.sub(r"[^\d]", "", text) or 0)
    except: return 0

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

# ================= 爬虫执行链路 =================

def get_game_list_from_16p(driver):
    print(f"[{MONTH_KEY} 开测榜] 正在从玩匠获取名单...")
    driver.get("https://www.16p.com/newgame")
    wait = WebDriverWait(driver, 15)

    # 1. 切换年月
    while True:
        try:
            if wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".dp-title"))).text.strip() == MONTH_KEY: break
            nav_btns = driver.find_elements(By.CSS_SELECTOR, "button.dp-nav")
            if nav_btns: driver.execute_script("arguments[0].click();", nav_btns[0]); time.sleep(0.8)
            else: break
        except: break
        
    # 2. 点击 1 号
    try: 
        for day in driver.find_elements(By.CSS_SELECTOR, ".dp-grid--days .dp-cell"):
            if day.text.strip() == "1" and "is-empty" not in day.get_attribute("class"):
                driver.execute_script("arguments[0].click();", day); time.sleep(3); break
    except: pass
    
    # 3. 定位列表并滚动
    try:
        feed = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.van-list[role='feed']")))
        for _ in range(20): # 加大滚动次数，确保能拉到底
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
    except: 
        print("❌ 无法找到页面列表元素。")
        return []

    results = []
    seen = set()
    try:
        for item in feed.find_elements(By.CSS_SELECTOR, "div.date-item"):
            spans = item.find_elements(By.CSS_SELECTOR, ".date_div span")
            if not spans: continue
            date = spans[0].text.strip()
            
            # === 核心防越界 ===
            if date > f"{TARGET_MONTH}-31": 
                print(f"🎯 探测到越界日期 [{date}]，当月数据获取完毕！")
                return results
                
            if not date.startswith(TARGET_MONTH): continue
            
            for g in item.find_elements(By.CSS_SELECTOR, "a.game-item"):
                if "上线" in g.text: continue
                name_span = g.find_elements(By.CSS_SELECTOR, ".game-info-1 span")
                if not name_span: continue
                name = name_span[0].text.strip()
                if name not in seen:
                    results.append({"rank": len(results)+1, "name": name, "date": date})
                    seen.add(name)
                # 触发条数限制
                if len(results) >= SCRAPE_LIMIT: 
                    return results
    except Exception as e: 
        print(f"解析列表异常: {e}")
    return results

def scrape_current_stats(driver):
    stats = {}
    try:
        for box in driver.find_elements(By.CSS_SELECTOR, ".single-info__content"):
            txt = box.text.strip()
            if any(k in txt for k in ["预约", "关注"]):
                try:
                    val = normalize_number(box.find_element(By.CSS_SELECTOR, ".single-info__content__value").text.strip())
                    if val > 0:
                        if "预约" in txt: stats["预约"] = val
                        elif "关注" in txt: stats["关注"] = val
                except: continue
    except: pass
    return stats

def get_taptap_details(driver, game_list):
    final_data = []
    total = len(game_list)
    for idx, item in enumerate(game_list):
        raw_name = item['name']
        search_name = clean_game_name(raw_name)
        if raw_name != search_name: print(f"[{idx+1}/{total}] Processing: {raw_name} -> 🔍 校准: [{search_name}]")
        else: print(f"[{idx+1}/{total}] Processing: {raw_name}")

        row = {"序号": item['rank'], "开测日期": item['date'], "名称": raw_name, "标签": "", "厂商": "", "预约/关注量": "暂无数据", "简介": ""}

        try:
            driver.get(f"https://www.taptap.cn/search/{search_name}")
            try: WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.tap-router[href*="/app/"]'))).click(); time.sleep(1.5) 
            except: final_data.append(row); continue

            row["厂商"] = get_publisher(driver)
            try: row["标签"] = ", ".join([t.text.strip() for t in driver.find_elements(By.CSS_SELECTOR, "a.app-intro__tag-item")])
            except: pass
            try:
                try: driver.find_element(By.CSS_SELECTOR, ".app-intro__summary").click()
                except: pass
                intro = driver.find_element(By.CSS_SELECTOR, ".text-modal").text.strip()
                row["简介"] = intro[:100] + "..." if len(intro) > 100 else intro
            except: pass

            # === 核心修改：聚合提取总预约量 ===
            current_data = scrape_current_stats(driver)
            if not current_data:
                try: 
                    btns = driver.find_elements(By.CSS_SELECTOR, "div.platform-picker-switch__item")
                    if btns: driver.execute_script("arguments[0].click();", btns[0]); time.sleep(0.5); current_data = scrape_current_stats(driver)
                except: pass
            
            num = current_data.get("预约", current_data.get("关注", 0))
            if num > 0: row["预约/关注量"] = num

            final_data.append(row)
        except Exception as e:
            final_data.append(row)

    return final_data

def main():
    # 如果是9999说明是抓取全月
    limit_str = "全月所有" if SCRAPE_LIMIT == 9999 else str(SCRAPE_LIMIT)
    print(f"Wanjiang Kernel Running: Target {limit_str} for {MONTH_KEY}")
    driver = init_driver()
    try:
        game_list = get_game_list_from_16p(driver)
        if game_list:
            df = pd.DataFrame(get_taptap_details(driver, game_list))
            cols = ["序号", "开测日期", "名称", "标签", "厂商", "预约/关注量", "简介"]
            df = df[[c for c in cols if c in df.columns]]
            df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
            print(f"File Saved: {OUTPUT_FILE}")
        else:
            print("未能抓取到任何有效数据，已触发安全退出。")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
