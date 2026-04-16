import os
import sys
import time
import warnings
import requests
from bs4 import BeautifulSoup
import pandas as pd

# === 屏蔽干扰日志并强制 UTF-8 输出 ===
warnings.filterwarnings("ignore")
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# === 环境变量读取 (由指挥官 app.py 传参) ===
SCRAPE_LIMIT = int(os.environ.get("SCRAPE_LIMIT", 5))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "Steam_Result.csv")

def scrape_steam_wishlist():
    base_url = "https://games-popularity.com"
    target_url = f"{base_url}/steam/top-wishlist"
    
    # 模拟浏览器头部，防止被基础反爬拦截
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    all_data = []
    page = 1
    
    print(f"Steam Kernel Running: Target Top {SCRAPE_LIMIT} Wishlist")

    while len(all_data) < SCRAPE_LIMIT:
        url = f"{target_url}/{page}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"页面请求失败: {response.status_code}")
                break

            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', id='table_wishlist')

            if not table:
                print("未找到表格，结束爬取。")
                break

            # 获取所有数据行 (排除表头)
            rows = table.find('tbody').find_all('tr')

            for row in rows:
                if len(all_data) >= SCRAPE_LIMIT:
                    break

                cols = row.find_all('td')
                if not cols or len(cols) < 7:
                    continue

                # 1. 提取 Rank (去除末尾的点)
                rank = cols[0].get_text(strip=True).replace('.', '')

                # 2. 提取 Name & Link 
                name_tag = cols[2].find('a')
                if name_tag:
                    name = name_tag.get_text(strip=True)
                    link = base_url + name_tag['href']
                else:
                    name = "N/A"
                    link = ""

                # 3. 提取 7天和30天热度变化
                change_7d = cols[4].get_text(strip=True)
                change_30d = cols[5].get_text(strip=True)

                # 4. 提取 Developer / Publisher 
                dev_pub_text = cols[6].get_text(strip=True)
                if " / " in dev_pub_text:
                    parts = dev_pub_text.split(" / ", 1)
                    developer = parts[0].strip()
                    publisher = parts[1].strip()
                else:
                    developer = dev_pub_text
                    publisher = dev_pub_text

                # === 配合 app.py 的实时进度条打印 ===
                print(f"[{len(all_data)+1}/{SCRAPE_LIMIT}] Processing: {name}")

                all_data.append({
                    "排名": rank,
                    "游戏名称": name,
                    "7日变化": change_7d,
                    "30日变化": change_30d,
                    "开发商": developer,
                    "发行商": publisher,
                    "参考链接": link
                })

            page += 1
            # 如果还需要翻页，稍微停顿一下礼貌抓取
            if len(all_data) < SCRAPE_LIMIT:
                time.sleep(1) 

        except Exception as e:
            print(f"发生错误: {e}")
            break

    # === 保存文件，通知系统链路 ===
    if all_data:
        df = pd.DataFrame(all_data)
        # 必须保存为 CSV，且命名为 OUTPUT_FILE，否则 app.py 找不到数据
        df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        print(f"File Saved: {OUTPUT_FILE}")
    else:
        print("没有抓取到数据。")

if __name__ == "__main__":
    scrape_steam_wishlist()
