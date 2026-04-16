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
    st.header("🎛️ 系统控制")
    if st.button("🧹 清空当前对话与输出", use_container_width=True):
        st.session_state.history = []
        st.rerun()
    st.markdown("---")
    st.caption("系统状态：\n- 容器化运行: 正常\n- 数据流监听: 开启\n- 容灾与降级: 就绪")

# --- 3. 数据源与规格说明 (极简产品风格) ---
with st.expander("📌 数据源规格与指令说明", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 🎮 TapTap 预约榜")
        st.markdown(
            "**时效范围**：实时数据\n"
            "**包含字段**：排名、名称、简介、标签、厂商、预约量\n"
            "**提取限制**：仅限当前最新排名，不支持历史回溯\n"
            "**指令示例**：`提取 taptap 预约榜前 5 名`"
        )
    with col2:
        st.markdown("### 🕹️ Steam 愿望榜")
        st.markdown(
            "**时效范围**：实时数据（含近7日/30日热度变化）\n"
            "**包含字段**：排名、名称、热度增量、开发商、发行商\n"
            "**提取限制**：受限于性能，单次提取建议不超过 200 条\n"
            "**指令示例**：`分析 steam 愿望榜前 50 名`"
        )
    with col3:
        st.markdown("### 🎬 IMDb 影视榜")
        st.markdown(
            "**时效范围**：按自然月度支持历史回溯\n"
            "**包含字段**：排名、名称、评分、链接\n"
            "**提取限制**：查询必须包含具体的年份与月份\n"
            "**指令示例**：`提取 imdb 2026年3月前 5 名`"
        )

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
            log_area.caption(f"⚙️ Kernel Log: {clean_line}")

            progress_match = re.search(r"\[(\d+)/(\d+)\]", clean_line)
            if progress_match:
                current = int(progress_match.group(1))
                total = int(progress_match.group(2))
                progress_bar.progress(min(current / total, 1.0))

    return_code = process.wait()
    return return_code, output_csv, "\n".join(full_logs)

# --- 5. 意图解析器 ---
def parse_intent(prompt):
    limit = re.search(r'(\d+)', prompt).group(1) if re.search(r'(\d+)', prompt) else "5"
    date_match = re.search(r'(\d{4})[年-]\s*(\d{1,2})', prompt)
    year = date_match.group(1) if date_match else "2026"
    month = date_match.group(2) if date_match else "02"

    p_lower = prompt.lower()
    if "steam" in p_lower:
        return "steam.py", {"SCRAPE_LIMIT": limit}
    elif "tap" in p_lower:
        return "taptap.py", {"SCRAPE_LIMIT": limit}
    elif "imdb" in p_lower:
        return "imdb.py", {"SCRAPE_LIMIT": limit, "YEAR": year, "MONTH": month}
    return None, None

# --- 6. 核心对话流 ---
if "history" not in st.session_state:
    st.session_state.history = []

for chat in st.session_state.history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

if prompt := st.chat_input("输入提取指令 (参考上方指令示例)..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    script_file, env_vars = parse_intent(prompt)

    if script_file:
        with st.status(f"执行中：调用 `{script_file}` 内核...", expanded=True) as status:
            ret_code, res_csv, final_logs = run_spider_with_progress(script_file, env_vars)

            if ret_code == 0 and os.path.exists(res_csv):
                df = pd.read_csv(res_csv)
                data_count = len(df)
                st.success(f"任务完成：成功加载 {data_count} 条数据。")
                st.dataframe(df)

                data_md = df.to_markdown(index=False)
                
                # === 根据数据量动态生成分析策略 ===
                if data_count <= 10:
                    analysis_strategy = "提取核心标的信息。请直接以精炼的列表形式输出这几款产品的关键数据表现，不做发散性的宏观趋势分析。"
                else:
                    analysis_strategy = "进行宏观数据概览。重点关注：1. 头部厂商/开发者的集中度；2. 增速最快（热度增量高）的标的；3. 整体品类分布特征。客观简练，避免过度口语化。"

                with st.chat_message("assistant"):
                    # === 结合你的专业 Prompt 结构 ===
                    ai_prompt = f"""
你是一个数据分析助手，请基于数据进行客观分析，不要编造信息。

【数据表】
{data_md}

【用户需求】
{prompt}

【分析策略】
{analysis_strategy}

【分析要求】
1. 先识别字段含义（如厂商、数值、时间等）
2. 所有结论必须基于数据，不允许主观推测
3. 禁止复述数据表内容
4. 禁止空洞结论（如“整体表现良好”）

【输出格式】
- 使用分点表达（不要长段落）
- 每一点必须有“数据支撑”
- 控制在 3-6 条结论
- 语言风格：客观、简洁、偏行业分析报告

直接输出结果，不要解释过程。

【重要约束】
如果数据不足以支持某个分析点，请直接跳过，不要补充或猜测。
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
                        st.error("API 调用超时，请直接查看原始数据。")

                status.update(label="处理完毕", state="complete")
                if os.path.exists(res_csv):
                    os.remove(res_csv)
            else:
                st.error("执行失败，日志详情：")
                with st.expander("展开内核日志"):
                    st.code(final_logs)
                st.info("提示：若出现 Timeout，请减少单次提取数量或稍后重试。")

    else:
        st.warning("指令无法解析。请确保包含关键字 (taptap / steam / imdb)。")
