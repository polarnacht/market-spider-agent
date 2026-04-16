import streamlit as st
import pandas as pd
import subprocess
import os
import re
import uuid
import sys
from datetime import datetime
from openai import OpenAI

# ================= 1. 核心配置与样式重构 =================
API_KEY = st.secrets.get("api_key", "sk-cc6655649d204550bd5bcffd355ab4dd")
CLIENT = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

st.set_page_config(page_title="Market Intelligence Agent", layout="wide", page_icon="🛡️")

# 极简主义 CSS
st.markdown("""
    <style>
    [data-testid="stHeader"] {background: rgba(0,0,0,0);}
    .reportview-container .main .block-container { padding-top: 2rem; }
    .stMetric { border: 1px solid #eee; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    code { color: #2563eb !important; font-weight: 600; }
    .source-card { border: 1px solid #e5e7eb; padding: 20px; border-radius: 12px; background: #fff; height: 100%; }
    .category-title { font-size: 1.1rem; font-weight: 700; color: #1f2937; margin-bottom: 15px; border-bottom: 2px solid #3b82f6; width: fit-content; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 侧边栏：监控与重置 ---
with st.sidebar:
    st.subheader("🛡️ 控制台")
    if st.button("🧹 重置系统状态"):
        st.session_state.history = []
        st.rerun()
    
    st.divider()
    st.caption("⚙️ 内核运行状态")
    st.markdown("● `隔离运行`   ● `textContent穿透` \n\n ● `跨模态分析`   ● `动态调度` ")
    st.divider()
    st.caption("📅 系统时间")
    st.info(f"{datetime.now().strftime('%Y年%m月%d日')}")

# --- 3. 产品手册：数据源规格表 (极简卡片化) ---
st.title("泛娱乐市场情报提取与分析 Agent")
st.markdown("针对游戏、直播与影视行业的自动化竞争情报决策系统。")

# 使用分栏卡片展示规格，移除冗余形容词
col_left, col_mid, col_right = st.columns(3)

with col_left:
    st.markdown('<div class="category-title">📱 移动游戏 (Mobile)</div>', unsafe_allow_html=True)
    df_m = pd.DataFrame({
        "数据源": ["TapTap", "玩匠"],
        "核心指标": ["累计预约/关注", "测试节点/预约"],
        "调度限制": ["实时快照", "按月回溯"]
    })
    st.table(df_m)

with col_mid:
    st.markdown('<div class="category-title">💻 PC & 直播 (Dynamic)</div>', unsafe_allow_html=True)
    df_p = pd.DataFrame({
        "数据源": ["Steam", "国内外直播"],
        "核心指标": ["愿望单增量", "观众/主播/弹幕"],
        "调度限制": ["实时API", "国内月度/国外30日"]
    })
    st.table(df_p)

with col_right:
    st.markdown('<div class="category-title">🎬 影视 IP (Content)</div>', unsafe_allow_html=True)
    df_f = pd.DataFrame({
        "数据源": ["豆瓣", "IMDb"],
        "核心指标": ["评分/简介/人数", "全球趋势/年份"],
        "调度限制": ["限20条(WAF盾)", "按月回溯"]
    })
    st.table(df_f)

# --- 4. 指令协议解析 (公式化说明) ---
with st.container():
    st.markdown("### 💡 指令构造协议")
    st.markdown("系统采用**自然语言路由**，请遵循以下公式以获得最佳提取效果：")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**1. 单点提取 (Precision)**")
        st.code("提取 [数据源] [数量]")
        st.caption("例：提取豆瓣欧美剧前10名")
    with c2:
        st.markdown("**2. 模块联动 (Intelligence)**")
        st.code("分析 [模块/时间] 整体大盘")
        st.caption("例：分析2026年3月手游市场")
    with c3:
        st.markdown("**3. 全局分析 (Strategy)**")
        st.code("生成 [时间] 泛娱乐简报")
        st.caption("例：生成4月全行业分析报告")

st.markdown("---")

# ================= 5. 执行内核 (保持高性能逻辑) =================

def run_spider_with_progress(script_name, params):
    task_id = str(uuid.uuid4())[:8]
    output_csv = f"result_{task_id}.csv"
    env = os.environ.copy()
    env.update(params)
    env["OUTPUT_FILE"] = output_csv

    process = subprocess.Popen(
        [sys.executable, "-u", os.path.abspath(script_name)], 
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
        text=True, encoding="utf-8", errors='replace'
    )

    progress_bar = st.progress(0)
    log_area = st.empty()

    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None: break
        if line:
            clean_line = line.strip()
            log_area.caption(f"Log: {clean_line[:80]}...")
            prog = re.search(r"\[(\d+)/(\d+)\]", clean_line)
            if prog:
                progress_bar.progress(min(int(prog.group(1)) / int(prog.group(2)), 1.0))

    return process.wait(), output_csv

def parse_intent(prompt):
    p = prompt.lower()
    # 提取数字
    num_match = re.search(r'(\d+)名|前\s*(\d+)|(\d+)条', prompt)
    explicit_num = num_match.group(1) or num_match.group(2) or num_match.group(3) if num_match else None
    
    # 提取日期
    date_match = re.search(r'(\d{4})[年-]\s*(\d{1,2})', prompt)
    month_match = re.search(r'(\d{1,2})月', prompt)
    now = datetime.now()
    year = date_match.group(1) if date_match else str(now.year)
    month = (date_match.group(2) if date_match else (month_match.group(1) if month_match else str(now.month))).zfill(2)

    macro = any(kw in p for kw in ["所有", "整体", "大盘", "全局", "全行业", "报告", "简报"])
    
    limit_std = explicit_num if explicit_num else ("200" if macro else "5")
    limit_heavy = explicit_num if explicit_num else ("20" if macro else "5")

    tasks = []
    # 手机路由
    if any(k in p for k in ["手游", "taptap", "玩匠", "测试"]):
        if macro or "tap" in p: tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": limit_std}})
        if macro or "玩匠" in p or "测" in p: tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": limit_heavy, "YEAR": year, "MONTH": month}})
    
    # PC/直播路由
    if any(k in p for k in ["pc", "steam", "直播", "twitch"]):
        if macro or "steam" in p: tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": limit_std}})
        if macro or "直播" in p: 
            tasks.append({"script": "domestic_live.py", "env": {"SCRAPE_LIMIT": limit_std}})
            tasks.append({"script": "intl_live.py", "env": {"SCRAPE_LIMIT": limit_std}})

    # 影视路由
    if any(k in p for k in ["影视", "豆瓣", "imdb", "泛娱乐"]):
        if macro or "imdb" in p: tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": limit_std, "YEAR": year, "MONTH": month}})
        if macro or "豆瓣" in p or "剧" in p:
            tag = "欧美剧" if "欧美" in p else "韩剧" if "韩" in p else "日剧" if "日" in p else "国产剧"
            tasks.append({"script": "douban.py", "env": {"SCRAPE_LIMIT": limit_heavy, "DOUBAN_TAG": tag}})
            
    return tasks

# --- 6. 对话流与展示 ---
if "history" not in st.session_state: st.session_state.history = []

for chat in st.session_state.history:
    with st.chat_message(chat["role"]): st.markdown(chat["content"])

if prompt := st.chat_input("请下达情报提取指令..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    tasks = parse_intent(prompt)
    if tasks:
        all_dfs = []
        with st.status(f"正在并行调度 {len(tasks)} 个采集任务...", expanded=True) as status:
            for task in tasks:
                st.write(f"📡 唤醒内核: `{task['script']}`")
                code, res_csv = run_spider_with_progress(task["script"], task["env"])
                if code == 0 and os.path.exists(res_csv):
                    df = pd.read_csv(res_csv)
                    st.success(f"完成: {task['script']} ({len(df)}条)")
                    st.dataframe(df, hide_index=True)
                    all_dfs.append(f"### {task['script']} 数据\n" + df.to_markdown(index=False))
                    os.remove(res_csv)
            
            if all_dfs:
                status.update(label="正在生成战略简报...", state="running")
                prompt_ai = f"你是一位资深商业分析师。请基于以下实时数据表，提炼核心结论、热度断层标的及跨端转化启示：\n\n" + "\n\n".join(all_dfs)
                with st.chat_message("assistant"):
                    try:
                        resp = CLIENT.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt_ai}])
                        msg = resp.choices[0].message.content
                        st.markdown(msg)
                        st.session_state.history.append({"role": "assistant", "content": msg})
                    except: st.error("AI 简报生成超时。")
                status.update(label="指令处理完成", state="complete")
    else:
        st.warning("协议匹配失败。请确保指令包含：'手游大盘'、'豆瓣欧美前5' 等关键字。")
