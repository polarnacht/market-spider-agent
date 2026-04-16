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
    /* 卡片与排版 */
    .dashboard-card { background: white; border: 1px solid #E2E8F0; padding: 20px; border-radius: 8px; height: 100%; box-shadow: 0 1px 2px rgba(0,0,0,0.02); }
    .card-title { font-size: 1.05rem; font-weight: 700; color: #0F172A; margin-bottom: 15px; border-bottom: 2px solid #3B82F6; padding-bottom: 6px; display: inline-block;}
    .item-title { font-weight: 600; color: #334155; margin-top: 10px; margin-bottom: 4px; font-size: 0.95rem; }
    .item-row { font-size: 0.85rem; color: #475569; margin-bottom: 3px; display: flex; align-items: center; }
    /* 精简标签 */
    .tag-blue { background: #EFF6FF; color: #2563EB; border: 1px solid #BFDBFE; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 8px; width: 40px; text-align: center; }
    .tag-red { background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 8px; width: 40px; text-align: center; }
    .tag-green { background: #F0FDF4; color: #16A34A; border: 1px solid #BBF7D0; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 8px; width: 40px; text-align: center; }
    /* 快捷按钮 */
    .stButton>button { border-radius: 6px; }
    /* 提示词框 */
    .prompt-box { background: white; border: 1px solid #E2E8F0; padding: 15px; border-radius: 8px; font-size: 0.9rem;}
    code { color: #0369A1 !important; background: #F0F9FF !important; }
    </style>
    """, unsafe_allow_html=True)

# ================= 2. 状态初始化与全局按键 =================
if "history" not in st.session_state: st.session_state.history = []
if "trigger_prompt" not in st.session_state: st.session_state.trigger_prompt = None

def set_prompt(val): st.session_state.trigger_prompt = val

# 顶部 Title 与 重置按钮
col_t1, col_t2 = st.columns([5, 1])
with col_t1:
    st.title("🌐 泛娱乐市场情报 Agent")
with col_t2:
    st.write("") # 占位对齐
    if st.button("🧹 清空当前会话", use_container_width=True):
        st.session_state.history = []
        st.rerun()

# ================= 3. 欢迎面板 (有对话后自动隐藏) =================
if len(st.session_state.history) == 0:
    st.write("")
    
    # --- 模块 A: 指令规范 ---
    st.markdown("### 💡 指令输入规范")
    cp1, cp2 = st.columns(2)
    with cp1:
        st.markdown("""
        <div class="prompt-box">
            <b>🎯 单点深度抓取</b> <span style="color:#64748B;">(用于精确提取品类榜单)</span><br>
            语法：<code>提取 [时间/分类] [数据源] 前[N]名</code><br>
            示例：提取 豆瓣韩剧 前20名
        </div>
        """, unsafe_allow_html=True)
    with cp2:
        st.markdown("""
        <div class="prompt-box">
            <b>🌐 宏观大盘联动</b> <span style="color:#64748B;">(跨模块并发抓取，生成研报)</span><br>
            语法：<code>分析 [时间] [行业大类]</code><br>
            示例：生成 4月 泛娱乐全行业简报
        </div>
        """, unsafe_allow_html=True)
        
    st.write("")

    # --- 模块 B: 数据源明细 (去除了冗余属性，仅保留参数与时效) ---
    st.markdown("### 🗂️ 挂载数据源明细")
    cd1, cd2, cd3 = st.columns(3)
    with cd1:
        st.markdown("""
        <div class="dashboard-card">
            <div class="card-title">📱 手游模块</div>
            <div class="item-title">TapTap 预约榜</div>
            <div class="item-row"><span class="tag-red">限制</span> 仅实时快照，无历史回溯</div>
            
            <div class="item-title" style="margin-top: 15px;">玩匠(16P) 开测榜</div>
            <div class="item-row"><span class="tag-blue">参数</span> 指定年份、月份</div>
            <div class="item-row"><span class="tag-green">支持</span> 历史大盘数据回溯</div>
        </div>
        """, unsafe_allow_html=True)
    with cd2:
        st.markdown("""
        <div class="dashboard-card">
            <div class="card-title">💻 PC & 直播模块</div>
            <div class="item-title">Steam 愿望榜</div>
            <div class="item-row"><span class="tag-red">限制</span> 实时接口，无历史回溯</div>
            
            <div class="item-title" style="margin-top: 15px;">国内外直播活跃榜</div>
            <div class="item-row"><span class="tag-blue">参数</span> 国内(播酱) / 国外(Twitch)</div>
            <div class="item-row"><span class="tag-red">限制</span> 国内按月统计，国外近30日</div>
        </div>
        """, unsafe_allow_html=True)
    with cd3:
        st.markdown("""
        <div class="dashboard-card">
            <div class="card-title">🎬 影视 IP 模块</div>
            <div class="item-title">豆瓣 影视榜</div>
            <div class="item-row"><span class="tag-blue">参数</span> 国产 / 欧美 / 日剧 / 韩剧</div>
            <div class="item-row"><span class="tag-red">高危</span> 极易触发WAF，强限20条内</div>
            
            <div class="item-title" style="margin-top: 15px;">IMDb 趋势榜</div>
            <div class="item-row"><span class="tag-blue">参数</span> 指定年份、月份</div>
            <div class="item-row"><span class="tag-green">支持</span> 历史流行度回溯</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    # --- 模块 C: 快捷分析模板 ---
    st.caption("✨ **快捷分析模板 (点击直接运行)**")
    cb1, cb2, cb3, cb4 = st.columns(4)
    cb1.button("📊 提取 TapTap 预约榜 前 50名", on_click=set_prompt, args=("提取 TapTap预约榜 前50名",), use_container_width=True)
    cb2.button("🎬 提取 豆瓣欧美剧 前 10名", on_click=set_prompt, args=("提取 豆瓣欧美剧前 10 名",), use_container_width=True)
    cb3.button("🎮 分析 PC与直播 跨端大盘", on_click=set_prompt, args=("分析 Steam 与 国内外直播榜单的大盘情况",), use_container_width=True)
    cb4.button("🌐 生成 泛娱乐全行业 简报", on_click=set_prompt, args=("生成本月泛娱乐全行业综合分析简报",), use_container_width=True)

st.markdown("---")

# ================= 4. 执行内核与路由 =================
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
            msg.caption(f"⚙️ 运行日志 [{script}]: {line.strip()[:60]}...")
            prog = re.search(r"\[(\d+)/(\d+)\]", line)
            if prog: bar.progress(min(int(prog.group(1))/int(prog.group(2)), 1.0))
    return p.wait(), out

def parse_intent(prompt):
    p = prompt.lower()
    num = re.search(r'(\d+)名|前\s*(\d+)|(\d+)条', prompt)
    limit = num.group(1) or num.group(2) or num.group(3) if num else None
    
    dt = re.search(r'(\d{4})[年-]\s*(\d{1,2})', prompt)
    mo_only = re.search(r'(\d{1,2})月', prompt)
    now = datetime.now()
    year = dt.group(1) if dt else str(now.year)
    month = (dt.group(2) if dt else (mo_only.group(1) if mo_only else str(now.month))).zfill(2)

    is_macro = any(k in p for k in ["所有", "整体", "大盘", "全局", "全行业", "简报", "联动"])
    
    # 智能水位分配
    l_hvy = limit if limit else ("20" if is_macro else "5")
    l_std = limit if limit else ("100" if is_macro else "10")

    tasks = []
    
    if any(k in p for k in ["手游", "tap", "玩匠", "测试", "大盘"]):
        if is_macro or "tap" in p or "大盘" in p: tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": l_std}})
        if is_macro or "玩匠" in p or "测" in p or "大盘" in p: tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": l_hvy, "YEAR": year, "MONTH": month}})
        
    if any(k in p for k in ["pc", "steam", "直播", "热度", "twitch"]):
        if is_macro or "steam" in p: tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": l_std}})
        if is_macro or "直播" in p or "热度" in p: 
            tasks.append({"script": "domestic_live.py", "env": {"SCRAPE_LIMIT": l_std}})
            tasks.append({"script": "intl_live.py", "env": {"SCRAPE_LIMIT": l_std}})

    if any(k in p for k in ["影视", "豆瓣", "imdb", "剧", "全行业", "泛娱乐"]):
        if is_macro or "imdb" in p: tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": l_std, "YEAR": year, "MONTH": month}})
        if is_macro or "豆瓣" in p or "剧" in p:
            tags = []
            if "欧美" in p: tags.append("欧美剧")
            if "韩" in p: tags.append("韩剧")
            if "日" in p: tags.append("日剧")
            if "国产" in p: tags.append("国产剧")
            if not tags: tags = ["欧美剧"] 
            for t in tags:
                tasks.append({"script": "douban.py", "env": {"SCRAPE_LIMIT": l_hvy, "DOUBAN_TAG": t}})
            
    return tasks

# ================= 5. 会话与流式输出 =================
for chat in st.session_state.history:
    with st.chat_message(chat["role"]): st.markdown(chat["content"])

user_input = st.chat_input("请输入指令 (例：生成 4月 泛娱乐全行业简报)...")
active_prompt = st.session_state.trigger_prompt or user_input

if active_prompt:
    st.session_state.trigger_prompt = None 
    st.session_state.history.append({"role": "user", "content": active_prompt})
    
    # 点击后刷新，隐藏欢迎面板
    if len(st.session_state.history) == 1: st.rerun()
    
    with st.chat_message("user"): st.markdown(active_prompt)

    tasks = parse_intent(active_prompt)
    if tasks:
        all_dfs = []
        with st.status(f"🚀 系统已受理指令，正在并发调度 {len(tasks)} 个目标数据源...", expanded=True) as status:
            for task in tasks:
                st.write(f"📡 穿透请求网络：`{task['script']}`")
                code, res_csv = run_spider(task["script"], task["env"])
                if code == 0 and os.path.exists(res_csv):
                    df = pd.read_csv(res_csv)
                    st.success(f"✅ {task['script']} 抓取清洗完毕 (共 {len(df)} 条)")
                    
                    with st.expander(f"📦 查看 {task['script']} 数据表格"):
                        st.dataframe(df, hide_index=True, use_container_width=True)
                        
                    all_dfs.append(f"### 数据源: {task['script']}\n" + df.to_markdown(index=False))
                    os.remove(res_csv)
                else:
                    st.error(f"❌ {task['script']} 抓取失败")

            if all_dfs:
                status.update(label=f"数据抓取完毕。正在请求 AI 生成商业简报...", state="running")
                
                # 固化的结构化报告要求
                ai_prompt = f"""
                你是一位具备全局视野的商业分析师。请基于以下采集的实时数据，撰写结构化简报。
                
                底层数据：
                {"\n\n".join(all_dfs)}
                
                排版要求（务必严格遵循）：
                1. 🎯 **核心结论**：一句话概括本次抓取结论（加粗）。
                2. 📊 **数据拆解**：无序列表列出 2-3 个支撑结论的数据事实，必须带具体数值/排名（数字加粗）。
                3. 💡 **商业建议**：给出一个具体的业务建议。
                """
                with st.chat_message("assistant"):
                    try:
                        resp = CLIENT.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": ai_prompt}])
                        ans = resp.choices[0].message.content
                        st.markdown(ans)
                        st.session_state.history.append({"role": "assistant", "content": ans})
                    except:
                        st.error("AI 分析超时，请查看上方的原始表格数据。")
                status.update(label="全部执行完毕", state="complete")
    else:
        st.warning("⚠️ 无法识别路由，请检查指令是否包含：玩匠、豆瓣、直播、手游 等关键字。")
