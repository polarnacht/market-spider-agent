import streamlit as st
import pandas as pd
import subprocess
import os
import re
import uuid
import sys
from datetime import datetime
from openai import OpenAI

# ================= 1. 核心配置与全局样式 =================
API_KEY = st.secrets.get("api_key", "sk-cc6655649d204550bd5bcffd355ab4dd")
CLIENT = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

st.set_page_config(page_title="泛娱乐情报 Agent", layout="wide", page_icon="🌐")

st.markdown("""
    <style>
    .main { background-color: #F8FAFC; }
    .ds-card { background: white; border: 1px solid #E2E8F0; padding: 15px 20px; border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.02); height: 100%; }
    .ds-header { font-size: 1.05rem; font-weight: 700; color: #0F172A; border-bottom: 2px solid #3B82F6; padding-bottom: 6px; margin-bottom: 12px; display: inline-block;}
    .ds-title { font-weight: 600; color: #1E293B; margin-top: 10px; margin-bottom: 4px; font-size: 0.95rem; }
    .ds-row { font-size: 0.85rem; color: #475569; margin-bottom: 4px; display: flex; align-items: center; }
    .tag-blue { background: #EFF6FF; color: #2563EB; border: 1px solid #BFDBFE; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 8px; width: 40px; text-align: center; }
    .tag-red { background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 8px; width: 40px; text-align: center; }
    .guide-box { background: white; border: 1px solid #E2E8F0; padding: 15px 20px; border-radius: 8px; }
    code { color: #0369A1 !important; background: #F0F9FF !important; }
    </style>
    """, unsafe_allow_html=True)

# ================= 2. 状态初始化与顶栏 (无侧边栏) =================
if "history" not in st.session_state: st.session_state.history = []
if "trigger_prompt" not in st.session_state: st.session_state.trigger_prompt = None

def trigger_shortcut(cmd):
    st.session_state.trigger_prompt = cmd

col_t1, col_t2, col_t3 = st.columns([5, 2, 1])
with col_t1:
    st.title("🌐 泛娱乐市场情报 Agent")
with col_t3:
    st.write("") 
    if st.button("🧹 清空会话", use_container_width=True):
        st.session_state.history = []
        st.session_state.trigger_prompt = None
        st.rerun()

# ================= 3. 永久常驻面板 (绝不折叠) =================

# --- 模块 A: 指令规范 (一示例且可点击) ---
st.markdown("### 💡 核心指令构造指南")
g1, g2 = st.columns(2)
with g1:
    st.markdown("""
    <div class="guide-box">
        <b>🎯 单点深度提取</b> <span style="font-size:0.85rem; color:#64748B;">(用于精准获取某个榜单)</span><br>
        语法：<code>提取 [时间/分类] [数据源] [数量]</code>
    </div>
    """, unsafe_allow_html=True)
    st.button("👉 点击填入示例：提取 国内直播 10", on_click=trigger_shortcut, args=("提取 国内直播 10",), use_container_width=True)

with g2:
    st.markdown("""
    <div class="guide-box">
        <b>🌐 宏观大盘联动</b> <span style="font-size:0.85rem; color:#64748B;">(并发拉起多数据源，生成研报)</span><br>
        语法：<code>分析 [时间] [行业大类]</code>
    </div>
    """, unsafe_allow_html=True)
    st.button("👉 点击填入示例：分析 4月 手游大盘", on_click=trigger_shortcut, args=("分析 4月 手游大盘",), use_container_width=True)

st.markdown("---")

# --- 模块 B: 数据源明细 ---
st.markdown("### 🗂️ 数据源能力明细")
d1, d2, d3 = st.columns(3)

with d1:
    st.markdown("""
    <div class="ds-card">
        <div class="ds-header">📱 手游模块</div>
        <div class="ds-title">TapTap 预约榜</div>
        <div class="ds-row"><span class="tag-blue">参数</span> 提取数量 (前N名)</div>
        <div class="ds-row"><span class="tag-red">限制</span> 仅实时快照，无历史回溯</div>
        
        <div class="ds-title" style="margin-top: 18px;">玩匠(16P) 开测榜</div>
        <div class="ds-row"><span class="tag-blue">参数</span> 年份、月份、提取数量</div>
        <div class="ds-row"><span class="tag-red">限制</span> 详情页穿透慢，大盘限50条</div>
    </div>
    """, unsafe_allow_html=True)

with d2:
    st.markdown("""
    <div class="ds-card">
        <div class="ds-header">💻 PC & 直播模块</div>
        <div class="ds-title">Steam 愿望榜</div>
        <div class="ds-row"><span class="tag-blue">参数</span> 提取数量 (前N名)</div>
        <div class="ds-row"><span class="tag-red">限制</span> 实时接口，单次建议100内</div>
        
        <div class="ds-title" style="margin-top: 18px;">国内外直播榜</div>
        <div class="ds-row"><span class="tag-blue">参数</span> 国内(播酱) / 国外(Twitch)</div>
        <div class="ds-row"><span class="tag-red">限制</span> 国内按月统计，国外近30日</div>
    </div>
    """, unsafe_allow_html=True)

with d3:
    st.markdown("""
    <div class="ds-card">
        <div class="ds-header">🎬 影视 IP 模块</div>
        <div class="ds-title">豆瓣 影视榜</div>
        <div class="ds-row"><span class="tag-blue">参数</span> 国产 / 欧美 / 日剧 / 韩剧</div>
        <div class="ds-row"><span class="tag-red">限制</span> 极易触发WAF，强限20条内</div>
        
        <div class="ds-title" style="margin-top: 18px;">IMDb 趋势榜</div>
        <div class="ds-row"><span class="tag-blue">参数</span> 年份、月份、提取数量</div>
        <div class="ds-row"><span class="tag-red">限制</span> 受国际网络接口限流影响</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ================= 4. 核心执行引擎 =================
def run_spider(script, params):
    task_id = str(uuid.uuid4())[:8]
    out = f"res_{task_id}.csv"
    env = os.environ.copy()
    env.update(params)
    env["OUTPUT_FILE"] = out
    p = subprocess.Popen([sys.executable, "-u", os.path.abspath(script)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors='replace')
    bar = st.progress(0); msg = st.empty()
    while True:
        line = p.stdout.readline()
        if not line and p.poll() is not None: break
        if line:
            msg.caption(f"⚙️ 数据流 [{script}]: {line.strip()[:60]}...")
            prog = re.search(r"\[(\d+)/(\d+)\]", line)
            if prog: bar.progress(min(int(prog.group(1))/int(prog.group(2)), 1.0))
    return p.wait(), out

def parse_intent(prompt):
    p = prompt.lower()
    
    # 精准剥离时间，防止把月份当成提取数量
    dt = re.search(r'(\d{4})[年-]\s*(\d{1,2})', prompt)
    mo_only = re.search(r'(\d{1,2})月', prompt)
    now = datetime.now()
    year = dt.group(1) if dt else str(now.year)
    month = (dt.group(2) if dt else (mo_only.group(1) if mo_only else str(now.month))).zfill(2)

    # 提取纯净文本用于寻找数字限制 (去掉年份和月份)
    clean_p = re.sub(r'\d{4}[年-]', '', p)
    clean_p = re.sub(r'\d{1,2}月', '', clean_p)
    
    # 强力数字捕捉
    num_match = re.search(r'前\s*(\d+)|(\d+)\s*[名条个]|(?:^|\s)(\d{1,3})(?:\s|$)', clean_p)
    limit = None
    if num_match:
        limit = num_match.group(1) or num_match.group(2) or num_match.group(3)

    is_macro = any(k in p for k in ["所有", "整体", "大盘", "全局", "全行业", "简报", "联动"])
    
    l_hvy = limit if limit else ("20" if is_macro else "5")
    l_std = limit if limit else ("100" if is_macro else "10")

    tasks = []
    
    if is_macro or any(k in p for k in ["手游", "移动", "tap", "玩匠", "大盘"]):
        if is_macro or any(k in p for k in ["tap", "手游", "大盘"]): 
            tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": l_std}})
        if is_macro or any(k in p for k in ["玩匠", "测", "手游", "大盘"]): 
            tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": l_hvy, "YEAR": year, "MONTH": month}})
            
    if is_macro or any(k in p for k in ["pc", "端游", "steam", "直播", "热度", "twitch", "播酱"]):
        if is_macro or any(k in p for k in ["steam", "pc", "端游"]): 
            tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": l_std}})
        
        has_live = any(k in p for k in ["直播", "热度", "twitch", "播酱"])
        if is_macro or has_live:
            is_domestic = any(k in p for k in ["国内", "播酱", "大陆"])
            is_intl = any(k in p for k in ["国外", "海外", "twitch", "国际"])
            
            if is_domestic and not is_intl:
                tasks.append({"script": "domestic_live.py", "env": {"SCRAPE_LIMIT": l_std}})
            elif is_intl and not is_domestic:
                tasks.append({"script": "intl_live.py", "env": {"SCRAPE_LIMIT": l_std}})
            else:
                tasks.append({"script": "domestic_live.py", "env": {"SCRAPE_LIMIT": l_std}})
                tasks.append({"script": "intl_live.py", "env": {"SCRAPE_LIMIT": l_std}})

    if is_macro or any(k in p for k in ["影视", "电影", "剧", "豆瓣", "imdb"]):
        if is_macro or any(k in p for k in ["imdb", "影视"]): 
            tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": l_std, "YEAR": year, "MONTH": month}})
        if is_macro or any(k in p for k in ["豆瓣", "剧", "电影", "影视"]):
            tags = []
            if "欧美" in p: tags.append("欧美剧")
            if "韩" in p: tags.append("韩剧")
            if "日" in p: tags.append("日剧")
            if "国产" in p: tags.append("国产剧")
            if not tags: tags = ["欧美剧"] 
            for t in tags:
                tasks.append({"script": "douban.py", "env": {"SCRAPE_LIMIT": l_hvy, "DOUBAN_TAG": t}})
            
    return tasks

# ================= 5. 会话与数据展示流 =================
user_input = st.chat_input("在此处手敲指令，或点击上方示例按钮...")

active_prompt = None
if st.session_state.trigger_prompt:
    active_prompt = st.session_state.trigger_prompt
    st.session_state.trigger_prompt = None 
elif user_input:
    active_prompt = user_input

for chat in st.session_state.history:
    with st.chat_message(chat["role"]): st.markdown(chat["content"])

if active_prompt:
    st.session_state.history.append({"role": "user", "content": active_prompt})
    with st.chat_message("user"): st.markdown(active_prompt)

    tasks = parse_intent(active_prompt)
    if tasks:
        all_dfs = []
        fetched_results = []
        
        # 1. 仅将执行日志包裹在 status 中，跑完自动折叠
        with st.status(f"🚀 正在并发拉起 {len(tasks)} 个目标数据源...", expanded=True) as status:
            for task in tasks:
                st.write(f"📡 执行抓取：
