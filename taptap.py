import time
import csv
import pandas as pd
import os  # === 改动点 1：引入 os ===
from selenium import webdriver
from dateutil.relativedelta import relativedelta
import json
import re
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# === 改动点 2：读取环境变量 ===
# 指挥官 app.py 会把这些参数传进来，如果没有传，则使用默认值
SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 5))  # 默认采集5个
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "国内预约榜.csv")  # 动态文件名

BASE_URL = "https://www.taptap.cn"


# BASE_DIR 不再写死，直接存放在当前目录下即可

def init_driver():
    options = Options()
    # === 改动点 3：强制开启无头模式，否则云端部署会报错 ===
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver


# ... [scroll_to_bottom_then_top 等中间函数保持完全不变] ...

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
    scroll_to_bottom_then_top(driver)
    games = driver.find_elements(By.CSS_SELECTOR, "div.rank-game-cell")
    game_list = []

    # === 改动点 4：在这里截断数量，只处理 SCRAPE_LIMIT 指定的个数 ===
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


# ... [get_platforms_data, get_additional_info, get_publisher, get_intro_full 保持完全不变] ...

def get_platforms_data(driver):
    def normalize_number(text):
        text = text.replace("人", "").replace(",", "").strip()
        try:
            if "万" in text:
                num = float(re.sub(r"[^\d\.]", "", text)) * 10000
            else:
                num = float(re.sub(r"[^\d\.]", "", text))
            return int(num)
        except:
            return text

    platforms_data = {}
    try:
        platform_buttons = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.platform-picker-switch__item"))
        )
        for i in range(len(platform_buttons)):
            platform_buttons = driver.find_elements(By.CSS_SELECTOR, "div.platform-picker-switch__item")
            button = platform_buttons[i]
            platform_name = button.find_element(By.CLASS_NAME, "font-bold").text.strip()
            driver.execute_script("arguments[0].click();", button)
            time.sleep(1)
            platform_info = {}
            info_boxes = driver.find_elements(By.CSS_SELECTOR, "div.single-info")
            for box in info_boxes:
                key = box.find_element(By.CSS_SELECTOR, ".caption-m12-w12").text.strip()
                val = box.find_element(By.CSS_SELECTOR, ".single-info__content__value").text.strip()
                if key in ["预约", "关注"]:
                    platform_info[key] = normalize_number(val)
            platforms_data[platform_name] = platform_info
    except:
        pass
    return platforms_data


def get_additional_info(driver):
    try:
        tag_elements = driver.find_elements(By.CSS_SELECTOR, "a.app-intro__tag-item")
        return ", ".join([tag.text.strip() for tag in tag_elements])
    except:
        return ""


def get_publisher(driver):
    try:
        return driver.find_element(By.XPATH,
                                   "//div[contains(text(),'发行') or contains(text(),'厂商') or contains(text(),'开发')]/following-sibling::div").text.strip()
    except:
        return ""


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


# === 改动点 5：修改保存函数，使用 OUTPUT_FILE ===
def save_detailed_data_to_csv(data):
    df = pd.DataFrame(data)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"[INFO] 详细数据已保存至 {OUTPUT_FILE}")


def main():
    driver = init_driver()
    url = "https://www.taptap.cn/top/reserve"
    driver.get(url)

    # 获取经过 SCRAPE_LIMIT 截断的游戏列表
    games = get_game_list(driver)
    results = []

    for i, row in enumerate(games):
        try:
            driver.get(row["link"])
            time.sleep(1)
            detail = get_platforms_data(driver)
            tags_str = get_additional_info(driver)
            factory = get_publisher(driver)
            intro = get_intro_full(driver)

            result = {
                "排名": row["rank"],
                "名称": row["name"],
                "简介": intro[:150] + "..." if len(intro) > 150 else intro,  # 限制长度防止表格太长
                "标签": tags_str,
                "厂商": factory,
            }
            # 整合平台数据
            for plat in ["安卓", "iOS", "PC端"]:
                if plat in detail:
                    result[f"{plat}平台"] = str(detail[plat])
                else:
                    result[f"{plat}平台"] = ""

            results.append(result)
        except Exception as e:
            continue

    # 保存到动态指定的文件
    save_detailed_data_to_csv(results)
    driver.quit()


if __name__ == "__main__":
    main()