import time
import pandas as pd
from bs4 import BeautifulSoup
import os
import re
import sys
import shutil
from datetime import datetime
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

SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 100))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "SteamDB_Result.csv")

# ================= 核心驱动配置 =================
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

# ================= 数据清洗与解析函数 =================
def parse_date_from_title(title_text):
    try:
        date_range_match = re.search(r'week of\s+([\d]{1,2} [A-Za-z]+)(?: ([\d]{4}))?\s*[—–\-]\s*([\d]{1,2} [A-Za-z]+) ([\d]{4})', title_text)
        if date_range_match:
            start_date, start_year, end_date, end_year = date_range_match.groups()
            real_start_year = start_year if start_year else end_year
            for fmt in ("%d %b %Y", "%d %B %Y"):
                try:
                    dt_obj = datetime.strptime(f"{start_date} {real_start_year}", fmt)
                    return dt_obj.strftime("%Y-%m-%d")
                except Exception: continue
            return ""
        else:
            year_match = re.search(r'— ?\d{1,2} [A-Za-z]+ (\d{4})', title_text)
            if not year_match: year_match = re.search(r'(\d{4})', title_text)
            year = year_match.group(1) if year_match else str(datetime.now().year)
            date_match = re.search(r'week of\s+((?:\d{1,2} [A-Za-z]+))\s+[—–-]', title_text)
            if not date_match: date_match = re.search(r'week of\s*([^\—\–\-]+)', title_text)
            if date_match:
                start_date_str = date_match.group(1).strip()
                for fmt in ("%d %b %Y", "%d %B %Y"):
                    try:
                        dt_obj = datetime.strptime(f"{start_date_str} {year}", fmt)
                        return dt_obj.strftime("%Y-%m-%d")
                    except Exception: continue
        return ""
    except Exception: return ""

def parse_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    week_num_tag = soup.select_one('.pre-table-title span')
    week_num_text = week_num_tag.get_text(strip=True) if week_num_tag else ""
    title_tag = soup.select_one('.pre-table-title h2')
    raw_title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"
    final_period_text = f"{week_num_text}: {raw_title}" if week_num_text else raw_title
    dt_value = parse_date_from_title(raw_title)

    table = soup.find('table', class_='table-products')
    if not table: return []

    rows = table.find('tbody').find_all('tr')
    data_list = []
    for row in rows:
        cols = row.find_all('td')
        if not cols: continue
        rank = cols[0].get_text(strip=True).replace('.', '')   
        name = cols[2].get_text(strip=True)                    
        price = cols[3].get_text(strip=True) or ""             
        
        change_col = cols[4]
        change_text = change_col.get_text(strip=True)
        if "seller-pos-up" in str(change_col): change = f"+{change_text}"
        elif "seller-pos-down" in str(change_col): change = f"-{change_text}"
        else: change = change_text or ""

        dev = cols[5].get_text(strip=True)                     
        release = cols[6].get_text(strip=True)                 

        data_list.append({
            'Week Period': final_period_text,
            'dt': dt_value,
            'Rank': rank,
            'Game Name': name,
            'Price': price,
            'Change': change,
            'Developer': dev,
            'Release Date': release
        })
    return data_list

# ================= 爬虫主逻辑 =================
def run_scraper():
    print(f"SteamDB Kernel Running: 目标获取 {SCRAPE_LIMIT} 条畅销榜数据")
    driver = init_driver()
    all_weeks_data = []

    try:
        url = "https://steamdb.info/topsellers/"
        driver.get(url)

        # SteamDB 每页大概 100 条数据，支持翻页获取历史周
        max_pages = max(1, (SCRAPE_LIMIT // 100) + 1)
        
        for i in range(max_pages):
            try:
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "table-products")))
                time.sleep(2)  
            except Exception:
                print("⚠️ 等待表格超时，可能触发了 Cloudflare 盾，请稍后再试。")
                break

            page_source = driver.page_source
            current_week_data = parse_html(page_source)

            if current_week_data:
                dt_this = current_week_data[0].get('dt', "")
                week_desc = current_week_data[0].get('Week Period', "")[:30]
                
                # 截断拼接
                remaining_slots = SCRAPE_LIMIT - len(all_weeks_data)
                data_to_add = current_week_data[:remaining_slots]
                all_weeks_data.extend(data_to_add)
                
                print(f"[{len(all_weeks_data)}/{SCRAPE_LIMIT}] 解析成功 -> 日期: {dt_this} | 周期: {week_desc}...")
                
                if len(all_weeks_data) >= SCRAPE_LIMIT:
                    break
            else:
                break

            # 翻到上一周
            try:
                prev_button = driver.find_element(By.CSS_SELECTOR, "a[rel='prev']")
                driver.execute_script("arguments[0].click();", prev_button)
                time.sleep(3)
            except Exception:
                break

        if all_weeks_data:
            df = pd.DataFrame(all_weeks_data)
            output_cols = ['dt', 'Rank', 'Week Period', 'Game Name', 'Price', 'Change', 'Developer', 'Release Date']
            df = df[[c for c in output_cols if c in df.columns]]
            df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
            print(f"✅ 成功! 文件已保存: {OUTPUT_FILE}")
        else:
            print("未能提取到任何数据。")

    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_scraper()
