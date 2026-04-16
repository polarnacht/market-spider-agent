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

st.set_page_config(page_title="战略研究-市场情报提取 Agent", layout="wide", page_icon="🛡️")

# --- 1. UI 头部设计 ---
st.title("🛡️ 战略研究-市场数据自动化提取与分析 Agent")
st.markdown("---")

# --- 2. 左侧边栏：控制面板 (视觉减负优化) ---
with st.sidebar:
    st.markdown("### 🎛️ 系统控制")
    # 移除全宽属性，增加 Tooltip，让按钮更精致小巧
    if st.button("🧹 清空会话与输出", help="一键重置当前界面的所有历史对话与表格"):
        st.session_state.history = []
        st.rerun()
    
    st.divider() # 添加优雅的分割线

    st.markdown("**系统监控状态**")
    st.caption("""
    🟢 容器化运行: 正常  
    🟢 数据流监听: 开启
    """) 


# --- 3. 数据源与规格说明 (保留清晰排版) ---
with st.expander("📌 数据源规格与指令说明", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 🎮 TapTap 预约榜")
        st.markdown("""
        * **时效范围**：实时数据
        * **包含字段**：排名、简介、标签、预约量
        * **提取限制**：仅限当前最新排名，不支持历史回溯
        * **指令示例**：`提取 taptap 预约榜前 5 名`
        """)
    with col2:
        st.markdown("### 🕹️ Steam 愿望榜")
        st.markdown("""
        * **时效范围**：实时数据（含近7/30日热度变化）
        * **包含字段**：排名、热度增量、开发/发行商
        * **提取限制**：受限性能，单次提取建议不超过 200 条
        * **指令示例**：`分析 steam 愿望榜前 50 名`
        """)
    with col3:
        st.markdown("### 🎬 IMDb 影视榜")
        st.markdown("""
        * **时效范围**：按自然月度支持历史回溯
        * **包含字段**：排名、名称、评分、链接
        * **提取限制**：查询需具体的年份与月份
        * **指令示例**：`提取 imdb 2026年3月前 5 名`
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
                    # === 最终版专业大模型分析 Prompt ===
                    ai_prompt = f"""
你是一位顶尖的【泛娱乐与游戏行业商业分析师】。
请基于提供的实时抓取数据，精准响应用户需求。你的输出将直接作为高管汇报的 Brief，必须具备极高的“信息密度”和“专业度”。

【核心输入】
- 用户需求：{prompt}
- 分析策略：{analysis_strategy}
- 原始数据表：
{data_md}

【分析准则：三大纪律】
1. 事实绝对保真：所有结论必须且只能从《原始数据表》中推导，严禁引入外部记忆或主观猜测。
2. 拒绝数据复读：不要把表格变成文字“报菜名”，必须提炼出数据背后的“业务特征”（如：资源集中度、断层领先、品类趋势等）。
3. 拒绝废话文学：严禁使用“整体表现良好”、“值得期待”等无信息量的空话。若数据不足以支撑某个维度，直接跳过。

【输出排版规范】
请严格遵循以下排版（无需开场白或解释过程，直接输出）：

👉 如果【分析策略】要求简报（数据较少时）：
直接使用紧凑的无序列表，提炼各标的的核心数值特征即可。

👉 如果【分析策略】要求宏观概览（数据较多时），请提炼 3-5 个最有价值的点，并严格按照以下格式输出：
### 💡 [提炼具有行业视角的小标题，如：大厂垄断头部，断层优势明显]
- **数据支撑**：[提取表格中的具体排名、数值差距或集中度占比]
- **业务结论**：[客观说明该数据反映的竞争格局或市场结构特征]

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
