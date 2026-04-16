import streamlit as st
import pandas as pd
import subprocess
import os
import re
import uuid
import sys
from datetime import datetime
from openai import OpenAI

# ================= 1. 核心配置与初始化 =================
if "api_key" in st.secrets:
    API_KEY = st.secrets["api_key"]
else:
    API_KEY = "sk-cc6655649d204550bd5bcffd355ab4dd" # 建议在生产环境使用 secrets

BASE_URL = "https://api.deepseek.com"
CLIENT = OpenAI(api_key=API_KEY, base_url=BASE_URL)

st.set_page_config(page_title="大文娱市场情报 Agent", layout="wide", page_icon="🛡️")

# --- UI 头部 ---
st.title("🛡️ 泛娱乐市场情报提取与分析 Agent")
st.markdown("---")

# ================= 2. 左侧边栏控制面板 =================
with st.sidebar:
    st.markdown("### 🎛️ 系统调度中心")
    if st.button("🧹 重置所有会话", help="清空界面数据与历史对话"):
        st.session_state.history = []
        st.rerun()
    
    st.divider() 
    st.markdown("**内核引擎状态**")
    st.caption("🟢 容器化隔离: 激活")
    st.caption("🟢 穿透式提取: 开启 (textContent)")
    st.caption("🟢 跨模态分析: 就绪")
    st.divider()
    st.info("💡 提示：本 Agent 会自动识别指令中的年份、月份及抓取数量。若未指定，系统将按预设的大盘上限执行。")

# ================= 3. 数据源模块说明 (三大板块) =================
with st.expander("📌 数据源规格与指令说明 (点击展开)", expanded=True):
    st.markdown("本系统将情报来源划分为三大垂直板块，支持**单点深挖**或**跨模块联动分析**：")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### 📱 模块一：手游矩阵")
        st.markdown("""
        * **TapTap 预约榜**：洞察国内中长线人气潜力。
        * **玩匠 开测榜**：追踪厂商近期测试节点。
        * *注：支持全量提取当月所有开测项目。*
        """)

    with col2:
        st.markdown("#### 💻 模块二：PC 与直播热度")
        st.markdown("""
        * **Steam 愿望榜**：发售前全球人气动能。
        * **国内直播榜**：全平台(抖快B)直播热度。
        * **国外直播榜**：Twitch 全球内容流行趋势。
        """)

    with col3:
        st.markdown("#### 🎬 模块三：泛娱乐影视")
        st.markdown("""
        * **豆瓣 影视榜**：支持 国产/欧美/日韩 深度抓取。
        * **IMDb 趋势榜**：全球影视 IP 价值月度回溯。
        * *注：豆瓣详情页由于反爬严格，单次上限建议20条。*
        """)
    
    st.divider()
    st.markdown("""
    #### 💡 综合指令范例：
    * `分析 2026年4月 手游大盘` —— *(联动 TapTap + 玩匠，看穿当月长短线)*
    * `分析 PC 游戏及国内外直播热度` —— *(联动 Steam + 直播双源)*
    * `提取 豆瓣欧美剧 前 10 名` —— *(单点影视分类深挖)*
    * `生成 2026年4月 泛娱乐全行业简报` —— *(七大源全量联动，生成究极研报)*
    """)

# ================= 4. 实时调度引擎内核 =================
def run_spider_with_progress(script_name, params):
    task_id = str(uuid.uuid4())[:8]
    output_csv = f"result_{task_id}.csv"
    script_abs_path = os.path.abspath(script_name)
    python_exe = sys.executable

    env = os.environ.copy()
    env.update(params)
    env["OUTPUT_FILE"] = output_csv

    # 使用子进程模式运行，捕获实时日志
    process = subprocess.Popen(
        [python_exe, "-u", script_abs_path], 
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  
        text=True,
        encoding="utf-8",
        errors='replace',
        cwd=os.getcwd()
    )

    progress_bar = st.progress(0)
    log_area = st.empty()

    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            clean_line = line.strip()
            log_area.caption(f"⚙️ 引擎日志 [{script_name}]: {clean_line}")

            # 捕捉标准进度格式 [x/y]
            progress_match = re.search(r"\[(\d+)/(\d+)\]", clean_line)
            if progress_match:
                current = int(progress_match.group(1))
                total = int(progress_match.group(2))
                progress_bar.progress(min(current / total, 1.0))

    return_code = process.wait()
    return return_code, output_csv

# ================= 5. 跨模块意图解析器 (核心路由) =================
def parse_intent(prompt):
    p_lower = prompt.lower()
    
    # 提取数字 (默认值：宏观大盘 200 / 单点查询 5)
    limit_match = re.search(r'(\d+)名|前\s*(\d+)|(\d+)条', prompt)
    explicit_limit = limit_match.group(1) or limit_match.group(2) or limit_match.group(3) if limit_match else None
    
    # 提取时间 (缺省为当前时间)
    date_match = re.search(r'(\d{4})[年-]\s*(\d{1,2})', prompt)
    now = datetime.now()
    year = date_match.group(1) if date_match else str(now.year)
    month = date_match.group(2) if date_match else str(now.month).zfill(2)

    is_macro = any(kw in p_lower for kw in ["所有", "整体", "大盘", "全局", "全行业", "大行业", "综合"])
    
    # 针对不同站点的限速/耗时策略
    wanjiang_limit = explicit_limit if explicit_limit else ("20" if is_macro else "5")
    douban_limit = explicit_limit if explicit_limit else ("20" if is_macro else "5")
    final_limit = explicit_limit if explicit_limit else ("200" if is_macro else "5")

    tasks = []

    # --- 模块一：手游分类 ---
    if "手游" in p_lower or "移动端" in p_lower or "taptap" in p_lower or "玩匠" in p_lower:
        if is_macro or "taptap" in p_lower:
            tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": final_limit}})
        if is_macro or "玩匠" in p_lower or "开测" in p_lower:
            tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": wanjiang_limit, "YEAR": year, "MONTH": month}})

    # --- 模块二：PC 与直播分类 ---
    if "pc" in p_lower or "电脑" in p_lower or "steam" in p_lower or "直播" in p_lower or "twitch" in p_lower:
        if is_macro or "steam" in p_lower or "愿望" in p_lower:
            tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": final_limit}})
        if is_macro or "直播" in p_lower or "国内直播" in p_lower or "热度" in p_lower:
            tasks.append({"script": "domestic_live.py", "env": {"SCRAPE_LIMIT": final_limit}})
        if is_macro or "国外直播" in p_lower or "twitch" in p_lower:
            tasks.append({"script": "intl_live.py", "env": {"SCRAPE_LIMIT": final_limit}})

    # --- 模块三：泛娱乐影视分类 ---
    if "影视" in p_lower or "豆瓣" in p_lower or "imdb" in p_lower or "全行业" in p_lower or "泛娱乐" in p_lower:
        if is_macro or "imdb" in p_lower:
            tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": final_limit, "YEAR": year, "MONTH": month}})
        if is_macro or "豆瓣" in p_lower or "剧" in p_lower:
            db_tag = "欧美剧" if "欧美" in p_lower else "韩剧" if "韩" in p_lower else "日剧" if "日" in p_lower else "国产剧"
            tasks.append({"script": "douban.py", "env": {"SCRAPE_LIMIT": douban_limit, "DOUBAN_TAG": db_tag}})
            
    return tasks

# ================= 6. 交互处理与 AI 分析 =================
if "history" not in st.session_state:
    st.session_state.history = []

# 渲染历史对话
for chat in st.session_state.history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

if prompt := st.chat_input("输入提取指令 (例如：分析2026年4月全行业大盘)..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    tasks = parse_intent(prompt)

    if tasks:
        combined_md_list = []
        total_data_count = 0
        has_error = False

        with st.status(f"🚀 任务解析完毕：识别到 {len(tasks)} 个并行路由，开始抓取...", expanded=True) as status:
            for task in tasks:
                script_file = task["script"]
                env_vars = task["env"]
                
                module_map = {
                    "taptap.py": "手游潜力(TapTap)", "wanjiang.py": "手游节点(玩匠)",
                    "steam.py": "PC动能(Steam)", "domestic_live.py": "国内直播热度",
                    "intl_live.py": "国外直播热度", "douban.py": "影视热度(豆瓣)", "imdb.py": "影视IP(IMDb)"
                }
                module_name = module_map.get(script_file, script_file)
                st.write(f"🔄 正在启动 `{module_name}` 采集引擎...")
                
                ret_code, res_csv = run_spider_with_progress(script_file, env_vars)

                if ret_code == 0 and os.path.exists(res_csv):
                    df = pd.read_csv(res_csv)
                    total_data_count += len(df)
                    st.success(f"✅ `{module_name}` 采集完成，成功加载 {len(df)} 条数据。")
                    st.dataframe(df)
                    combined_md_list.append(f"### 【{module_name} 模块原始数据表】\n" + df.to_markdown(index=False))
                    os.remove(res_csv)
                else:
                    st.error(f"❌ `{module_name}` 模块运行异常。")

            if total_data_count > 0:
                status.update(label=f"聚合采集完毕！共获取 {total_data_count} 条核心数据，正在生成商业报告...", state="running")
                
                # --- AI 分析策略生成 ---
                analysis_strategy = "本次分析包含多源情报数据。"
                if len(tasks) >= 3:
                    analysis_strategy += " 请以【行业顶层视角】分析各模块数据。重点关注：1. 影游联动趋势；2. 国内外直播热度与发售预期的转化关系；3. 大厂在不同领域的分布特征。"
                else:
                    analysis_strategy += " 请进行宏观概览，分析头部资源的集中度、热度断层标的，并给出具有张力的数据对比（如倍数、占比）。"

                final_data_md = "\n\n".join(combined_md_list)

                with st.chat_message("assistant"):
                    ai_prompt = f"""
你是一位顶尖的【全赛道大文娱商业分析师】。
请基于提供的多维实时数据，出具一份高管级分析 Brief。

【输入数据】
- 用户指令：{prompt}
- 洞察策略：{analysis_strategy}
- 原始数据汇总：
{final_data_md}

【输出准则：三大纪律】
1. 事实绝对保真：结论严禁脱离提供的原始表格数据。
2. 数据张力对比：在提炼结论时，必须使用具体的数字对比，核心数字用 **加粗**。
3. 行动启示导向：每个结论必须包含该现象带来的“商业启示”或“战略建议”。

【排版要求】
请严格按照以下 Markdown 格式输出 3-5 条高价值洞察：
### 💡 [提炼具有行业视角的专业小标题]
- **核心数据**：[提取跨表对比的具体排名、数值、或断层比例，数字**加粗**]
- **商业结论**：[客观说明该现象反映的市场竞争格局，并在句末增加一句“战略启示/资源分配建议”]

开始执行：
                    """
                    try:
                        resp = CLIENT.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": ai_prompt}])
                        ans = resp.choices[0].message.content
                        st.markdown(ans)
                        st.session_state.history.append({"role": "assistant", "content": ans})
                    except:
                        st.error("AI 服务响应超时，请参考上方原始表格进行判断。")
                
                status.update(label="处理完毕", state="complete")
            else:
                status.update(label="未获取到有效数据", state="error")
    else:
        st.warning("指令无法识别。请确保包含关键字 (如：手游大盘 / 直播热度 / 豆瓣前10)。")
