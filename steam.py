import time
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains # 引入鼠标轨迹模拟
from datetime import datetime
import re
import os
import sys
import shutil
import warnings

# === 屏蔽干扰日志并强制 UTF-8 输出 ===
warnings.filterwarnings("ignore")
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# === 环境变量读取 ===
SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 5))
WEEKS_TO_SCRAPE = int(os.environ.get("WEEKS_TO_SCRAPE", 1))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "Steam_Result.csv")

def get_stealth_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # 模拟真实环境
    options.add_argument("--force-device-scale-factor=1")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7")
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    options.add_argument(f'user-agent={ua}')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # 动态锁定系统路径
    chrome_bin = "/usr/bin/chromium"
    driver_bin = "/usr/bin/chromedriver"
    if not os.path.exists(chrome_bin):
        chrome_bin = shutil.which("chromium") or shutil.which("chromium-browser")
    if not os.path.exists(driver_bin):
        driver_bin = shutil.which("chromedriver")

    options.binary_location = chrome_bin
    service = Service(executable_path=driver_bin)
    driver = webdriver.Chrome(service=service, options=options)

    # 注入隐身脚本
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """
    })
    return driver

def parse_date_from_title(title_text):
    # [保留你原本完美的日期解析逻辑...]
    try:
        date_range_match = re.search(r'week of\s+([\d]{1,2} [A-Za-z]+)(?: ([\d]{4}))?\s*[—–\-]\s*([\d]{1,2} [A-Za-z]+) ([\d]{4})', title_text)
        if date_range_match:
            start_date, start_year, end_date, end_year = date_range_match.groups()
            real_start_year = start_year if start_year else end_year
            for fmt in ("%d %b %Y", "%d %B %Y"):
                try: return datetime.strptime(f"{start_date} {real_start_year}", fmt).strftime("%Y-%m-%d")
                except Exception: continue
        else:
            year_match = re.search(r'— ?\d{1,2} [A-Za-z]+ (\d{4})', title_text)
            year = year_match.group(1) if year_match else str(datetime.now().year)
            date_match = re.search(r'week of\s*([^\—\–\-]+)', title_text)
            if date_match:
                start_date_str = date_match.group(1).strip()
                for fmt in ("%d %b %Y", "%d %B %Y"):
                    try: return datetime.strptime(f"{start_date_str} {year}", fmt).strftime("%Y-%m-%d")
                    except Exception: continue
    except: pass
    return ""

def parse_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    week_num_tag = soup.select_one('.pre-table-title span')
    title_tag = soup.select_one('.pre-table-title h2')
    week_num_text = week_num_tag.get_text(strip=True) if week_num_tag else ""
    raw_title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"
    final_period_text = f"{week_num_text}: {raw_title}" if week_num_text else raw_title
    dt_value = parse_date_from_title(raw_title)

    table = soup.find('table', class_='table-products')
    if not table: return []

    rows = table.find('tbody').find_all('tr')[:SCRAPE_LIMIT]
    data_list = []

    for row in rows:
        cols = row.find_all('td')
        if not cols: continue
        change_col = cols[4]
        change_text = change_col.get_text(strip=True)
        if "seller-pos-up" in str(change_col): change = f"+{change_text}"
        elif "seller-pos-down" in str(change_col): change = f"-{change_text}"
        else: change = change_text or ""

        data_list.append({
            'week': final_period_text, 'dt': dt_value,
            'rank': cols[0].get_text(strip=True).replace('.', ''),
            'name': cols[2].get_text(strip=True),
            'ifree': cols[3].get_text(strip=True) or "",
            'change': change,
            'developer': cols[5].get_text(strip=True),
            'releasedate': cols[6].get_text(strip=True)
        })
    return data_list

def bypass_cloudflare(driver):
    """使用拟人化鼠标轨迹穿透 Cloudflare"""
    for attempt in range(2):
        time.sleep(10) 
        if "table-products" in driver.page_source: return True
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for frame in iframes:
                src = frame.get_attribute("src") or ""
                if "challenges" in src or "turnstile" in src:
                    driver.switch_to.frame(frame)
                    # 模拟真实鼠标移动和点击
                    try:
                        target = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='checkbox'], #challenge-stage"))
                        )
                        actions = ActionChains(driver)
                        actions.move_to_element(target).pause(0.5).click().perform()
                        print("✨ 人机轨迹模拟点击成功！")
                    except:
                        driver.find_element(By.TAG_NAME, "body").click()
                    driver.switch_to.default_content()
                    time.sleep(8)
                    break
            driver.execute_script("window.scrollBy(0, 100);")
            if "table-products" in driver.page_source: return True
            else: driver.refresh()
        except: driver.switch_to.default_content()
    return False

def scrape_steamdb_history():
    print(f"Steam Kernel Running: Target Top {SCRAPE_LIMIT} for {WEEKS_TO_SCRAPE} weeks")
    driver = get_stealth_driver()
    all_weeks_data = []

    try:
        url = "https://steamdb.info/topsellers/"
        driver.get(url)

        for i in range(WEEKS_TO_SCRAPE):
            print(f"[{i+1}/{WEEKS_TO_SCRAPE}] 正在处理第 {i+1} 周数据...")

            if i == 0 and not bypass_cloudflare(driver):
                time.sleep(10)

            try:
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, "table-products")))
                time.sleep(2) 
            except Exception:
                print(f"❌ 穿透失败，等待表格超时。已被 Cloudflare WAF 拦截。")
                break

            current_week_data = parse_html(driver.page_source)
            if current_week_data: all_weeks_data.extend(current_week_data)

            if i == WEEKS_TO_SCRAPE - 1: break

            try:
                prev_button = driver.find_element(By.CSS_SELECTOR, "a[rel='prev']")
                driver.execute_script("arguments[0].click();", prev_button)
                time.sleep(5)
            except Exception: break

    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        # 安全退出驱动
        if 'driver' in locals(): driver.quit()
        
    # === 修复点：移出 finally 代码块 ===
    return all_weeks_data

if __name__ == "__main__":
    final_data = scrape_steamdb_history()

    if final_data:
        df = pd.DataFrame(final_data)
        df = df.rename(columns={
            'week': 'Week Period', 'dt': 'dt', 'rank': 'Rank',
            'name': 'Game Name', 'ifree': 'Price', 'change': 'Change',
            'developer': 'Developer', 'releasedate': 'Release Date'
        })
        output_cols = [col for col in ['dt', 'Rank', 'Week Period', 'Game Name', 'Price', 'Change', 'Developer', 'Release Date'] if col in df.columns]
        df = df[output_cols]
        if 'dt' in df.columns:
            df['dt'] = df['dt'].astype(str).apply(lambda x: pd.to_datetime(x, errors='coerce').strftime('%Y-%m-%d') if pd.notna(x) and x != '' else x)
        df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        print(f"File Saved: {OUTPUT_FILE}")
