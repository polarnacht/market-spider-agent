import streamlit as st
import pandas as pd
import subprocess
import os
import re
import uuid
import sys
from datetime import datetime
from openai import OpenAI

# ================= 1. 核心配置与极简样式 =================
API_KEY = st.secrets.get("api_key", "sk-cc6655649d204550bd5bcffd355ab4dd")
CLIENT = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

st.set_page_config(page_title="市场情报爬取 Agent", layout="wide", page_icon="🌐")

st.markdown("""
    <style>
    .main { background-color: #F8FAFC; }
    .ds-card { background: white; border: 1px solid #E2E8F0; padding: 15px 20px; border-radius: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.02); height: 100%; }
    .ds-header { font-size: 1.05rem; font-weight: 700; color: #0F172A; border-bottom: 2px solid #3B82F6; padding-bottom: 6px; margin-bottom: 12px; display: inline-block;}
    .ds-title { font-weight: 600; color: #1E293B; margin-top: 10px; margin-bottom: 4px; font-size: 0.95rem; }
    .ds-row { font-size: 0.85rem; color: #475569; margin-bottom: 4px; display: flex; align-items: center; }
    
    /* 精简标签 */
    .tag-blue { background: #EFF6FF; color: #2563EB; border: 1px solid #BFDBFE; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 8px; width: 40px; text-align: center; }
    .tag-red { background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 8px; width: 40px; text-align: center; }
    .tag-green { background: #F0FDF4; color: #16A34A; border: 1px solid #BBF7D0; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-right: 8px; width: 40px; text-align: center; }
    
    .guide-box { background: white; border: 1px solid #E2E8F0; padding: 15px 20px; border-radius: 8px; margin-bottom: 12px;}
    code { color: #0369A1 !important; background: #F0F9FF !important; }
    
    /* 强制重写按钮样式为高级清爽蓝 */
    div[data-testid="stButton"] button {
        border: 1px solid #BFDBFE !important;
        color: #1D4ED8 !important;
        background-color: #EFF6FF !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
    }
    div[data-testid="stButton"] button:hover {
        border: 1px solid #3B82F6 !important;
        color: #FFFFFF !important;
        background-color: #3B82F6 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ================= 2. 状态初始化与顶栏 =================
if "history" not in st.session_state: st.session_state.history = []
if "trigger_prompt" not in st.session_state: st.session_state.trigger_prompt = None

def trigger_shortcut(cmd):
    st.session_state.trigger_prompt = cmd

col_t1, col_t2, col_t3 = st.columns([5, 2, 1])
with col_t1:
    st.title("🌐 战略研究-游戏市场信息 Agent")
with col_t3:
    st.write("") 
    if st.button("🧹 清空会话", use_container_width=True):
        st.session_state.history = []
        st.session_state.trigger_prompt = None
        st.rerun()

# ================= 3. 永久常驻面板 (绝对禁止隐藏) =================

# --- 模块 A: 指令规范 ---
st.markdown("### 💡 核心指令指南")
g1, g2 = st.columns(2)
with g1:
    st.markdown(
'<div class="guide-box">'
'<b>🎯 单点深度提取</b> <span style="font-size:0.85rem; color:#64748B;">(用于精准获取某个榜单)</span><br>'
'语法：<code>提取 [时间/分类] [数据源] [数量]</code>'
'</div>', unsafe_allow_html=True)
    st.button("▶ 示例运行：提取 国内直播 10", on_click=trigger_shortcut, args=("提取 国内直播 10",), use_container_width=True)

with g2:
    st.markdown(
'<div class="guide-box">'
'<b>🌐 宏观大盘联动</b> <span style="font-size:0.85rem; color:#64748B;">(并发拉起多数据源，生成研报)</span><br>'
'语法：<code>分析 [时间] [行业大类]</code>'
'</div>', unsafe_allow_html=True)
    st.button("▶ 示例运行：分析 4月 手游大盘", on_click=trigger_shortcut, args=("分析 4月 手游大盘",), use_container_width=True)

st.markdown("---")

# --- 模块 B: 数据源明细 (纯净无属性展示) ---
st.markdown("### 🗂️ 数据源明细")
d1, d2, d3 = st.columns(3)

with d1:
    st.markdown(
'<div class="ds-card">'
'<div class="ds-header">📱 手游模块</div>'
'<div class="ds-title">TapTap 预约榜</div>'
'<div class="ds-row"><span class="tag-blue">参数</span> 提取数量 (前N名)</div>'
'<div class="ds-row"><span class="tag-red">限制</span> 仅实时快照，无历史回溯</div>'
'<div class="ds-title" style="margin-top: 18px;">玩匠(16P) 开测榜</div>'
'<div class="ds-row"><span class="tag-blue">参数</span> 年份、月份、提取数量</div>'
'<div class="ds-row"><span class="tag-green">支持</span> 支持历史大盘数据回溯</div>'
'</div>', unsafe_allow_html=True)

with d2:
    st.markdown(
'<div class="ds-card">'
'<div class="ds-header">💻 PC & 直播模块</div>'
'<div class="ds-title">Steam 愿望榜</div>'
'<div class="ds-row"><span class="tag-blue">参数</span> 提取数量 (前N名)</div>'
'<div class="ds-row"><span class="tag-red">限制</span> 实时接口，无历史回溯</div>'
'<div class="ds-title" style="margin-top: 18px;">国内外直播榜</div>'
'<div class="ds-row"><span class="tag-blue">参数</span> 国内(播酱) / 国外(Twitch)</div>'
'<div class="ds-row"><span class="tag-red">限制</span> 国内按月统计，国外近30日</div>'
'</div>', unsafe_allow_html=True)

with d3:
    st.markdown(
'<div class="ds-card">'
'<div class="ds-header">🎬 影视 IP 模块</div>'
'<div class="ds-title">豆瓣 影视榜</div>'
'<div class="ds-row"><span class="tag-blue">参数</span> 国产 / 欧美 / 日剧 / 韩剧</div>'
'<div class="ds-row"><span class="tag-red">限制</span> 极易触发WAF防护建议单点</div>'
'<div class="ds-title" style="margin-top: 18px;">IMDb 趋势榜</div>'
'<div class="ds-row"><span class="tag-blue">参数</span> 年份、月份、提取数量</div>'
'<div class="ds-row"><span class="tag-green">支持</span> 支持指定历史年月回溯</div>'
'</div>', unsafe_allow_html=True)

st.markdown("---")

# ================= 4. 核心执行引擎 (后端静默限流 50) =================
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
    
    dt = re.search(r'(\d{4})[年-]\s*(\d{1,2})', prompt)
    mo_only = re.search(r'(\d{1,2})月', prompt)
    now = datetime.now()
    year = dt.group(1) if dt else str(now.year)
    month = (dt.group(2) if dt else (mo_only.group(1) if mo_only else str(now.month))).zfill(2)

    clean_p = re.sub(r'\d{4}[年-]', '', p)
    clean_p = re.sub(r'\d{1,2}月', '', clean_p)
    
    num_match = re.search(r'前\s*(\d+)|(\d+)\s*[名条个]|(?:^|\s)(\d{1,3})(?:\s|$)', clean_p)
    
    limit = None
    if num_match:
        raw_limit = int(num_match.group(1) or num_match.group(2) or num_match.group(3))
        limit = str(min(raw_limit, 50)) # 后端静默安全熔断

    is_pan_entertainment = any(k in p for k in ["泛娱乐", "全行业", "全局", "综合"])
    is_sector_macro = "大盘" in p
    
    l_hvy = limit if limit else ("20" if (is_pan_entertainment or is_sector_macro) else "5")
    l_std = limit if limit else ("50" if (is_pan_entertainment or is_sector_macro) else "10")

    tasks = []
    
    if is_pan_entertainment or any(k in p for k in ["手游", "移动", "tap", "玩匠"]):
        if is_pan_entertainment or any(k in p for k in ["tap", "手游"]): 
            tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": l_std}})
        if is_pan_entertainment or any(k in p for k in ["玩匠", "测", "手游"]): 
            tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": l_hvy, "YEAR": year, "MONTH": month}})
            
    if is_pan_entertainment or any(k in p for k in ["pc", "端游", "steam", "直播", "热度", "twitch", "播酱"]):
        if is_pan_entertainment or any(k in p for k in ["steam", "pc", "端游"]): 
            tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": l_std}})
        
        has_live = any(k in p for k in ["直播", "热度", "twitch", "播酱"])
        if is_pan_entertainment or has_live:
            is_domestic = any(k in p for k in ["国内", "播酱", "大陆"])
            is_intl = any(k in p for k in ["国外", "海外", "twitch", "国际"])
            
            if is_domestic and not is_intl:
                tasks.append({"script": "domestic_live.py", "env": {"SCRAPE_LIMIT": l_std}})
            elif is_intl and not is_domestic:
                tasks.append({"script": "intl_live.py", "env": {"SCRAPE_LIMIT": l_std}})
            else:
                tasks.append({"script": "domestic_live.py", "env": {"SCRAPE_LIMIT": l_std}})
                tasks.append({"script": "intl_live.py", "env": {"SCRAPE_LIMIT": l_std}})

    if is_pan_entertainment or any(k in p for k in ["影视", "电影", "剧", "豆瓣", "imdb"]):
        if is_pan_entertainment or any(k in p for k in ["imdb", "影视"]): 
            tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": l_std, "YEAR": year, "MONTH": month}})
        if is_pan_entertainment or any(k in p for k in ["豆瓣", "剧", "电影", "影视"]):
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
        
        with st.status(f"🚀 正在并发拉起 {len(tasks)} 个目标数据源...", expanded=True) as status:
            for task in tasks:
                st.write(f"📡 执行抓取：`{task['script']}`")
                code, res_csv = run_spider(task["script"], task["env"])
                if code == 0 and os.path.exists(res_csv):
                    df = pd.read_csv(res_csv)
                    st.success(f"✅ {task['script']} 完成 (成功提取 {len(df)} 条)")
                    fetched_results.append({"script": task['script'], "df": df})
                    all_dfs.append(f"### 数据源: {task['script']}\n" + df.to_markdown(index=False))
                    os.remove(res_csv)
                else:
                    st.error(f"❌ {task['script']} 运行异常")
            status.update(label="✅ 数据采集完毕，准备生成研报", state="complete", expanded=False)

        if fetched_results:
            st.markdown("### 📦 抓取数据结果")
            # 统计总抓取量，供 AI 决策使用
            total_rows = sum(len(res['df']) for res in fetched_results)
            
            for res in fetched_results:
                with st.expander(f"查看 {res['script']} 原始表格 (共 {len(res['df'])} 条)", expanded=True):
                    st.dataframe(res['df'], hide_index=True, use_container_width=True)

            # ================= 高能 AI Prompt 植入区 =================
            ai_prompt = f"""
            你是一位顶级的泛娱乐商业情报分析师。请基于下方的【数据表】，输出“高质量的分析结论”，绝不能进行单纯的数据复述。
            
            【抓取状态】
            - 用户原始指令：{active_prompt}
            - 本次共获取数据：{total_rows} 条
            
            【数据表】
            {"\n\n".join(all_dfs)}
            
            ——————————
            【核心规则与禁忌（绝对遵守）】
            1. 坚守数据底线：所有的结论【必须百分之百】基于上方提供的数据表！
            2. 绝不脑补瞎猜：如果你发现表格中缺少某些关键维度数据，请【直接跳过】，严禁使用“可能是因为”、“推测原因”等主观话术！
            3. 禁止复述表格：要找差距、找极值、找头部集中度，而不是把表格顺着念一遍。
            4. 不要出现“第一点/第二点”这种敷衍的词，直接使用行业小标题。
            
            ——————————
            【根据数据量动态输出】
            请判断本次数据量 {total_rows}，严格执行以下对应模式：
            
            👉 若数据总量 ≤ 10 条（触发【简报模式】）：
            - 动作：不做延展分析。
            - 格式：直接输出 3-4 条干练的无序列表。
            - 内容：指出数据最突出的特征（如谁断层领先、谁最反常），必须带上具体数值或排名。
            - 禁忌：禁止包含任何长篇大论的“战略启示”或宏观预测。
            
            👉 若数据总量 > 10 条（触发【宏观模式】）：
            - 动作：进行横向和深度的商业研判。
            - 格式：挑选 3-5 个最有信息量的维度，输出“小标题 + 深度结论”。
            - 内容：
              1. 必须包含【数据张力】：即一定要计算出明显的差距倍数、占比、或排名变动。
              2. 必须包含【战略启示】：基于这批宏观数据，给大厂或发行方一条明确的业务落地建议。
            """
            
            with st.chat_message("assistant"):
                try:
                    resp = CLIENT.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": ai_prompt}])
                    ans = resp.choices[0].message.content
                    st.markdown(ans)
                    st.session_state.history.append({"role": "assistant", "content": ans})
                except:
                    st.error("AI 分析服务连接失败，请直接查阅上方的数据表。")
    else:
        st.warning("⚠️ 未能识别出需要抓取的分类，请参考上方的指令构造指南。")
