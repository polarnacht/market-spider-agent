import streamlit as st
import pandas as pd
import subprocess
import os
import re
import uuid
import sys
from datetime import datetime
from openai import OpenAI

# ================= 1. 核心配置与 UI 样式 =================
# 建议在生产环境通过 st.secrets 配置
API_KEY = st.secrets.get("api_key", "sk-cc6655649d204550bd5bcffd355ab4dd")
BASE_URL = "https://api.deepseek.com"
CLIENT = OpenAI(api_key=API_KEY, base_url=BASE_URL)

st.set_page_config(page_title="泛娱乐情报 Agent", layout="wide", page_icon="🛡️")

# 自定义 CSS：优化看板美观度与紧凑感
st.markdown("""
    <style>
    .main { background-color: #f9fafb; }
    div[data-testid="stExpander"] { border: 1px solid #e5e7eb; border-radius: 8px; background-color: white; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
    .stMetric { border: 1px solid #f3f4f6; padding: 10px; border-radius: 8px; background: #fff; }
    .stChatFloatingInputContainer { background-color: rgba(255,255,255,0.9); }
    h1 { color: #1f2937; font-weight: 700; }
    h4 { color: #374151; border-left: 4px solid #3b82f6; padding-left: 10px; margin-top: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 侧边栏：状态控制台 ---
with st.sidebar:
    st.title("🛡️ 系统调度中心")
    if st.button("🧹 重置当前会话"):
        st.session_state.history = []
        st.rerun()
    
    st.divider()
    st.subheader("⚙️ 内核引擎状态")
    c1, c2 = st.columns(2)
    c1.caption("🟢 容器化隔离")
    c1.caption("🟢 文本穿透提取")
    c2.caption("🟢 跨模态分析")
    c2.caption("🟢 参数自动补全")
    st.divider()
    st.markdown("**指令协议说明**")
    st.caption("指令 = [动作] + [对象] + [参数]")
    st.caption("参数支持：年份、月份、具体名次")

# --- 3. 数据源规格与能力边界 (产品级文档) ---
st.title("泛娱乐市场情报提取与分析 Agent")

with st.expander("📝 数据源规格说明书", expanded=True):
    m1, m2, m3 = st.columns(3)
    
    with m1:
        st.markdown("#### 📱 手游矩阵")
        st.markdown("""
        **TapTap 预约榜**
        - **属性**：实时热度、厂商、预约/关注量
        - **限制**：仅当前快照，不支持回溯
        
        **玩匠 开测榜**
        - **属性**：测试节点、测试类型、最高预约量
        - **指定**：支持指定**年份、月份** (缺省取当前)
        """)

    with m2:
        st.markdown("#### 💻 PC & 直播热度")
        st.markdown("""
        **Steam 愿望榜**
        - **属性**：人气动能、7日/30日热度增量
        - **限制**：实时接口，不支持历史回溯
        
        **直播热度榜 (国内/国外)**
        - **属性**：活跃观众、主播数、弹幕、观看时长
        - **指定**：国内(播酱)按月；国外(Twitch)近30日
        """)

    with m3:
        st.markdown("#### 🎬 影视 IP")
        st.markdown("""
        **豆瓣 影视榜**
        - **属性**：评分、评价数、剧情简介
        - **指定**：支持 **国产/日剧/欧美/韩剧** 分类
        
        **IMDb 趋势榜**
        - **属性**：全球IP热度趋势、评分、制作年份
        - **指定**：支持指定**年份、月份**进行回溯
        """)

# --- 4. 交互引导 ---
st.markdown("### 💡 快速开始")
t1, t2, t3 = st.columns(3)
t1.info("**单点深度提取**\n`提取 2026年3月 玩匠前 50名`")
t2.info("**行业模块联动**\n`分析 目前所有直播热度情况`")
t3.info("**全局跨界分析**\n`生成 4月 泛娱乐全行业简报`")

st.markdown("---")

# ================= 5. 自动化调度内核 =================

def run_spider_with_progress(script_name, params):
    task_id = str(uuid.uuid4())[:8]
    output_csv = f"result_{task_id}.csv"
    env = os.environ.copy()
    env.update(params)
    env["OUTPUT_FILE"] = output_csv

    # 使用子进程执行，-u 确保输出流实时同步
    process = subprocess.Popen(
        [sys.executable, "-u", os.path.abspath(script_name)], 
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
        text=True, encoding="utf-8", errors='replace'
    )

    progress_bar = st.progress(0)
    status_box = st.empty()

    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None: break
        if line:
            clean_line = line.strip()
            status_box.caption(f"⚙️ 引擎日志 [{script_name}]: {clean_line}")
            # 捕获进度标志 [当前/总数]
            prog_match = re.search(r"\[(\d+)/(\d+)\]", clean_line)
            if prog_match:
                progress_bar.progress(min(int(prog_match.group(1)) / int(prog_match.group(2)), 1.0))

    return process.wait(), output_csv

def parse_intent(prompt):
    p = prompt.lower()
    
    # 1. 提取数量限制
    num_match = re.search(r'(\d+)名|前\s*(\d+)|(\d+)条', prompt)
    explicit_num = num_match.group(1) or num_match.group(2) or num_match.group(3) if num_match else None
    
    # 2. 提取时间参数
    date_match = re.search(r'(\d{4})[年-]\s*(\d{1,2})', prompt)
    month_only_match = re.search(r'(\d{1,2})月', prompt)
    now = datetime.now()
    year = date_match.group(1) if date_match else str(now.year)
    if date_match:
        month = date_match.group(2).zfill(2)
    elif month_only_match:
        month = month_only_match.group(1).zfill(2)
    else:
        month = str(now.month).zfill(2)

    # 3. 确定大盘采集模式
    is_macro = any(kw in p for kw in ["所有", "整体", "大盘", "全局", "全行业", "简报", "综合"])
    
    # 4. 参数配置协议 (指定 > 宏观默认 > 单点默认)
    limit_heavy = explicit_num if explicit_num else ("20" if is_macro else "5")
    limit_normal = explicit_num if explicit_num else ("200" if is_macro else "5")

    tasks = []

    # --- 路由引擎 ---
    # 手游分类
    if any(kw in p for kw in ["手游", "taptap", "玩匠", "测试", "移动端"]):
        if is_macro or "tap" in p:
            tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": limit_normal}})
        if is_macro or "玩匠" in p or "开测" in p:
            tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": limit_heavy, "YEAR": year, "MONTH": month}})

    # PC与直播分类
    if any(kw in p for kw in ["pc", "steam", "直播", "热度", "twitch"]):
        if is_macro or "steam" in p or "愿望" in p:
            tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": limit_normal}})
        if is_macro or "直播" in p or "热度" in p:
            tasks.append({"script": "domestic_live.py", "env": {"SCRAPE_LIMIT": limit_normal}})
            tasks.append({"script": "intl_live.py", "env": {"SCRAPE_LIMIT": limit_normal}})

    # 泛娱乐与影视分类
    if any(kw in p for kw in ["影视", "豆瓣", "imdb", "剧", "全行业", "泛娱乐"]):
        if is_macro or "imdb" in p:
            tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": limit_normal, "YEAR": year, "MONTH": month}})
        if is_macro or "豆瓣" in p or "剧" in p:
            db_tag = "欧美剧" if "欧美" in p else "韩剧" if "韩" in p else "日剧" if "日" in p else "国产剧"
            tasks.append({"script": "douban.py", "env": {"SCRAPE_LIMIT": limit_heavy, "DOUBAN_TAG": db_tag}})
            
    return tasks

# --- 6. 会话交互流 ---
if "history" not in st.session_state: st.session_state.history = []

for chat in st.session_state.history:
    with st.chat_message(chat["role"]): st.markdown(chat["content"])

if prompt := st.chat_input("输入提取指令..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    tasks = parse_intent(prompt)
    if tasks:
        results_md = []
        total_count = 0
        with st.status(f"🚀 调度中心已受理 (识别到 {len(tasks)} 个并行任务)...", expanded=True) as status:
            for task in tasks:
                # 模块展示名称映射
                name_map = {
                    "taptap.py": "TapTap预约", "wanjiang.py": "玩匠开测", "steam.py": "Steam愿望",
                    "domestic_live.py": "国内直播", "intl_live.py": "Twitch直播",
                    "douban.py": "豆瓣影视", "imdb.py": "IMDb趋势"
                }
                m_display = name_map.get(task["script"], task["script"])
                st.write(f"正在激活引擎：`{m_display}` ...")
                
                code, res_csv = run_spider_with_progress(task["script"], task["env"])
                
                if code == 0 and os.path.exists(res_csv):
                    df = pd.read_csv(res_csv)
                    total_count += len(df)
                    st.success(f"✅ {m_display} 完成 ({len(df)} 条)")
                    st.dataframe(df, use_container_width=True)
                    results_md.append(f"### {m_display} 原始数据\n" + df.to_markdown(index=False))
                    os.remove(res_csv)
                else:
                    st.error(f"❌ {m_display} 运行异常")

            if total_count > 0:
                status.update(label="数据汇集完毕，开始商业逻辑分析...", state="running")
                ai_prompt = f"""你是一位资深商业分析师。基于提供的多源实时数据表，为高管提供简报。
                数据内容：\n{"\n\n".join(results_md)}
                分析要求：
                1. 识别具有“断层热度”或“异常表现”的标的。
                2. 分析跨领域（如游戏与影视、直播热度与发售预期）的关联规律。
                3. 关键数字必须加粗，结论必须具备战略启示。
                """
                with st.chat_message("assistant"):
                    try:
                        resp = CLIENT.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": ai_prompt}])
                        ans = resp.choices[0].message.content
                        st.markdown(ans)
                        st.session_state.history.append({"role": "assistant", "content": ans})
                    except: st.error("AI 简报引擎暂时无法连接。")
                status.update(label="处理完毕", state="complete")
    else:
        st.warning("协议匹配失败。请包含关键词如：'手游大盘'、'豆瓣韩剧前10'、'2026年3月玩匠' 等。")
