import streamlit as st
import pandas as pd
import subprocess
import os
import re
import uuid
import sys
from openai import OpenAI

# ================= 核心配置区 =================
if "api_key" in st.secrets:
    API_KEY = st.secrets["api_key"]
else:
    API_KEY = "sk-cc6655649d204550bd5bcffd355ab4dd"

BASE_URL = "https://api.deepseek.com"
CLIENT = OpenAI(api_key=API_KEY, base_url=BASE_URL)

st.set_page_config(page_title="市场情报提取 Agent", layout="wide", page_icon="🛡️")

# --- 1. UI 头部设计 ---
st.title("🛡️ 市场数据自动化提取与分析 Agent")
st.markdown("---")

# --- 2. 左侧边栏：控制面板 ---
with st.sidebar:
    st.markdown("### 🎛️ 系统控制")
    if st.button("🧹 清空会话与输出", help="一键重置当前界面的所有历史对话与表格"):
        st.session_state.history = []
        st.rerun()
    
    st.divider() 
    
    st.markdown("**系统监控状态**")
    st.caption("🟢 容器化运行: 正常")
    st.caption("🟢 数据流监听: 开启")
    st.caption("🟢 多源聚合调度: 开启")

# --- 3. 数据源说明 ---
with st.expander("📌 数据源规格与指令说明", expanded=True):
    st.markdown("""
    本系统支持单点快速查询与**大盘聚合分析**，目前接入了三大典型代表数据源（未来可无限扩展）：
    * **🎮 TapTap 预约榜**：实时反映国内手游大盘动向。
    * **🕹️ Steam 愿望榜**：实时追踪全球 PC 端游热度动能。
    * **🎬 IMDb 影视榜**：按月回溯全球泛娱乐影视 IP 趋势。
    
    **💡 进阶指令示例（多源聚合分析）**：
    * `分析目前所有游戏整体情况`（系统将自动拉满 200 条，同时抓取 TapTap 和 Steam 进行跨端对比）
    * `分析手游大盘整体情况`（自动拉满 TapTap 数据进行深度分析）
    """)

# --- 4. 实时调度内核 ---
def run_spider_with_progress(script_name, params):
    task_id = str(uuid.uuid4())[:8]
    output_csv = f"result_{task_id}.csv"
    script_abs_path = os.path.abspath(script_name)
    python_exe = sys.executable

    env = os.environ.copy()
    env.update(params)
    env["OUTPUT_FILE"] = output_csv

    process = subprocess.Popen(
        [python_exe, "-u", script_abs_path], 
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  
        text=True,
        encoding="utf-8",
        errors='replace',
        cwd=os.getcwd(),
        bufsize=1
    )

    progress_bar = st.progress(0)
    log_area = st.empty()
    full_logs = []

    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            clean_line = line.strip()
            full_logs.append(clean_line)
            log_area.caption(f"⚙️ 核心日志 [{script_name}]: {clean_line}")

            progress_match = re.search(r"\[(\d+)/(\d+)\]", clean_line)
            if progress_match:
                current = int(progress_match.group(1))
                total = int(progress_match.group(2))
                progress_bar.progress(min(current / total, 1.0))

    return_code = process.wait()
    return return_code, output_csv, "\n".join(full_logs)

# --- 5. 多源意图解析器 (核心升级) ---
def parse_intent(prompt):
    p_lower = prompt.lower()
    limit = re.search(r'(\d+)', prompt).group(1) if re.search(r'(\d+)', prompt) else "5"
    date_match = re.search(r'(\d{4})[年-]\s*(\d{1,2})', prompt)
    year = date_match.group(1) if date_match else "2026"
    month = date_match.group(2) if date_match else "02"

    tasks = []
    
    # 宏观聚合指令路由
    if "所有游戏" in p_lower or "全局" in p_lower or ("整体" in p_lower and "游戏" in p_lower):
        tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": "200"}})
        tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": "200"}})
    elif "手游" in p_lower and ("整体" in p_lower or "大盘" in p_lower):
        tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": "200"}})
    elif ("端游" in p_lower or "pc" in p_lower) and ("整体" in p_lower or "大盘" in p_lower):
        tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": "200"}})
    # 单一精细指令路由
    elif "steam" in p_lower:
        tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": limit}})
    elif "tap" in p_lower:
        tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": limit}})
    elif "imdb" in p_lower:
        tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": limit, "YEAR": year, "MONTH": month}})
        
    return tasks

# --- 6. 核心对话流 ---
if "history" not in st.session_state:
    st.session_state.history = []

for chat in st.session_state.history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

if prompt := st.chat_input("输入提取指令 (例：分析目前所有游戏整体情况)..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    tasks = parse_intent(prompt)

    if tasks:
        combined_md_list = []
        total_data_count = 0
        has_error = False

        with st.status(f"🚀 执行中：识别到 {len(tasks)} 个采集任务，正在下发调度...", expanded=True) as status:
            # 依次执行任务队列
            for task in tasks:
                script_file = task["script"]
                env_vars = task["env"]
                
                st.write(f"🔄 正在拉起 `{script_file}` 数据引擎...")
                ret_code, res_csv, final_logs = run_spider_with_progress(script_file, env_vars)

                if ret_code == 0 and os.path.exists(res_csv):
                    df = pd.read_csv(res_csv)
                    data_len = len(df)
                    total_data_count += data_len
                    st.success(f"✅ `{script_file}` 采集完成，成功加载 {data_len} 条数据。")
                    
                    # 在界面展示该部分数据
                    st.dataframe(df)
                    
                    # 拼接到传给大模型的总 Markdown 中
                    source_name = "手游大盘数据" if "tap" in script_file else "PC端大盘数据" if "steam" in script_file else "影视大盘数据"
                    combined_md_list.append(f"### 【{source_name}】\n" + df.to_markdown(index=False))
                    os.remove(res_csv)
                else:
                    has_error = True
                    st.error(f"❌ `{script_file}` 执行失败，日志详情：")
                    with st.expander("展开内核日志"):
                        st.code(final_logs)

            if not has_error and total_data_count > 0:
                status.update(label=f"数据采集完毕，共计获取 {total_data_count} 条核心数据，开始战略洞察...", state="running")
                
                # === 动态分析策略：区分单源与多源聚合 ===
                if len(tasks) > 1:
                    analysis_strategy = "本次分析包含【跨平台】（如手游与PC端）的多源海量数据。请在宏观概览的基础上，增加『跨平台趋势对比』，分析不同平台的品类偏好、大厂布局差异等。重点提炼 4-5 个高价值的行业级结论。"
                elif total_data_count <= 10:
                    analysis_strategy = "提取核心标的信息。请直接以精炼的无序列表形式输出这几款产品的关键数据表现，不做发散性的宏观趋势分析。"
                else:
                    analysis_strategy = "进行宏观数据概览。重点关注：1. 头部厂商的集中度；2. 增速最快的标的；3. 整体品类分布特征。客观简练，避免过度口语化。"

                final_data_md = "\n\n".join(combined_md_list)

                with st.chat_message("assistant"):
                    ai_prompt = f"""
你是一位顶尖的【泛娱乐与游戏行业商业分析师】。
请基于提供的实时抓取数据，精准响应用户需求。你的输出将直接作为高管汇报的 Brief，必须具备极高的“信息密度”和“专业度”。

【核心输入】
- 用户需求：{prompt}
- 分析策略：{analysis_strategy}
- 原始多源数据表：
{final_data_md}

【分析准则：三大纪律】
1. 事实绝对保真：所有结论必须且只能从《原始多源数据表》中推导，严禁引入外部记忆或主观猜测。
2. 拒绝数据复读：必须提炼出数据背后的“业务特征”（如：资源集中度、跨端平台壁垒、品类趋势等）。
3. 拒绝废话文学：严禁使用“整体表现良好”等无信息量空话。若数据不足直接跳过。

【输出排版规范】
请严格遵循以下排版（无需开场白或解释过程，直接输出）：

👉 如果【分析策略】要求简报（数据较少时）：
直接使用紧凑的无序列表，提炼各标的的核心数值特征。

👉 如果【分析策略】包含宏观概览或跨平台对比时，请严格按照以下格式输出：
### 💡 [提炼具有行业视角的小标题，如：大厂垄断移动端，独立游戏突围PC端]
- **数据**：[提取跨平台表格中的具体排名、占比或数值对比，数字使用**加粗**]
- **结论**：[客观说明该现象反映的竞争格局，并在句末附上一句“战略启示/应对建议”]

开始执行：
                    """
                    
                    try:
                        resp = CLIENT.chat.completions.create(
                            model="deepseek-chat",
                            messages=[{"role": "user", "content": ai_prompt}]
                        )
                        ans = resp.choices[0].message.content
                        st.markdown(ans)
                        st.session_state.history.append({"role": "assistant", "content": ans})
                    except:
                        st.error("API 调用超时，请直接查看上方原始数据。")
                
                status.update(label="处理完毕", state="complete")
            else:
                status.update(label="调度终止", state="error")

    else:
        st.warning("指令无法解析。请确保包含关键字 (如：手游整体情况 / 所有游戏大盘 / taptap / steam)。")
