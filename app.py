import streamlit as st
import pandas as pd
import subprocess
import os
import re
import uuid
import sys
from datetime import datetime
from openai import OpenAI

# ================= 1. 初始化配置 =================
API_KEY = st.secrets.get("api_key", "sk-cc6655649d204550bd5bcffd355ab4dd")
CLIENT = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

st.set_page_config(page_title="大文娱情报 Agent", layout="wide", page_icon="🛡️")

# 注入自定义样式，提升专业感
st.markdown("""
    <style>
    .source-header { font-size: 1.2rem; font-weight: 700; color: #1e293b; margin-bottom: 10px; }
    .tag-blue { background: #dbeafe; color: #1e40af; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
    .tag-red { background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
    .command-box { background: #f8fafc; border-left: 5px solid #3b82f6; padding: 15px; margin: 10px 0; font-family: monospace; }
    </style>
    """, unsafe_allow_html=True)

# ================= 2. 侧边栏：系统看板 =================
with st.sidebar:
    st.title("🛡️ 调度控制中心")
    if st.button("🧹 重置所有状态"):
        st.session_state.history = []
        st.rerun()
    st.divider()
    st.subheader("⚙️ 核心引擎能力")
    st.caption("● 实时穿透：基于 textContent 穿透 Vue/React 异步渲染")
    st.caption("● 智能限流：根据站点 WAF 动态调整单点采集水位")
    st.caption("● 时间感知：支持指定年份、月份的跨月回溯采集")
    st.divider()
    st.info(f"📅 当前系统时间：{datetime.now().strftime('%Y-%m-%d')}")

# ================= 3. 数据能力地图 (解决“不知道有什么”问题) =================
st.title("泛娱乐市场情报提取与分析 Agent")
st.markdown("本系统通过自动化采集引擎，为您提供游戏、直播、影视行业的深度商业情报。")

# 采用标签页形式，详细展开各源能力
tab1, tab2, tab3 = st.tabs(["📱 手游大盘 (Mobile)", "💻 PC & 直播 (Digital)", "🎬 影视 IP (Content)"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="source-header">TapTap 预约热度榜</p>', unsafe_allow_html=True)
        st.markdown("""
        - **获取信息**：当前全网人气排名、厂商名称、游戏标签、**全平台累计预约/关注量**、详情简介。
        - **控制参数**：`SCRAPE_LIMIT` (抓取前N名)。
        - **<span class="tag-blue">优势</span>**：数据最实时，反映中长线产品潜力。
        - **<span class="tag-red">限制</span>**：仅支持“当前”热度，不支持查询历史某月的排名。
        """, unsafe_allow_html=True)
    with col2:
        st.markdown('<p class="source-header">玩匠(16P) 开测榜</p>', unsafe_allow_html=True)
        st.markdown("""
        - **获取信息**：测试日期、厂商、测试类型(删档/不删档)、**最高关联预约量**。
        - **控制参数**：`YEAR`, `MONTH` (指定年月), `LIMIT` (抓取名次)。
        - **<span class="tag-blue">优势</span>**：**支持抓取全月所有数据**，追踪厂商发号节点。
        - **<span class="tag-red">限制</span>**：由于需深度穿透详情页，50条以上数据采集耗时较久。
        """, unsafe_allow_html=True)

with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="source-header">Steam 全球愿望榜</p>', unsafe_allow_html=True)
        st.markdown("""
        - **获取信息**：排名、游戏名、发售日期、**近期(7日/30日)热度趋势**、所属厂商。
        - **控制参数**：`LIMIT` (抓取名次)。
        - **<span class="tag-blue">优势</span>**：洞察全球买断制游戏的真实期待度转化。
        - **<span class="tag-red">限制</span>**：受 Steam 国际接口波动影响，单次抓取不建议超过 100 条。
        """, unsafe_allow_html=True)
    with col2:
        st.markdown('<p class="source-header">直播活跃榜 (播酱/Twitch)</p>', unsafe_allow_html=True)
        st.markdown("""
        - **获取信息**：**活跃观众数、主播人数、弹幕总量、平均观看时长**、礼物总值。
        - **控制参数**：`LIMIT` (名次)；支持“国内/国外”路由分发。
        - **<span class="tag-blue">优势</span>**：反映游戏在内容社区的“长线生命力”。
        - **<span class="tag-red">限制</span>**：国内数据为月度统计，国外数据为近 30 日快照。
        """, unsafe_allow_html=True)

with tab3:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<p class="source-header">豆瓣影视深度榜</p>', unsafe_allow_html=True)
        st.markdown("""
        - **获取信息**：豆瓣评分、**评价人数(反映出圈度)**、年份、剧情简介、分类标签。
        - **控制参数**：`DOUBAN_TAG` (支持**国产/欧美/韩剧/日剧**自动切换)。
        - **<span class="tag-blue">优势</span>**：支持详情页穿透，获取完整的评论深度数据。
        - **<span class="tag-red">限制</span>**：**防爬虫极严**，单次采集建议限制在 **20 条** 以内，否则易封禁。
        """, unsafe_allow_html=True)
    with col2:
        st.markdown('<p class="source-header">IMDb 全球影视趋势</p>', unsafe_allow_html=True)
        st.markdown("""
        - **获取信息**：IMDb 评分、人气排名、制作年份、全球流行趋势分值。
        - **控制参数**：`YEAR`, `MONTH` (支持历史月份回溯)。
        - **<span class="tag-blue">优势</span>**：评估全球顶级影视 IP 的商业价值变化。
        """, unsafe_allow_html=True)

# ================= 4. 指令构造协议 (解决“不知道怎么问”问题) =================
st.markdown("### 💡 指令构造指南")
st.markdown("您可以像对分析师说话一样下达指令，但请包含以下核心要素以触发精准路由：")

c1, c2, c3 = st.columns(3)
with c1:
    st.info("**要素 1：动作 + 数据源**\n必须包含分类关键字，如：`玩匠`、`豆瓣欧美`、`直播`、`手游大盘`。")
with c2:
    st.info("**要素 2：时间参数 (选填)**\n涉及历史月份请明确，如：`2026年3月`、`4月份`。")
with c3:
    st.info("**要素 3：数量限制 (选填)**\n默认按大盘逻辑执行，支持指定：`前10名`、`50条`。")

with st.expander("📝 典型常用指令范例 (点击可直接参考)"):
    st.markdown("""
    - **【精准查某个品类】**：`提取 2026年3月 玩匠前 50名 数据`
    - **【影视行业深挖】**：`提取 豆瓣韩剧前 10 名，并进行口碑分析`
    - **【跨端大盘对比】**：`分析 4月 手游与直播市场的联动情况` (系统将自动拉起 玩匠+TapTap+直播)
    - **【全行业简报】**：`生成 2026年4月 泛娱乐全行业分析简报` (系统将并发调用七大引擎)
    """)

st.markdown("---")

# ================= 5. 任务调度逻辑 (逻辑保持严谨) =================

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
    status_msg = st.empty()

    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None: break
        if line:
            clean_line = line.strip()
            status_msg.caption(f"⚙️ {script_name} 状态: {clean_line[:80]}...")
            # 捕获进度日志
            prog = re.search(r"\[(\d+)/(\d+)\]", clean_line)
            if prog:
                progress_bar.progress(min(int(prog.group(1)) / int(prog.group(2)), 1.0))

    return process.wait(), output_csv

def parse_intent(prompt):
    p = prompt.lower()
    
    # 提取数字参数
    num_match = re.search(r'(\d+)名|前\s*(\d+)|(\d+)条', prompt)
    explicit_num = num_match.group(1) or num_match.group(2) or num_match.group(3) if num_match else None
    
    # 提取日期参数
    date_match = re.search(r'(\d{4})[年-]\s*(\d{1,2})', prompt)
    month_match = re.search(r'(\d{1,2})月', prompt)
    now = datetime.now()
    year = date_match.group(1) if date_match else str(now.year)
    month = (date_match.group(2) if date_match else (month_match.group(1) if month_match else str(now.month))).zfill(2)

    # 判定大盘模式
    macro = any(kw in p for kw in ["所有", "整体", "大盘", "全局", "全行业", "简报", "报告"])
    
    # 策略路由限流 (针对耗时模块限流)
    limit_heavy = explicit_num if explicit_num else ("20" if macro else "5")
    limit_std = explicit_num if explicit_num else ("100" if macro else "5")

    tasks = []
    
    # 路由 1：手游
    if any(k in p for k in ["手游", "移动", "tap", "玩匠", "测试"]):
        if macro or "tap" in p: tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": limit_std}})
        if macro or "玩匠" in p or "测" in p: tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": limit_heavy, "YEAR": year, "MONTH": month}})
    
    # 路由 2：PC & 直播
    if any(k in p for k in ["pc", "steam", "直播", "热度", "twitch"]):
        if macro or "steam" in p: tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": limit_std}})
        if macro or "直播" in p or "热度" in p: 
            tasks.append({"script": "domestic_live.py", "env": {"SCRAPE_LIMIT": limit_std}})
            tasks.append({"script": "intl_live.py", "env": {"SCRAPE_LIMIT": limit_std}})

    # 路由 3：影视
    if any(k in p for k in ["影视", "豆瓣", "imdb", "剧", "全行业", "泛娱乐"]):
        if macro or "imdb" in p: tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": limit_std, "YEAR": year, "MONTH": month}})
        if macro or "豆瓣" in p or "剧" in p:
            tag = "欧美剧" if "欧美" in p else "韩剧" if "韩" in p else "日剧" if "日" in p else "国产剧"
            tasks.append({"script": "douban.py", "env": {"SCRAPE_LIMIT": limit_heavy, "DOUBAN_TAG": tag}})
            
    return tasks

# ================= 6. 交互流展示 =================
if "history" not in st.session_state: st.session_state.history = []

for chat in st.session_state.history:
    with st.chat_message(chat["role"]): st.markdown(chat["content"])

if prompt := st.chat_input("在此输入您的情报提取指令..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    tasks = parse_intent(prompt)
    if tasks:
        all_results_md = []
        with st.status(f"🚀 正通过 {len(tasks)} 个并行模块提取实时情报...", expanded=True) as status:
            for task in tasks:
                st.write(f"正在拉取内核数据：`{task['script']}`")
                code, res_csv = run_spider_with_progress(task["script"], task["env"])
                if code == 0 and os.path.exists(res_csv):
                    df = pd.read_csv(res_csv)
                    st.success(f"完成采集：{task['script']} (成功获取 {len(df)} 条)")
                    st.dataframe(df, hide_index=True)
                    all_results_md.append(f"### 数据快照：{task['script']}\n" + df.to_markdown(index=False))
                    os.remove(res_csv)
            
            if all_results_md:
                status.update(label="数据流已汇入，AI 正在提炼商业结论...", state="running")
                final_ai_prompt = f"""你是一位具备全球视野的商业情报分析师。
                请基于以下多维实时采集的数据，为决策层提供简报。
                
                数据源内容：
                {"\n\n".join(all_results_md)}
                
                分析要求：
                1. 提取具有“热度断层”的标的（如预约数、直播观众远超同行的产品）。
                2. 针对跨模块数据（如：影视剧的口碑与同期游戏的测试计划）尝试发掘关联机会。
                3. 每条结论必须使用 **数字+百分比** 增强说服力。
                """
                with st.chat_message("assistant"):
                    try:
                        resp = CLIENT.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": final_ai_prompt}])
                        ans = resp.choices[0].message.content
                        st.markdown(ans)
                        st.session_state.history.append({"role": "assistant", "content": ans})
                    except:
                        st.error("AI 服务响应超时，请直接参考表格进行判断。")
                status.update(label="情报处理流程全部结束", state="complete")
    else:
        st.warning("⚠️ 指令无法识别路由。请确保包含关键字，如：'玩匠'、'手游大盘'、'豆瓣欧美前5' 等。")
