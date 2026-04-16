import time
import pandas as pd
import os
import re
import sys
import shutil
from bs4 import BeautifulSoup
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

# === 从环境变量获取调度参数 ===
SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 10))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "Douban_Result.csv")
# 接收标签：国产剧/欧美剧/韩剧/日剧
TARGET_TAG = os.environ.get("DOUBAN_TAG", "国产剧")

def clean_text(text):
    if not text: return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

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
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
    })
    return driver

def get_detail_page_data(driver, url):
    data = {"reviews": "", "description": ""}
    if not url or url == "N/A": return data
    try:
        # 兼容手机端分享链接
        request_url = url
        if "doubanapp/dispatch" in url:
            tv_id_match = re.search(r'/tv/(\d+)', url)
            if tv_id_match: request_url = f"https://movie.douban.com/subject/{tv_id_match.group(1)}/"
        
        driver.get(request_url)
        time.sleep(2) # 豆瓣详情页渲染较慢，多等一会
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # 提取评价人数
        vote_tag = soup.find(attrs={"property": "v:votes"})
        if vote_tag: data['reviews'] = vote_tag.get_text(strip=True)
        
        # 提取简介 (优先取隐藏的全文)
        summary_hidden = soup.find(class_=re.compile(r"all\s+hidden"))
        if summary_hidden:
            data['description'] = clean_text(summary_hidden.get_text())
        else:
            summary_tag = soup.find(attrs={"property": "v:summary"})
            if summary_tag: data['description'] = clean_text(summary_tag.get_text())
    except: pass
    return data

def scrape_douban():
    print(f"🚀 Douban Kernel Starting: Target={TARGET_TAG}, Limit={SCRAPE_LIMIT}")
    driver = init_driver()
    try:
        driver.get("https://movie.douban.com/tv/")
        wait = WebDriverWait(driver, 15)
        
        # --- 1. 动态点击分类标签 ---
        try:
            # 豆瓣的标签文本可能包含“欧美”、“韩剧”等
            tag_xpath = f"//li[contains(@class, 'explore-menu-second-tag') and text()='{TARGET_TAG}']"
            wait.until(EC.element_to_be_clickable((By.XPATH, tag_xpath))).click()
            time.sleep(3)
        except Exception as e:
            print(f"❌ 点击分类标签 '{TARGET_TAG}' 失败，使用默认分类。")

        # --- 2. 瀑布流滚动加载 ---
        last_count = 0
        while True:
            items = driver.find_elements(By.CSS_SELECTOR, '.drc-subject-info-subtitle')
            count = len(items)
            if count >= SCRAPE_LIMIT: break
            if count == last_count: break # 到底了
            last_count = count
            
            try:
                # 尝试点击加载更多
                load_more = driver.find_element(By.XPATH, "//button[contains(text(), '加载更多')]")
                driver.execute_script("arguments[0].click();", load_more)
            except:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        # --- 3. 解析列表 ---
        print("📋 Parsing list...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        subtitles = soup.find_all(class_="drc-subject-info-subtitle")
        raw_results = []
        for sub in subtitles[:SCRAPE_LIMIT]:
            a_tag = sub.find_parent('a')
            if not a_tag: continue
            
            name = a_tag.find(class_=re.compile("title-text")).get_text(strip=True) if a_tag.find(class_=re.compile("title-text")) else "未知"
            raw_url = a_tag.get('href', '')
            link = raw_url
            tv_id_match = re.search(r'subject/(\d+)', raw_url)
            if tv_id_match: link = f"https://www.douban.com/doubanapp/dispatch?uri=/tv/{tv_id_match.group(1)}"
            
            sub_text = sub.get_text(strip=True)
            parts = [p.strip() for p in sub_text.split('/')]
            
            rating_tag = a_tag.find(class_="drc-rating-num")
            points = rating_tag.get_text(strip=True) if rating_tag else ""
            
            raw_results.append({
                "名称": name,
                "链接": link,
                "年份": parts[0] if len(parts) > 0 else "",
                "评分": points if points != "暂无评分" else "暂无",
                "标签": parts[2] if len(parts) > 2 else ""
            })

        # --- 4. 遍历抓取详情 ---
        final_data = []
        total = len(raw_results)
        for i, item in enumerate(raw_results):
            # 关键：打印符合 app.py 正则的进度日志
            print(f"[{i+1}/{total}] Fetching detail for: {item['名称']}")
            
            detail = get_detail_page_data(driver, item['链接'])
            item["评价人数"] = detail['reviews']
            item["剧情简介"] = detail['description'][:150] + "..." if len(detail['description']) > 150 else detail['description']
            final_data.append(item)

        if final_data:
            df = pd.DataFrame(final_data)
            df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
            print(f"✅ Success: {OUTPUT_FILE}")
        else:
            print("未能提取到任何有效数据。")

    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_douban()
