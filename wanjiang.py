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

# === 屏蔽警告并强制 UTF-8 输出，防止进度条截取特殊字符时崩溃 ===
warnings.filterwarnings("ignore")
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# === 从 app.py 读取环境变量 ===
SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 10))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "Wanjiang_Result.csv")
YEAR = os.environ.get("YEAR", "2026")
MONTH = os.environ.get("MONTH", "02")

# 动态生成玩匠的年月匹配字符串
MONTH_KEY = f"{YEAR}年{int(MONTH)}月"   # 例如: "2026年2月"
TARGET_MONTH = f"{YEAR}-{str(MONTH).zfill(2)}"  # 例如: "2026-02"

# ================= 核心工具函数 =================

def init_driver():
    """适配云端 Linux 环境的核心无头浏览器配置"""
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

def clean_game_name(name):
    if not name: return ""
    original = name
    name = re.split(r'[-—:：(（\[【]', name)[0]
    name = re.sub(r'\d+月\d+日.*', '', name)
    cleaned = name.strip()
    return original if len(cleaned) < 1 else cleaned

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
    except:
        return 0

def get_publisher(driver):
    """复用 TapTap 最强多重 Fallback 厂商提取机制"""
    try:
        elements = driver.find_elements(By.XPATH, "//*[contains(text(), '供应商') or contains(text(), '发行商') or contains(text(), '开发商')]")
        for el in elements:
            text = el.text.strip()
            if 2 < len(text) < 40: 
                for prefix in ["供应商", "发行商", "开发商", "厂商", ":", "：", " "]:
                    text = text.replace(prefix, "")
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
    wait = WebDriverWait(driver, 10)

    # 切换年月
    while True:
        try:
            ym = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@class='v-date-picker-header__value']//button")))
            if ym.text.strip() == MONTH_KEY: break
            driver.find_element(By.XPATH, "//i[contains(@class, 'mdi-chevron-left')]").click()
            time.sleep(0.5)
        except: break
    
    try: wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'1日')]"))).click()
    except: pass
    
    # 滚动加载
    try:
        feed = driver.find_element(By.CSS_SELECTOR, "div.van-list[role='feed']")
        for _ in range(15): 
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.8)
    except: pass

    results = []
    seen = set()
    try:
        items = feed.find_elements(By.CSS_SELECTOR, "div.date-item")
        rank = 1
        for item in items:
            date = item.find_element(By.CSS_SELECTOR, ".date_div > span").text.strip()
            if not date.startswith(TARGET_MONTH): continue
            
            games = item.find_elements(By.CSS_SELECTOR, "a.game-item")
            for g in games:
                if "上线" in g.text: continue
                name = g.find_element(By.CSS_SELECTOR, ".game-info-1 > span").text.strip()
                if name not in seen:
                    results.append({"rank": rank, "name": name, "date": date})
                    seen.add(name)
                    rank += 1
                if len(results) >= SCRAPE_LIMIT: # 触发截断
                    return results
    except: pass
    return results

def scrape_current_stats(driver):
    stats = {}
    try:
        boxes = driver.find_elements(By.CSS_SELECTOR, ".single-info__content")
        for box in boxes:
            txt = box.text.strip()
            if any(k in txt for k in ["预约", "关注", "安装", "玩过"]):
                try:
                    val_str = box.find_element(By.CSS_SELECTOR, ".single-info__content__value").text.strip()
                    val = normalize_number(val_str)
                    if val > 0:
                        if "预约" in txt: stats["预约"] = val
                        elif "关注" in txt: stats["关注"] = val
                        elif "安装" in txt or "玩过" in txt: stats["安装"] = val
                except: continue
    except: pass
    return stats

def get_taptap_details(driver, game_list):
    final_data = []
    total = len(game_list)
    
    for idx, item in enumerate(game_list):
        raw_name = item['name']
        search_name = clean_game_name(raw_name)
        
        # === 配合 app.py 实时进度条打印 ===
        print(f"[{idx+1}/{total}] Processing: {raw_name} (开测日期: {item['date']})")

        row = {
            "序号": item['rank'],
            "开测日期": item['date'],
            "名称": raw_name,
            "标签": "",
            "厂商": "",
            "安卓平台": "",
            "iOS平台": "",
            "PC端平台": "",
            "简介": ""
        }

        try:
            driver.get(f"https://www.taptap.cn/search/{search_name}")
            try:
                link = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.tap-router[href*="/app/"]'))
                )
                link.click()
                time.sleep(2) 
            except:
                final_data.append(row)
                continue

            row["厂商"] = get_publisher(driver)
            
            try:
                tags = [t.text.strip() for t in driver.find_elements(By.CSS_SELECTOR, "a.app-intro__tag-item")]
                row["标签"] = ", ".join(tags)
            except: pass

            try:
                try: driver.find_element(By.CSS_SELECTOR, ".app-intro__summary").click()
                except: pass
                intro = driver.find_element(By.CSS_SELECTOR, ".text-modal").text.strip()
                row["简介"] = intro[:100] + "..." if len(intro) > 100 else intro
            except: pass

            platforms_map = {"安卓": {}, "iOS": {}, "PC": {}}
            try: btns = driver.find_elements(By.CSS_SELECTOR, "div.platform-picker-switch__item")
            except: btns = []

            if btns:
                for btn in btns:
                    try:
                        p_name = btn.text.strip()
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.5)
                        current_data = scrape_current_stats(driver)
                        if "Android" in p_name or "安卓" in p_name: platforms_map["安卓"] = current_data
                        elif "iOS" in p_name: platforms_map["iOS"] = current_data
                        elif "PC" in p_name: platforms_map["PC"] = current_data
                    except: pass
            else:
                platforms_map["安卓"] = scrape_current_stats(driver)
                
            if platforms_map["安卓"]: row["安卓平台"] = str(platforms_map["安卓"])
            if platforms_map["iOS"]: row["iOS平台"] = str(platforms_map["iOS"])
            if platforms_map["PC"]: row["PC端平台"] = str(platforms_map["PC"])

            final_data.append(row)
        except Exception as e:
            final_data.append(row)

    return final_data

def main():
    print(f"Wanjiang Kernel Running: Target Top {SCRAPE_LIMIT} for {MONTH_KEY}")
    driver = init_driver()
    try:
        game_list = get_game_list_from_16p(driver)
        if game_list:
            data = get_taptap_details(driver, game_list)
            df = pd.DataFrame(data)
            cols = ["序号", "开测日期", "名称", "标签", "厂商", "安卓平台", "iOS平台", "PC端平台", "简介"]
            df = df[cols]
            df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
            print(f"File Saved: {OUTPUT_FILE}")
        else:
            print("未能抓取到任何有效数据，可能该月无数据或页面结构变更。")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
