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
    .item-title { font-weight: 600; color: #334155; margin-top: 10px; margin-bottom: 6px; font-size: 0.95rem; }
    .item-row { font-size: 0.85rem; color: #475569; margin-bottom: 4px; display: flex; align-items: flex-start; }
    /* 精简标签 */
    .tag-blue { background: #EFF6FF; color: #2563EB; border: 1px solid #BFDBFE; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 8px; width: 38px; text-align: center; flex-shrink: 0;}
    .tag-red { background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 8px; width: 38px; text-align: center; flex-shrink: 0;}
    /* 提示框与按钮 */
    .guide-box { background: white; border: 1px solid #E2E8F0; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between;}
    code { color: #0369A1 !important; background: #F0F9FF !important; font-size: 0.95rem;}
    .stButton>button { border-radius: 6px; }
    </style>
    """, unsafe_allow_html=True)

# ================= 2. 状态初始化与顶栏 =================
if "history" not in st.session_state: st.session_state.history = []
if "trigger_prompt" not in st.session_state: st.session_state.trigger_prompt = None

def set_prompt(val): st.session_state.trigger_prompt = val

# 顶部 Title 与 重置按钮 (取代侧边栏)
col_t1, col_t2 = st.columns([6, 1])
with col_t1:
    st.title("🌐 泛娱乐市场情报 Agent")
with col_t2:
    st.write("") 
    if st.button("🧹 清空当前会话", use_container_width=True):
        st.session_state.history = []
        st.session_state.trigger_prompt = None
        st.rerun()

# 获取用户输入
user_input = st.chat_input("请输入指令 (例：分析 4月 手游大盘)...")
active_prompt = st.session_state.trigger_prompt or user_input

# ================= 3. 欢迎面板 (首次无对话时展现) =================
if len(st.session_state.history) == 0 and not active_prompt:
    st.write("")
    
    # --- 模块 A: 指令指南 (唯一示例，可点击) ---
    st.markdown("### 💡 核心指令构造指南")
    g_col1, g_col2 = st.columns([3, 2])
    with g_col1:
        st.markdown("<div style='padding-top: 8px; font-size: 1rem; color: #1E293B;'><b>语法公式：</b> <code>[动作] + [时间/分类] + [数据源] + [数量]</code></div>", unsafe_allow_html=True)
    with g_col2:
        st.button("👉 示例提取：提取 4月玩匠开测榜 前50名", on_click=set_prompt, args=("提取 4月玩匠开测榜 前50名",), use_container_width=True)

    st.markdown("---") # 绝对的视觉隔离

    # --- 模块 B: 数据源明细 (3x3 工整排版，合并直播) ---
    st.markdown("### 🗂️ 挂载数据源明细")
    cd1, cd2, cd3 = st.columns(3)
    
    with cd1:
        st.markdown(
"""<div class="dashboard-card">
<div class="card-title">📱 手游模块</div>
<div class="item-title">TapTap 预约榜</div>
<div class="item-row"><span class="tag-blue">属性</span> 累计预约量、厂商、标签</div>
<div class="item-row"><span class="tag-blue">参数</span> 提取数量 (前N名)</div>
<div class="item-row"><span class="tag-red">限制</span> 仅实时快照，无历史回溯</div>

<div class="item-title" style="margin-top: 20px;">玩匠(16P) 开测榜</div>
<div class="item-row"><span class="tag-blue">属性</span> 测试节点、最高关联预约</div>
<div class="item-row"><span class="tag-blue">参数</span> 年份、月份、提取数量</div>
<div class="item-row"><span class="tag-red">限制</span> 详情页穿透较慢，大盘限50条</div>
</div>""", unsafe_allow_html=True)

    with cd2:
        st.markdown(
"""<div class="dashboard-card">
<div class="card-title">💻 PC & 直播模块</div>
<div class="item-title">Steam 愿望榜</div>
<div class="item-row"><span class="tag-blue">属性</span> 游戏名、近期热度增量</div>
<div class="item-row"><span class="tag-blue">参数</span> 提取数量 (前N名)</div>
<div class="item-row"><span class="tag-red">限制</span> 实时接口，单次建议100条内</div>

<div class="item-title" style="margin-top: 20px;">国内外直播活跃榜</div>
<div class="item-row"><span class="tag-blue">属性</span> 活跃观众、主播、弹幕、时长</div>
<div class="item-row"><span class="tag-blue">参数</span> 国内(播酱) / 国外(Twitch)</div>
<div class="item-row"><span class="tag-red">限制</span> 国内按月统计，国外近30日</div>
</div>""", unsafe_allow_html=True)

    with cd3:
        st.markdown(
"""<div class="dashboard-card">
<div class="card-title">🎬 影视 IP 模块</div>
<div class="item-title">豆瓣 影视榜</div>
<div class="item-row"><span class="tag-blue">属性</span> 评分、评价人数、内容简介</div>
<div class="item-row"><span class="tag-blue">参数</span> 国产 / 欧美 / 日剧 / 韩剧</div>
<div class="item-row"><span class="tag-red">限制</span> 极易触发WAF，强限20条内</div>

<div class="item-title" style="margin-top: 20px;">IMDb 趋势榜</div>
<div class="item-row"><span class="tag-blue">属性</span> 全球流行度、评分、制作年份</div>
<div class="item-row"><span class="tag-blue">参数</span> 年份、月份、提取数量</div>
<div class="item-row"><span class="tag-red">限制</span> 受国际网络接口限流影响</div>
</div>""", unsafe_allow_html=True)

    st.write("")

    # --- 模块 C: 快捷分析模板 ---
    st.caption("✨ **快捷分析模板 (点击直接运行)**")
    cb1, cb2, cb3, cb4 = st.columns(4)
    cb1.button("📊 分析 4月 手游大盘", on_click=set_prompt, args=("分析 4月 手游大盘情况",), use_container_width=True)
    cb2.button("🎬 提取 豆瓣欧美剧 前 10名", on_click=set_prompt, args=("提取 豆瓣欧美剧前 10 名",), use_container_width=True)
    cb3.button("🎮 分析 PC与直播 跨端大盘", on_click=set_prompt, args=("分析 Steam 与 国内外直播榜单的大盘联动",), use_container_width=True)
    cb4.button("🌐 生成 泛娱乐全行业 简报", on_click=set_prompt, args=("生成本月泛娱乐全行业综合分析简报",), use_container_width=True)

st.markdown("---")

# ================= 4. 核心路由引擎 =================
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
    
    num = re.search(r'(\d+)名|前\s*(\d+)|(\d+)条', prompt)
    limit = num.group(1) or num.group(2) or num.group(3) if num else None
    
    dt = re.search(r'(\d{4})[年-]\s*(\d{1,2})', prompt)
    mo_only = re.search(r'(\d{1,2})月', prompt)
    now = datetime.now()
    year = dt.group(1) if dt else str(now.year)
    month = (dt.group(2) if dt else (mo_only.group(1) if mo_only else str(now.month))).zfill(2)

    tasks = []
    
    is_pan = any(k in p for k in ["泛娱乐", "全行业", "全局", "综合"])
    l_hvy = limit if limit else "20" 
    l_std = limit if limit else "100"

    # --- 1. 手游模块触发器 ---
    if is_pan or any(k in p for k in ["手游", "移动", "tap", "玩匠", "大盘"]):
        if is_pan or any(k in p for k in ["tap", "手游", "大盘"]): 
            tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": l_std}})
        if is_pan or any(k in p for k in ["玩匠", "测", "手游", "大盘"]): 
            tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": l_hvy, "YEAR": year, "MONTH": month}})
            
    # --- 2. PC与直播触发器 (底层路由依然精准解耦) ---
    if is_pan or any(k in p for k in ["pc", "端游", "steam", "直播", "热度", "twitch", "播酱"]):
        if is_pan or any(k in p for k in ["steam", "pc", "端游"]): 
            tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": l_std}})
        
        has_live = any(k in p for k in ["直播", "热度", "twitch", "播酱"])
        if is_pan or has_live:
            is_domestic = any(k in p for k in ["国内", "播酱", "大陆"])
            is_intl = any(k in p for k in ["国外", "海外", "twitch", "国际"])
            
            if is_domestic and not is_intl:
                tasks.append({"script": "domestic_live.py", "env": {"SCRAPE_LIMIT": l_std}})
            elif is_intl and not is_domestic:
                tasks.append({"script": "intl_live.py", "env": {"SCRAPE_LIMIT": l_std}})
            else:
                tasks.append({"script": "domestic_live.py", "env": {"SCRAPE_LIMIT": l_std}})
                tasks.append({"script": "intl_live.py", "env": {"SCRAPE_LIMIT": l_std}})

    # --- 3. 影视模块触发器 ---
    if is_pan or any(k in p for k in ["影视", "电影", "剧", "豆瓣", "imdb"]):
        if is_pan or any(k in p for k in ["imdb", "影视"]): 
            tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": l_std, "YEAR": year, "MONTH": month}})
        if is_pan or any(k in p for k in ["豆瓣", "剧", "电影", "影视"]):
            tags = []
            if "欧美" in p: tags.append("欧美剧")
            if "韩" in p: tags.append("韩剧")
            if "日" in p: tags.append("日剧")
            if "国产" in p: tags.append("国产剧")
            if not tags: tags = ["欧美剧"] 
            for t in tags:
                tasks.append({"script": "douban.py", "env": {"SCRAPE_LIMIT": l_hvy, "DOUBAN_TAG": t}})
            
    return tasks

# ================= 5. 会话执行流 =================
if active_prompt:
    st.session_state.trigger_prompt = None 
    st.session_state.history.append({"role": "user", "content": active_prompt})
    if len(st.session_state.history) == 1:
        st.rerun()

for chat in st.session_state.history:
    with st.chat_message(chat["role"]): st.markdown(chat["content"])

if active_prompt and len(st.session_state.history) > 0 and st.session_state.history[-1]["role"] == "user":
    tasks = parse_intent(active_prompt)
    if tasks:
        all_dfs = []
        with st.status(f"🚀 路由解析完毕，并发启动 {len(tasks)} 个采集通道...", expanded=True) as status:
            for task in tasks:
                st.write(f"📡 穿透目标节点：`{task['script']}`")
                code, res_csv = run_spider(task["script"], task["env"])
                if code == 0 and os.path.exists(res_csv):
                    df = pd.read_csv(res_csv)
                    st.success(f"✅ {task['script']} 提取完成 (共 {len(df)} 条)")
                    
                    with st.expander(f"📦 查看 {task['script']} 数据结果"):
                        st.dataframe(df, hide_index=True, use_container_width=True)
                        
                    all_dfs.append(f"### 数据源: {task['script']}\n" + df.to_markdown(index=False))
                    os.remove(res_csv)
                else:
                    st.error(f"❌ {task['script']} 执行失败")

            if all_dfs:
                status.update(label=f"数据汇聚完成。正在生成商业简报...", state="running")
                
                ai_prompt = f"""
                你是一位具备全局视野的商业分析师。请基于以下底层采集的实时结构化数据，撰写商业简报。
                
                底层数据源：
                {"\n\n".join(all_dfs)}
                
                排版要求（必须严格遵守）：
                1. 🎯 **核心结论**：一句话概括最重要的数据趋势结论（加粗显示）。
                2. 📊 **数据论证**：使用无序列表列出 2-3 个支撑事实，必须引用表中的具体数值或排名（数字加粗）。
                3. 💡 **战略启示**：给出一个具体的业务落地建议。
                """
                with st.chat_message("assistant"):
                    try:
                        resp = CLIENT.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": ai_prompt}])
                        ans = resp.choices[0].message.content
                        st.markdown(ans)
                        st.session_state.history.append({"role": "assistant", "content": ans})
                    except:
                        st.error("AI 简报服务响应超时，请直接参考上方的数据表格进行研判。")
                status.update(label="全部执行完毕", state="complete")
    else:
        st.warning("⚠️ 无法识别有效路由，请参考上方的指令构造公式（如：分析 手游大盘）。")
