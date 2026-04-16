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

# ================= 核心修复：三重雷达轮询提取 =================
def get_max_reserve_num(driver):
    def normalize_number(text):
        if not text: return 0
        # 移除空格和所有非数字及非单位字符
        text = str(text).replace(" ", "").replace(",", "").strip()
        try:
            # 提取数字部分（支持 12.5 这种浮点）
            match = re.search(r"[\d\.]+", text)
            if not match: return 0
            num = float(match.group())
            if "万" in text: return int(num * 10000)
            elif "亿" in text: return int(num * 100000000)
            else: return int(num)
        except: return 0

    def extract_from_html():
        max_v = 0
        try:
            # 策略：根据你提供的 HTML 源码精准定位
            # 寻找所有包含 single-info__content 的块
            info_blocks = driver.find_elements(By.CSS_SELECTOR, ".single-info__content")
            for block in info_blocks:
                block_text = block.get_attribute("textContent") # 穿透式提取内容
                if "预约" in block_text or "关注" in block_text:
                    # 尝试定位那个包含数值的具体 div
                    val_elem = block.find_element(By.CSS_SELECTOR, ".single-info__content__value")
                    val_str = val_elem.get_attribute("textContent")
                    max_v = max(max_v, normalize_number(val_str))
        except: pass
        return max_v

    global_max = 0
    # 强制等待目标元素在页面上“现身”
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".single-info__content__value"))
        )
    except: pass

    try:
        # 检查是否有切换按钮（多端情况）
        btns = driver.find_elements(By.CSS_SELECTOR, "div.platform-picker-switch__item")
        if btns:
            for i in range(len(btns)):
                # 重新获取按钮，防止页面刷新导致失效
                refresh_btns = driver.find_elements(By.CSS_SELECTOR, "div.platform-picker-switch__item")
                btn = refresh_btns[i]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1.2) # 给 Vue 组件一点数据挂载时间
                global_max = max(global_max, extract_from_html())
        else:
            # 单端情况直接抓
            global_max = extract_from_html()
    except:
        global_max = extract_from_html()

    return global_max if global_max > 0 else "暂无数据"
# ==============================================================

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
            return WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, "p.text-modal__text"))).get_attribute("innerText").strip()
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
                # 去掉无脑的 sleep(1)，让提取函数自己去智能轮询
                
                tags_str = get_additional_info(driver)
                factory = get_publisher(driver)
                intro = get_intro_full(driver)
                
                # 触发提取核心引擎
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
        else: print("未能抓取到任何有效数据。")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
