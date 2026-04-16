import streamlit as st
import pandas as pd
import subprocess
import os
import re
import uuid
import sys
from datetime import datetime
from openai import OpenAI

# ================= 1. 核心配置与视觉样式 =================
API_KEY = st.secrets.get("api_key", "sk-cc6655649d204550bd5bcffd355ab4dd")
CLIENT = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

st.set_page_config(page_title="泛娱乐数据 Agent", layout="wide", page_icon="🌐")

# 注入自定义 CSS，强化卡片质感与层级
st.markdown("""
    <style>
    .main { background-color: #F8FAFC; }
    .source-card { background: white; border: 1px solid #E2E8F0; padding: 16px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.02); height: 100%; }
    .source-card h4 { color: #1E293B; margin-top: 0; font-size: 1.05rem; border-bottom: 2px solid #3B82F6; padding-bottom: 5px; display: inline-block; }
    .tag-blue { background: #DBEAFE; color: #1E40AF; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 5px;}
    .tag-red { background: #FEE2E2; color: #991B1B; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 5px;}
    /* 弱化状态文字 */
    .status-text { color: #64748B; font-size: 0.85rem; }
    </style>
    """, unsafe_allow_html=True)

# ================= 2. 左侧侧边栏 (任务工作台) =================
with st.sidebar:
    st.image("https://api.dicebear.com/7.x/shapes/svg?seed=agent&backgroundColor=3b82f6", width=50)
    st.markdown("### ⚙️ 分析控制台")
    
    st.markdown("#### 🎯 AI 洞察视角")
    analysis_mode = st.selectbox(
        "选择报告侧重点",
        ["📈 大盘趋势与核心结论", "🔥 爆款基因与特征挖掘", "⚔️ 赛道竞品数据对比", "🌐 跨端影游联动分析"],
        label_visibility="collapsed"
    )
    
    st.divider()
    st.markdown("#### 📡 探针健康度")
    st.caption("🟢 手游模块: TapTap | 玩匠")
    st.caption("🟢 PC直播: Steam | Twitch | 播酱")
    st.caption("🟢 影视模块: 豆瓣 | IMDb")
    
    st.divider()
    if st.button("🧹 清空看板并返回首页", use_container_width=True):
        st.session_state.history = []
        st.rerun()
    st.caption(f"🕘 系统时间：{datetime.now().strftime('%Y-%m-%d')}")

# ================= 3. 顶部：全局导航与说明书 =================
st.title("🌐 泛娱乐大盘情报 Agent")

# 始终悬浮的数据源说明书（折叠状态）
with st.expander("📖 **数据源图谱 & Prompt 指南 (点击展开)**", expanded=False):
    st.markdown("### 💡 如何下达指令？")
    st.info("**标准公式**：`[动作]` + `[时间/分类]` + `[数据源]` + `[提取数量]`\n\n"
            "👉 **单点提取**：`提取 豆瓣韩剧 前20名` *(系统将启动详情页穿透)*\n"
            "👉 **大盘联动**：`分析 4月 泛娱乐全行业` *(不带数字时，系统自动执行大盘默认上限 20~200条)*")
    
    st.markdown("### 🗂️ 挂载数据源能力明细")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class="source-card">
            <h4>📱 手游数据</h4>
            <p><b>TapTap 预约榜</b><br>
            <span class="tag-blue">属性</span>累计预约量、厂商、标签<br>
            <span class="tag-red">限制</span>仅实时快照，无历史回溯</p>
            <p><b>玩匠(16P) 开测榜</b><br>
            <span class="tag-blue">属性</span>测试节点、最高关联预约<br>
            <span class="tag-blue">参数</span>支持指定年份、月份</p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="source-card">
            <h4>💻 PC & 直播</h4>
            <p><b>Steam 愿望榜</b><br>
            <span class="tag-blue">属性</span>近期热度增量动能<br>
            <span class="tag-red">限制</span>实时接口限制前100名</p>
            <p><b>国内外直播活跃榜</b><br>
            <span class="tag-blue">属性</span>活跃观众、主播、弹幕量<br>
            <span class="tag-blue">参数</span>国内(播酱) / 国外(Twitch)</p>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="source-card">
            <h4>🎬 影视 IP</h4>
            <p><b>豆瓣 影视榜</b><br>
            <span class="tag-blue">属性</span>评分、评价人数、简介<br>
            <span class="tag-blue">参数</span>支持 国产/欧美/日/韩<br>
            <span class="tag-red">高危</span>极易触发WAF，限20条内</p>
            <p><b>IMDb 趋势榜</b><br>
            <span class="tag-blue">属性</span>全球流行度、制作年份<br>
            <span class="tag-blue">参数</span>支持指定历史年月回溯</p>
        </div>
        """, unsafe_allow_html=True)

# 状态管理：快捷指令触发器
if "trigger_prompt" not in st.session_state:
    st.session_state.trigger_prompt = None

def set_prompt(val):
    st.session_state.trigger_prompt = val

# ================= 4. 智能欢迎面板 (仅无历史对话时显示) =================
if len(st.session_state.get("history", [])) == 0:
    st.write("")
    st.markdown("### ✨ 请选择快捷分析模板，或在下方直接输入指令")
    
    tab_m, tab_p, tab_f, tab_all = st.tabs(["📱 手游深挖", "💻 PC与直播热度", "🎬 影视口碑追踪", "🌐 全局行业联动"])
    
    with tab_m:
        col1, col2 = st.columns(2)
        col1.button("📊 提取当月玩匠开测前 20 名", on_click=set_prompt, args=("提取本月玩匠开测榜前20名，分析短线布局",), use_container_width=True)
        col2.button("📈 提取 TapTap 实时预约前 50 名", on_click=set_prompt, args=("提取 TapTap 预约榜前50名，分析中长线潜力",), use_container_width=True)
    
    with tab_p:
        col1, col2 = st.columns(2)
        col1.button("🎮 提取 Steam 愿望榜前 50 名", on_click=set_prompt, args=("提取 Steam 愿望榜前50名数据",), use_container_width=True)
        col2.button("📡 对比国内外直播热度大盘", on_click=set_prompt, args=("对比 国内直播 与 国外直播 的整体热度数据",), use_container_width=True)

    with tab_f:
        col1, col2 = st.columns(2)
        col1.button("📺 获取 豆瓣欧美剧 高分TOP10", on_click=set_prompt, args=("提取豆瓣欧美剧前10名，进行口碑分析",), use_container_width=True)
        col2.button("🌍 分析 IMDb 当月全球热门趋势", on_click=set_prompt, args=("提取本月 IMDb 趋势榜数据，分析全球热点",), use_container_width=True)
        
    with tab_all:
        st.button("🚀 一键生成本月【泛娱乐全行业】商业简报 (并发7大数据源)", type="primary", on_click=set_prompt, args=("生成本月泛娱乐全行业大盘分析简报",), use_container_width=True)

st.markdown("---")

# ================= 5. 执行内核与解析引擎 =================
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
            msg.markdown(f'<span class="status-text">📡 引擎网络 [{script}]: {line.strip()[:60]}...</span>', unsafe_allow_html=True)
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
    l_std = limit if limit else ("200" if is_macro else "5")

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
            if not tags: tags = ["欧美剧"] # 缺省
            for t in tags:
                tasks.append({"script": "douban.py", "env": {"SCRAPE_LIMIT": l_hvy, "DOUBAN_TAG": t}})
            
    return tasks

# ================= 6. 对话渲染与主控流 =================
for chat in st.session_state.history:
    with st.chat_message(chat["role"]): st.markdown(chat["content"])

user_input = st.chat_input("或在此手动输入指令 (例：提取 4月玩匠 前20名)...")
active_prompt = st.session_state.trigger_prompt or user_input

if active_prompt:
    st.session_state.trigger_prompt = None # 消费触发器
    st.session_state.history.append({"role": "user", "content": active_prompt})
    
    # 触发后重新渲染一次，以隐藏 Welcome Dashboard
    if len(st.session_state.history) == 1:
        st.rerun()
        
    with st.chat_message("user"): st.markdown(active_prompt)

    tasks = parse_intent(active_prompt)
    if tasks:
        all_dfs = []
        with st.status(f"⏳ 正在执行 Agent 调度网络 (命中 {len(tasks)} 个模块)...", expanded=True) as status:
            for task in tasks:
                st.write(f"📡 请求并穿透数据源：`{task['script']}`")
                code, res_csv = run_spider(task["script"], task["env"])
                if code == 0 and os.path.exists(res_csv):
                    df = pd.read_csv(res_csv)
                    st.success(f"✅ {task['script']} 抓取与清洗完毕 (共 {len(df)} 条)")
                    
                    with st.expander(f"📦 查看 {task['script']} 结构化数据 (点击展开)"):
                        st.dataframe(df, hide_index=True, use_container_width=True)
                        
                    all_dfs.append(f"### {task['script']} 结构化快照\n" + df.to_markdown(index=False))
                    os.remove(res_csv)
                else:
                    st.error(f"❌ {task['script']} 节点请求异常")

            if all_dfs:
                status.update(label=f"数据源拉取完毕。正在基于【{analysis_mode}】视角进行归纳...", state="running")
                
                ai_prompt = f"""
                你是一位具备全局视野的商业情报专家。当前用户的核心分析诉求为：【{analysis_mode}】。
                请基于底层 Agent 刚刚抓取的结构化数据，撰写高管级简报。
                
                底层数据源快照：
                {"\n\n".join(all_dfs)}
                
                输出排版要求（务必严格遵循）：
                1. 🎯 **核心摘要**：一句话说明本次抓取覆盖的范围，并给出最重要的一条定性结论（加粗显示）。
                2. 📊 **数据洞察**：以无序列表形式，列出支撑结论的关键数据事实。必须包含表中的具体数值或排名对比（关键数字需加粗）。
                3. 💡 **战略启示**：基于当前分析视角，给出一条直接指向业务落地的商业建议。
                """
                with st.chat_message("assistant"):
                    try:
                        resp = CLIENT.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": ai_prompt}])
                        ans = resp.choices[0].message.content
                        st.markdown(ans)
                        st.session_state.history.append({"role": "assistant", "content": ans})
                    except:
                        st.error("AI 分析服务响应超时，请直接展开上方的数据卡片进行查看。")
                status.update(label="✅ 分析报告生成完毕", state="complete")
    else:
        st.warning("⚠️ 无法解析指令意图。请确保包含：玩匠、豆瓣、直播、手游 等有效识别关键字。")
