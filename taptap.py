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

# 读取环境变量，默认值由 app.py 控制
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
    # 注入真实 UA 隐藏爬虫痕迹
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    options.add_argument(f'user-agent={ua}')
    
    chromium_path = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    chromedriver_path = shutil.which("chromedriver")
    if chromium_path: options.binary_location = chromium_path
    service = Service(executable_path=chromedriver_path) if chromedriver_path else Service()
    
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"})
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
    scroll_to_bottom_then_top(driver)
    games = driver.find_elements(By.CSS_SELECTOR, "div.rank-game-cell")
    game_list = []
    for game in games[:SCRAPE_LIMIT]:
        try:
            rank = game.find_element(By.CSS_SELECTOR, "span.rank-index").text.strip()
            name = game.find_element(By.CSS_SELECTOR, "div.text-with-tags.app-title span.text-default--size").text.strip()
            links = game.find_elements(By.CSS_SELECTOR, "a[href^='/app/']")
            href = links[0].get_attribute("href")
            link = BASE_URL + href if href.startswith("/") else href
            game_list.append({"rank": rank, "name": name, "link": link})
        except: continue
    return game_list

def get_max_reserve_num(driver):
    """【最终版】穿透式数值提取引擎"""
    def normalize_number(text):
        if not text: return 0
        # 清除空格/逗号/换行，只留数字和“万/亿”
        text = str(text).replace(" ", "").replace(",", "").replace("\n", "").strip()
        try:
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
            # 针对你提供的源码精准定位 single-info__content
            blocks = driver.find_elements(By.CSS_SELECTOR, ".single-info__content")
            for block in blocks:
                # 使用 get_attribute("textContent") 强行穿透 CSS 样式获取原始字符
                full_text = block.get_attribute("textContent")
                if "预约" in full_text or "关注" in full_text:
                    val_elem = block.find_element(By.CSS_SELECTOR, ".single-info__content__value")
                    val_str = val_elem.get_attribute("textContent")
                    max_v = max(max_v, normalize_number(val_str))
        except: pass
        return max_v

    global_max = 0
    # 等待 Vue 核心数据节点现身
    try: WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".single-info__content__value")))
    except: pass

    try:
        btns = driver.find_elements(By.CSS_SELECTOR, "div.platform-picker-switch__item")
        if btns:
            # 严格循环点击模式
            for i in range(len(btns)):
                fresh_btns = driver.find_elements(By.CSS_SELECTOR, "div.platform-picker-switch__item")
                btn = fresh_btns[i]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1.2) # 留出 DOM 更新缓冲
                global_max = max(global_max, extract_from_html())
        else:
            global_max = extract_from_html()
    except:
        global_max = extract_from_html()
    return global_max if global_max > 0 else "暂无数据"

def get_publisher(driver):
    try:
        # 策略1：应对新版前端结构（关键字和公司名在同一个 div 标签内，例如："供应商 完美世界（北京）互动娱乐有限公司"）
        nodes = driver.find_elements(By.XPATH, "//div[contains(text(),'供应商') or contains(text(),'厂商') or contains(text(),'发行') or contains(text(),'开发')]")
        for node in nodes:
            text = node.get_attribute("textContent").strip()
            # 限制文本长度在合理范围内，防止误抓到包含这些字眼的游戏长篇简介
            if 2 < len(text) < 50:
                # 用正则精准剃掉开头的提示词、冒号和空格，只保留纯正的公司名
                clean_text = re.sub(r"^(供应商|厂商|开发商|开发者|发行商|开发|发行|：|:|\s)+", "", text)
                if clean_text:  # 如果剔除前缀后还有内容，说明精准命中了公司名
                    return clean_text.strip()
        
        # 策略2：兜底老版前端结构（关键字和公司名分别在相邻的两个兄弟 div 里）
        factory = driver.find_element(By.XPATH, "//div[contains(text(),'发行') or contains(text(),'厂商') or contains(text(),'开发') or contains(text(),'供应商')]/following-sibling::div").get_attribute("textContent").strip()
        return factory
    except:
        return "暂无信息"

def get_intro_full(driver):
    try:
        summary = WebDriverWait(driver, 4).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.app-intro__summary")))
        driver.execute_script("arguments[0].click();", summary)
        time.sleep(0.5)
        intro = WebDriverWait(driver, 4).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.text-modal.paragraph-m14-w14"))).get_attribute("textContent").strip()
        return intro[:150] + "..." if len(intro) > 150 else intro
    except: return ""

def main():
    print(f"TapTap Kernel Starting: Top {SCRAPE_LIMIT}")
    driver = init_driver()
    try:
        driver.get("https://www.taptap.cn/top/reserve")
        time.sleep(3)
        games = get_game_list(driver)
        results = []
        total = len(games)
        for i, row in enumerate(games):
            print(f"[{i+1}/{total}] Processing: {row['name']}")
            driver.get(row["link"])
            time.sleep(1)
            
            results.append({
                "排名": row["rank"],
                "名称": row["name"],
                "标签": ", ".join([t.text.strip() for t in driver.find_elements(By.CSS_SELECTOR, "a.app-intro__tag-item")]),
                "厂商": get_publisher(driver),
                "预约/关注量": get_max_reserve_num(driver),
                "简介": get_intro_full(driver)
            })

        if results:
            df = pd.DataFrame(results)
            df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
            print(f"✅ Success: {OUTPUT_FILE}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
