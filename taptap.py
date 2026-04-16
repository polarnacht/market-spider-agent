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

# === 屏蔽警告并强制 UTF-8 输出，防止进度条截取特殊字符时崩溃 ===
import warnings
warnings.filterwarnings("ignore")
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# === 读取环境变量 ===
SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 5))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "TapTap_Result.csv")

BASE_URL = "https://www.taptap.cn"

def init_driver():
    options = Options()
    # === 针对云端 Linux 环境的核心配置 ===
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")

    # === 核心修改：动态寻找 Chromium 和 Chromedriver 的路径 ===
    chromium_path = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    chromedriver_path = shutil.which("chromedriver")

    if chromium_path:
        options.binary_location = chromium_path

    if chromedriver_path:
        service = Service(executable_path=chromedriver_path)
    else:
        service = Service()

    driver = webdriver.Chrome(service=service, options=options)

    # CDP 隐身注入
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
        if new_height == last_height:
            break
        last_height = new_height
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(wait_time)

def get_absolute_link(href, base_url=BASE_URL):
    if href.startswith("/"):
        return base_url + href
    return href

def get_game_list(driver):
    print("正在滚动加载首页榜单数据...")
    scroll_to_bottom_then_top(driver)
    games = driver.find_elements(By.CSS_SELECTOR, "div.rank-game-cell")
    game_list = []

    # 截断数量，只处理 SCRAPE_LIMIT 指定的个数
    target_games = games[:SCRAPE_LIMIT]

    for i, game in enumerate(target_games):
        try:
            rank = game.find_element(By.CSS_SELECTOR, "span.rank-index").text.strip()
            name_element = game.find_element(By.CSS_SELECTOR, "div.text-with-tags.app-title span.text-default--size")
            name = name_element.text.strip()
            links = game.find_elements(By.CSS_SELECTOR, "a[href^='/app/']")
            link = get_absolute_link(links[0].get_attribute("href")) if links else ""
            game_list.append({"rank": rank, "name": name, "link": link})
        except Exception as e:
            continue
    return game_list

# === 核心修改点：化繁为简，只提取全局预约/关注总量 ===
def get_single_metric(driver):
    def normalize_number(text):
        text = text.replace("人", "").replace(",", "").strip()
        try:
            if "万" in text:
                return int(float(re.sub(r"[^\d\.]", "", text)) * 10000)
            else:
                return int(float(re.sub(r"[^\d\.]", "", text)))
        except:
            return 0

    def grab_data():
        try:
            info_boxes = driver.find_elements(By.CSS_SELECTOR, "div.single-info")
            for box in info_boxes:
                key = box.find_element(By.CSS_SELECTOR, ".caption-m12-w12").text.strip()
                val = box.find_element(By.CSS_SELECTOR, ".single-info__content__value").text.strip()
                if key in ["预约", "关注"]:
                    return normalize_number(val)
        except:
            pass
        return 0

    # 1. 优先尝试从默认加载的页面抓取总数
    num = grab_data()
    if num > 0:
        return num
        
    # 2. 兜底方案：如果默认页没加载出来，尝试点击第一个平台按钮激活数据
    try:
        btns = driver.find_elements(By.CSS_SELECTOR, "div.platform-picker-switch__item")
        if btns:
            driver.execute_script("arguments[0].click();", btns[0])
            time.sleep(0.5)
            return grab_data()
    except:
        pass
        
    return 0

def get_additional_info(driver):
    try:
        tag_elements = driver.find_elements(By.CSS_SELECTOR, "a.app-intro__tag-item")
        return ", ".join([tag.text.strip() for tag in tag_elements])
    except:
        return ""

def get_publisher(driver):
    """
    多重 Fallback 机制提取厂商信息，大幅提高容错率
    """
    # === 策略 1：针对最新 HTML 结构 (包含“供应商”、“开发商”的单行文本) ===
    try:
        elements = driver.find_elements(By.XPATH, "//*[contains(text(), '供应商') or contains(text(), '发行商') or contains(text(), '开发商')]")
        for el in elements:
            text = el.text.strip()
            if 2 < len(text) < 40: 
                for prefix in ["供应商", "发行商", "开发商", "厂商", ":", "：", " "]:
                    text = text.replace(prefix, "")
                if text:
                    return text.strip()
    except:
        pass

    # === 策略 2：兼容旧版 TapTap 的兄弟节点结构 ===
    try:
        return driver.find_element(By.XPATH, "//div[contains(text(),'发行') or contains(text(),'厂商') or contains(text(),'开发')]/following-sibling::div").text.strip()
    except:
        pass
        
    # === 策略 3：直接寻找常见的开发者 class 锚点 ===
    try:
        return driver.find_element(By.CSS_SELECTOR, "a.developer-name, span.developer-text").text.strip()
    except:
        pass

    return "暂无信息"

def get_intro_full(driver):
    try:
        summary = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.app-intro__summary")))
        driver.execute_script("arguments[0].click();", summary)
        time.sleep(0.5)
        summary_div = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.text-modal.paragraph-m14-w14")))
        return summary_div.text.strip()
    except:
        return ""

def save_detailed_data_to_csv(data):
    df = pd.DataFrame(data)
    # 强制限定并重排导出的列，抛弃冗余平台列
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
        time.sleep(3) # 给首页留点渲染时间

        # 获取经过 SCRAPE_LIMIT 截断的游戏列表
        games = get_game_list(driver)
        results = []
        total_games = len(games)

        for i, row in enumerate(games):
            try:
                # === 配合 app.py 实时进度条打印 ===
                print(f"[{i+1}/{total_games}] Processing Detail: {row['name']}")
                
                driver.get(row["link"])
                time.sleep(1)
                
                tags_str = get_additional_info(driver)
                factory = get_publisher(driver)
                intro = get_intro_full(driver)
                
                # 直接获取合并后的整体数值
                reserve_num = get_single_metric(driver)

                result = {
                    "排名": row["rank"],
                    "名称": row["name"],
                    "简介": intro[:150] + "..." if len(intro) > 150 else intro,  
                    "标签": tags_str,
                    "厂商": factory,
                    "预约/关注量": reserve_num if reserve_num > 0 else "暂无数据"
                }

                results.append(result)
            except Exception as e:
                continue

        # 保存到动态指定的文件
        if results:
            save_detailed_data_to_csv(results)
        else:
            print("未能抓取到任何有效数据。")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
