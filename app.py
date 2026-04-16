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

st.set_page_config(page_title="泛娱乐商业分析 Agent", layout="wide", page_icon="📊")

# 现代 SaaS 风格 CSS
st.markdown("""
    <style>
    .main { background-color: #F8FAFC; }
    /* 卡片悬浮效果 */
    .action-card { 
        background: white; border: 1px solid #E2E8F0; padding: 20px; 
        border-radius: 12px; transition: all 0.3s ease; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .action-card:hover { transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-color: #3B82F6; }
    .card-title { font-size: 1.1rem; font-weight: 700; color: #0F172A; margin-bottom: 8px; }
    .card-desc { font-size: 0.85rem; color: #64748B; margin-bottom: 15px; min-height: 40px; }
    /* 隐藏默认繁杂元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ================= 2. 侧边栏：分析控制台 =================
with st.sidebar:
    st.image("https://api.dicebear.com/7.x/shapes/svg?seed=agent&backgroundColor=0ea5e9", width=60)
    st.markdown("### 📊 分析控制台")
    
    # 核心升级：分析模式选择器
    st.markdown("#### 🎯 设定分析目标")
    analysis_mode = st.selectbox(
        "AI 洞察视角",
        ["📈 常规大盘概览 (默认)", "🔥 潜力爆款挖掘", "⚔️ 赛道竞品对比", "🌐 跨端影游联动分析"],
        help="切换此选项将改变 AI 最终输出报告的侧重点。"
    )
    
    st.divider()
    
    st.markdown("#### 📡 数据源监控")
    st.caption("🟢 TapTap 预约引擎    🟢 玩匠 开测节点")
    st.caption("🟢 Steam 愿望动能    🟢 Twitch 全球直播")
    st.caption("🟢 播酱 国内直播     🟢 豆瓣 影视口碑")
    st.caption("🟢 IMDb 国际热度")
    
    st.divider()
    if st.button("🧹 开启全新分析轮次", use_container_width=True):
        st.session_state.history = []
        st.rerun()

# ================= 3. 主界面：Hero Section 与 快捷入口 =================
st.title("泛娱乐大盘分析助手")
st.markdown("一键洞察 **游戏、直播、影视** 跨界市场趋势，为您自动生成结构化商业情报。")
st.write("")

# 快捷操作卡片（取代枯燥的说明书）
if "trigger_prompt" not in st.session_state:
    st.session_state.trigger_prompt = None

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown("""
    <div class="action-card">
        <div class="card-title">🔥 爆款基因挖掘</div>
        <div class="card-desc">提取豆瓣高分欧美剧与韩剧，分析当下爆款内容特征。</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("一键执行", key="btn1", use_container_width=True):
        st.session_state.trigger_prompt = "提取豆瓣欧美剧和韩剧前 10 名，分析高分爆款特征"

with c2:
    st.markdown("""
    <div class="action-card">
        <div class="card-title">🎮 游戏短线追踪</div>
        <div class="card-desc">抓取本月玩匠开测榜单，分析近期头部厂商的发号布局。</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("一键执行", key="btn2", use_container_width=True):
        st.session_state.trigger_prompt = f"抓取 {datetime.now().month}月 玩匠开测榜，分析厂商布局"

with c3:
    st.markdown("""
    <div class="action-card">
        <div class="card-title">📡 社区热度透视</div>
        <div class="card-desc">对比 Steam 愿望单与直播活跃数据，看穿真实热度。</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("一键执行", key="btn3", use_container_width=True):
        st.session_state.trigger_prompt = "分析 Steam 与 国内外直播榜单的整体联动情况"

with c4:
    st.markdown("""
    <div class="action-card">
        <div class="card-title">🌐 宏观大盘简报</div>
        <div class="card-desc">调动全量七大数据源，生成全行业跨界洞察报告。</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("一键执行", key="btn4", use_container_width=True):
        st.session_state.trigger_prompt = "生成本月泛娱乐全行业综合分析简报"

st.markdown("---")

# ================= 4. 核心调度引擎 =================

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
    status_box = st.empty()

    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None: break
        if line:
            clean_line = line.strip()
            status_box.caption(f"⏳ 采集节点 [{script_name}]: {clean_line[:60]}...")
            prog = re.search(r"\[(\d+)/(\d+)\]", clean_line)
            if prog:
                progress_bar.progress(min(int(prog.group(1)) / int(prog.group(2)), 1.0))

    return process.wait(), output_csv

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
    l_std = limit if limit else ("200" if is_macro else "5")

    tasks = []
    
    if any(k in p for k in ["手游", "tap", "玩匠", "测试", "布局"]):
        if is_macro or "tap" in p or "大盘" in p: tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": l_std}})
        if is_macro or "玩匠" in p or "测" in p or "布局" in p: tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": l_hvy, "YEAR": year, "MONTH": month}})
        
    if any(k in p for k in ["pc", "steam", "直播", "热度", "twitch"]):
        if is_macro or "steam" in p: tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": l_std}})
        if is_macro or "直播" in p or "热度" in p: 
            tasks.append({"script": "domestic_live.py", "env": {"SCRAPE_LIMIT": l_std}})
            tasks.append({"script": "intl_live.py", "env": {"SCRAPE_LIMIT": l_std}})

    if any(k in p for k in ["影视", "豆瓣", "imdb", "剧", "全行业", "爆款"]):
        if is_macro or "imdb" in p: tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": l_std, "YEAR": year, "MONTH": month}})
        if is_macro or "豆瓣" in p or "剧" in p or "爆款" in p:
            # 支持多标签智能识别
            tags = []
            if "欧美" in p: tags.append("欧美剧")
            if "韩" in p: tags.append("韩剧")
            if "日" in p: tags.append("日剧")
            if "国产" in p: tags.append("国产剧")
            if not tags: tags = ["欧美剧"] # 默认
            for t in tags:
                tasks.append({"script": "douban.py", "env": {"SCRAPE_LIMIT": l_hvy, "DOUBAN_TAG": t}})
            
    return tasks

# ================= 5. 会话渲染与执行 =================
if "history" not in st.session_state: st.session_state.history = []

for chat in st.session_state.history:
    with st.chat_message(chat["role"]): st.markdown(chat["content"])

# 接收输入框输入 或 快捷卡片触发
user_input = st.chat_input("或在此自由输入您的分析需求 (例如：提取豆瓣国产剧前20名)...")
active_prompt = st.session_state.trigger_prompt or user_input

if active_prompt:
    # 消费掉 trigger，防止循环触发
    st.session_state.trigger_prompt = None
    
    st.session_state.history.append({"role": "user", "content": active_prompt})
    with st.chat_message("user"): st.markdown(active_prompt)

    tasks = parse_intent(active_prompt)
    if tasks:
        all_dfs = []
        with st.status(f"🚀 系统已受理：正在调动 {len(tasks)} 个采集节点...", expanded=True) as status:
            for task in tasks:
                st.write(f"正在接入数据源：`{task['script']}`")
                code, res_csv = run_spider_with_progress(task["script"], task["env"])
                if code == 0 and os.path.exists(res_csv):
                    df = pd.read_csv(res_csv)
                    st.success(f"✅ {task['script']} 提取完成 ({len(df)} 条数据)")
                    
                    # 嵌套展示数据，提升信息层级
                    with st.expander(f"👁️ 查看 {task['script']} 原始数据快照"):
                        st.dataframe(df, hide_index=True, use_container_width=True)
                    
                    all_dfs.append(f"### 数据源: {task['script']}\n" + df.to_markdown(index=False))
                    os.remove(res_csv)
                else:
                    st.error(f"❌ {task['script']} 节点响应异常")

            if all_dfs:
                status.update(label=f"数据装载完毕。正在以【{analysis_mode}】视角生成研报...", state="running")
                
                # 动态 Prompt：根据左侧边栏的设定改变输出结构
                ai_prompt = f"""
                你是一位顶尖的商业分析师。当前设定的分析目标为：【{analysis_mode}】。
                请基于以下自动化采集的实时数据源，撰写一份结构化商业简报。
                
                原始数据：
                {"\n\n".join(all_dfs)}
                
                排版要求（必须严格遵守）：
                1. 🎯 **核心结论**：开篇直接给出最重要的一条定性结论（不超过50字）。
                2. 📊 **数据洞察**：以无序列表形式，列出支撑结论的 2-3 个关键数据事实。必须对比具体数字（加粗显示）。
                3. 💡 **商业启示**：基于当前设定的分析目标，给出一条明确的业务落地建议。
                """
                with st.chat_message("assistant"):
                    try:
                        resp = CLIENT.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": ai_prompt}])
                        ans = resp.choices[0].message.content
                        st.markdown(ans)
                        st.session_state.history.append({"role": "assistant", "content": ans})
                    except:
                        st.error("AI 引擎当前不可用，请参考上方原始数据进行人工判断。")
                status.update(label="分析任务圆满完成", state="complete")
    else:
        st.warning("⚠️ 指令未匹配到有效数据源，请尝试点击上方的快捷卡片。")
