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

SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 10))
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
    wait = WebDriverWait(driver, 15)

    # === 核心修复 1：适配全新日历组件 ===
    while True:
        try:
            # 获取新版日历标题 <div class="dp-title">
            ym_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".dp-title")))
            current_ym = ym_element.text.strip()
            
            if current_ym == MONTH_KEY: 
                break
            
            # 点击新版日历左侧箭头 <button class="dp-nav">‹</button>
            nav_btns = driver.find_elements(By.CSS_SELECTOR, "button.dp-nav")
            if nav_btns:
                driver.execute_script("arguments[0].click();", nav_btns[0])
                time.sleep(0.8)
            else:
                break
        except Exception as e: 
            print(f"切换月份结束或异常: {e}")
            break
    
    # === 核心修复 2：点击当月 1 号 ===
    try: 
        # 获取新版日期的 span
        days = driver.find_elements(By.CSS_SELECTOR, ".dp-grid--days .dp-cell")
        for day in days:
            if day.text.strip() == "1" and "is-empty" not in day.get_attribute("class"):
                driver.execute_script("arguments[0].click();", day)
                print("成功点击当月 1 日，等待数据加载...")
                time.sleep(3) # 强制等待 Vue 异步拉取数据
                break
    except Exception as e: 
        print(f"点击日期警告: {e}")
    
    # 定位列表框
    try:
        feed = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.van-list[role='feed']")))
    except Exception:
        print("❌ 无法找到页面列表元素，可能遭遇人机验证拦截或页面未加载完成。")
        return []

    # 滚动加载
    for _ in range(15): 
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

    results = []
    seen = set()
    try:
        items = feed.find_elements(By.CSS_SELECTOR, "div.date-item")
        rank = 1
        for item in items:
            # === 核心修复 3：精准提取日期跨度结构 ===
            spans = item.find_elements(By.CSS_SELECTOR, ".date_div span")
            if not spans: continue
            date = spans[0].text.strip()
            
            if not date.startswith(TARGET_MONTH): continue
            
            games = item.find_elements(By.CSS_SELECTOR, "a.game-item")
            for g in games:
                if "上线" in g.text: continue
                name_span = g.find_elements(By.CSS_SELECTOR, ".game-info-1 span")
                if not name_span: continue
                name = name_span[0].text.strip()
                
                if name not in seen:
                    results.append({"rank": rank, "name": name, "date": date})
                    seen.add(name)
                    rank += 1
                if len(results) >= SCRAPE_LIMIT: 
                    return results
    except Exception as e: 
        print(f"解析列表异常: {e}")
        
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
            print("未能抓取到任何有效数据，已触发安全退出。")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
