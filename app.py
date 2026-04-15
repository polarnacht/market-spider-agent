import streamlit as st
import pandas as pd
import subprocess
import os
import re
import uuid
import sys
import time
from openai import OpenAI
from datetime import datetime

# ================= 核心配置区 =================
# 优先从 Streamlit 云端安全配置(Secrets)中读取，若无则使用默认 Key
if "api_key" in st.secrets:
    API_KEY = st.secrets["api_key"]
else:
    API_KEY = "sk-cc6655649d204550bd5bcffd355ab4dd"

BASE_URL = "https://api.deepseek.com"
CLIENT = OpenAI(api_key=API_KEY, base_url=BASE_URL)

st.set_page_config(page_title="战略数分爬取 Agent", layout="wide", page_icon="🛡️")

# --- 1. UI 头部设计 ---
st.title("🛡️ 战略数分 - 市场信息提取 Agent")
st.markdown("---")

# --- 1.5 左侧边栏：控制面板 (新增清空功能) ---
with st.sidebar:
    st.header("🎛️ 控制面板")
    st.markdown("用于重置 Agent 状态，开启全新查询。")
    if st.button("🧹 清空所有对话和输出", use_container_width=True):
        st.session_state.history = []
        st.rerun()

# --- 2. 动态说明指南 ---
with st.expander("📌 使用指南与能力说明", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 🎮 TapTap 预约榜")
        st.caption("数据属性：**实时更新**")
        st.markdown(
            "- **功能**：抓取当前最新预约排名\n- **深度**：进入详情页提取简介及安卓预约量\n- **限制**：实时性强，无历史追溯")
    with col2:
        st.markdown("### 🕹️ Steam 畅销榜")
        st.caption("数据属性：**周度更新**")
        st.markdown(
            "- **功能**：抓取周畅销榜单\n- **深度**：支持追溯历史周数据、价格及排名变化\n- **限制**：以“周”为单位进行翻页")
    with col3:
        st.markdown("### 🎬 IMDb 影视榜")
        st.caption("数据属性：**月度更新**")
        st.markdown(
            "- **功能**：抓取全球影视热度榜\n- **深度**：支持自定义年份、月份查询\n- **限制**：按自然月筛选发布日期")

    st.info("""
    **💡 提问范式示例：**
    - **TapTap**: `提取 taptap 预约榜前 3 名`
    - **Steam**: `查看 steam 过去 2 周的畅销榜` (系统会自动翻页抓取历史周)
    - **IMDb**: `分析 imdb 2026年3月的前 3 名影视剧`
    """)


# --- 3. 实时调度内核 ---
def run_spider_with_progress(script_name, params):
    """
    通过 Popen 实时监听子进程输出，更新进度条与日志窗
    """
    task_id = str(uuid.uuid4())[:8]
    output_csv = f"result_{task_id}.csv"
    script_abs_path = os.path.abspath(script_name)
    python_exe = sys.executable

    env = os.environ.copy()
    env.update(params)
    env["OUTPUT_FILE"] = output_csv

    # 使用 Popen 开启实时流式监听
    process = subprocess.Popen(
        [python_exe, "-u", script_abs_path], # -u 确保输出不被缓存
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # 合并错误流
        text=True,
        encoding="utf-8",
        errors='replace',
        cwd=os.getcwd(),
        bufsize=1
    )

    # 在 st.status 内部创建动态占位符
    progress_bar = st.progress(0)
    log_area = st.empty()
    full_logs = []

    # 循环读取输出
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            clean_line = line.strip()
            full_logs.append(clean_line)
            # 实时显示日志行
            log_area.caption(f" 内核日志: {clean_line}")

            # 匹配进度格式 [x/y]
            progress_match = re.search(r"\[(\d+)/(\d+)\]", clean_line)
            if progress_match:
                current = int(progress_match.group(1))
                total = int(progress_match.group(2))
                # 限制进度在 0-1 之间
                progress_bar.progress(min(current / total, 1.0))

    return_code = process.wait()
    return return_code, output_csv, "\n".join(full_logs)


# --- 4. 指令意图解析器 ---
def parse_intent(prompt):
    limit = re.search(r'(\d+)', prompt).group(1) if re.search(r'(\d+)', prompt) else "5"
    date_match = re.search(r'(\d{4})[年-]\s*(\d{1,2})', prompt)
    year = date_match.group(1) if date_match else "2026"
    month = date_match.group(2) if date_match else "02"

    weeks = "1"
    if "周" in prompt:
        w_match = re.search(r'(\d+)周', prompt)
        weeks = w_match.group(1) if w_match else "1"

    p_lower = prompt.lower()
    if "steam" in p_lower:
        return "steam.py", {"SCRAPE_LIMIT": limit, "WEEKS_TO_SCRAPE": weeks}
    elif "tap" in p_lower:
        return "taptap.py", {"SCRAPE_LIMIT": limit}
    elif "imdb" in p_lower:
        return "imdb.py", {"SCRAPE_LIMIT": limit, "YEAR": year, "MONTH": month}
    return None, None


# --- 5. 对话交互逻辑 ---
if "history" not in st.session_state:
    st.session_state.history = []

# 渲染历史
for chat in st.session_state.history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

# 输入处理
if prompt := st.chat_input("在此输入您的提取指令..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    script_file, env_vars = parse_intent(prompt)

    if script_file:
        with st.status(f"⚙任务下达：启动 `{script_file}` 内核进行数据穿透...", expanded=True) as status:
            # 运行并显示实时进度
            ret_code, res_csv, final_logs = run_spider_with_progress(script_file, env_vars)

            if ret_code == 0 and os.path.exists(res_csv):
                df = pd.read_csv(res_csv)
                st.success(f"数据采集成功！已加载 {len(df)} 条结构化记录。")
                st.dataframe(df)

                # AI 分析
                data_md = df.to_markdown(index=False)
                with st.chat_message("assistant"):
                    ai_prompt = f"你是一个战略数分专家。基于实时抓取的数据表格：\n\n{data_md}\n\n请针对用户需求 '{prompt}' 进行总结与洞察。"
                    try:
                        resp = CLIENT.chat.completions.create(
                            model="deepseek-chat",
                            messages=[{"role": "user", "content": ai_prompt}]
                        )
                        ans = resp.choices[0].message.content
                        st.markdown(ans)
                        st.session_state.history.append({"role": "assistant", "content": ans})
                    except:
                        st.error("AI 战略洞察生成失败，请参考上方数据表格。")

                status.update(label="✅ 战略提取任务完成", state="complete")
                if os.path.exists(res_csv):
                    os.remove(res_csv)
            else:
                st.error(f"内核运行异常，详细日志如下：")
                with st.expander("点击查看底层日志详情"):
                    st.code(final_logs)
                st.info(" 战略分析：若出现 Timeout，通常由于云端网络或反爬升级，请尝试减少数量后重试。")

    else:
        st.warning("⚠无法识别您的指令。请参考顶部的【使用指南】进行提问。")
