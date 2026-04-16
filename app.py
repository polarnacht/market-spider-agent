import streamlit as st
import pandas as pd
import subprocess
import os
import re
import uuid
import sys
from datetime import datetime
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
    st.caption("🟢 五源复合引擎: 就绪")

# --- 3. 数据源与指令说明 ---
with st.expander("📌 数据源规格与指令说明 (点击展开)", expanded=True):
    st.markdown("本系统支持**单点精细查询**与**跨界宏观大盘分析**，现已集成五大核心模块：")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 📱 移动端矩阵")
        st.markdown("- **TapTap 预约榜**：实时快照，洞察中长线潜力。\n- **玩匠 开测榜**：按月检索，追踪短线宣发节点。")
    with col2:
        st.markdown("#### 💻 PC / 泛娱乐矩阵")
        st.markdown("- **Steam 愿望榜**：实时动能，全球买断制大盘。\n- **Steam 畅销榜**：单周维度，按实际商业化流水排行。\n- **IMDb 影视榜**：跨界边界，评估全球文娱 IP 趋势。")
    
    st.divider()
    st.markdown("""
    #### 💡 指令范例 (支持智能参数缺省)
    * **【单点商业提取】**：`提取 Steam畅销榜 前 10 名` *(提取本周实际销量排行)*
    * **【PC端游大盘】**：`分析目前所有 PC 游戏大盘情况` *(联动 愿望热度 + 畅销流水)*
    * **【全局聚合研报】**：`生成全行业游戏市场分析简报` *(四源并发)*
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
            log_area.caption(f"⚙️ 内核日志 [{script_name}]: {clean_line}")

            progress_match = re.search(r"\[(\d+)/(\d+)\]", clean_line)
            if progress_match:
                current = int(progress_match.group(1))
                total = int(progress_match.group(2))
                progress_bar.progress(min(current / total, 1.0))

    return_code = process.wait()
    return return_code, output_csv, "\n".join(full_logs)

# --- 5. 复合意图解析器 ---
def parse_intent(prompt):
    p_lower = prompt.lower()
    
    limit_match = re.search(r'(\d+)名|前\s*(\d+)|(\d+)条', prompt)
    explicit_limit = limit_match.group(1) or limit_match.group(2) or limit_match.group(3) if limit_match else None
    
    date_match = re.search(r'(\d{4})[年-]\s*(\d{1,2})', prompt)
    now = datetime.now()
    year = date_match.group(1) if date_match else str(now.year)
    month = date_match.group(2) if date_match else str(now.month).zfill(2)

    final_limit = explicit_limit if explicit_limit else "9999"
    tasks = []
    
    # 路由一：全局泛娱乐联动 (五源并发)
    if "全行业" in p_lower or "泛娱乐" in p_lower or ("所有市场" in p_lower):
        tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": final_limit, "YEAR": year, "MONTH": month}})
        tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": final_limit}})
        tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": final_limit}})
        tasks.append({"script": "steamdb.py", "env": {"SCRAPE_LIMIT": final_limit}})
        tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": final_limit, "YEAR": year, "MONTH": month}})
        
    # 路由二：跨端游戏联动 (手游 + PC，四大模块)
    elif "所有游戏" in p_lower or ("游戏" in p_lower and any(kw in p_lower for kw in ["整体", "大盘"])):
        tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": final_limit, "YEAR": year, "MONTH": month}})
        tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": final_limit}})
        tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": final_limit}})
        tasks.append({"script": "steamdb.py", "env": {"SCRAPE_LIMIT": final_limit}})
        
    # 路由三：PC 端游双榜联动 (愿望动能 + 畅销商业化)
    elif "端游" in p_lower or "pc" in p_lower:
        tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": final_limit}})
        tasks.append({"script": "steamdb.py", "env": {"SCRAPE_LIMIT": final_limit}})

    # 路由四：单点精准模块
    else:
        if "手游" in p_lower or "tap" in p_lower or "预约" in p_lower:
            tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": final_limit}})
        if "影视" in p_lower or "imdb" in p_lower:
            tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": final_limit, "YEAR": year, "MONTH": month}})
        if "玩匠" in p_lower or "开测" in p_lower or "测试" in p_lower:
            tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": final_limit, "YEAR": year, "MONTH": month}})
        if "畅销" in p_lower or "steamdb" in p_lower:
            tasks.append({"script": "steamdb.py", "env": {"SCRAPE_LIMIT": final_limit}})
        elif "steam" in p_lower or "愿望" in p_lower:
            tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": final_limit}})
            
    return tasks

# --- 6. 核心对话流 ---
if "history" not in st.session_state:
    st.session_state.history = []

for chat in st.session_state.history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

if prompt := st.chat_input("输入提取指令 (例：分析目前所有 PC 游戏大盘情况)..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    tasks = parse_intent(prompt)

    if tasks:
        combined_md_list = []
        total_data_count = 0
        has_error = False

        with st.status(f"🚀 识别到 {len(tasks)} 个采集路由，正在下发调度...", expanded=True) as status:
            for task in tasks:
                script_file = task["script"]
                env_vars = task["env"]
                
                module_map = {
                    "taptap.py": "手游潜力(TapTap)",
                    "wanjiang.py": "手游节点(玩匠)",
                    "steam.py": "PC动能(Steam愿望榜)",
                    "steamdb.py": "PC商业化(Steam畅销榜)",
                    "imdb.py": "影视IP(IMDb)"
                }
                module_name = module_map.get(script_file, script_file)
                st.write(f"🔄 正在拉起 `{module_name}` 引擎...")
                
                ret_code, res_csv, final_logs = run_spider_with_progress(script_file, env_vars)

                if ret_code == 0 and os.path.exists(res_csv):
                    df = pd.read_csv(res_csv)
                    data_len = len(df)
                    total_data_count += data_len
                    st.success(f"✅ `{module_name}` 抓取完成，成功提取 {data_len} 条商业数据。")
                    
                    st.dataframe(df)
                    combined_md_list.append(f"### 【{module_name} 数据矩阵】\n" + df.to_markdown(index=False))
                    os.remove(res_csv)
                else:
                    has_error = True
                    st.error(f"❌ `{module_name}` 执行失败，请检查诊断日志：")
                    with st.expander("展开内核诊断日志"):
                        st.code(final_logs)

            if total_data_count > 0:
                status.update(label=f"数据汇集完毕！共计 {total_data_count} 条，正在调用 AI 引擎生成洞察...", state="running")
                
                # === 动态分析策略引擎 ===
                if len(tasks) >= 3:
                    analysis_strategy = "本次分析包含【跨界大盘】的多源数据。请以顶层视角，分析各生态护城河的差异，输出全局商业洞察。"
                elif any("steam.py" in t["script"] for t in tasks) and any("steamdb.py" in t["script"] for t in tasks):
                    analysis_strategy = "本次联动了PC生态的【愿望单/发售前动能】与【畅销榜/实际营收能力】。请交叉分析玩家预期热度与实际买单转化率的差异，发掘具有高商业价值的品类特征。"
                elif total_data_count <= 10:
                    analysis_strategy = "提取核心标的商业信息。请直接以精炼的无序列表形式输出关键数据，不做发散。"
                else:
                    analysis_strategy = "进行赛道的宏观商业数据概览。重点关注：1. 头部厂商/IP的集中度；2. 排名剧烈变动（飙升/暴跌）的标的；3. 赛道主流定价区间与变现效率。"

                final_data_md = "\n\n".join(combined_md_list)

                with st.chat_message("assistant"):
                    ai_prompt = f"""
你是一位顶尖的【泛娱乐与游戏行业商业分析师】。
请基于提供的抓取数据，精准响应用户需求。你的输出将直接作为高管汇报的 Brief，必须具备极高的“信息密度”和“专业度”。

【核心输入】
- 用户需求：{prompt}
- 洞察策略：{analysis_strategy}
- 原始商业数据库：
{final_data_md}

【分析准则：三大纪律】
1. 事实绝对保真：结论必须且只能从《原始数据库》推导，严禁引入外部记忆。
2. 穿透数据表象：不要复读数据，必须提炼“业务特征”（如：营收集中度、买断制定价策略、长短线转化率等）。
3. 拒绝废话文学：严禁使用“整体表现良好”等空话。

【输出排版规范】
请严格遵循以下排版（无需开场白，直接输出）：

👉 如果【洞察策略】要求简报：
直接使用紧凑的无序列表，提炼核心财务与热度数值。

👉 如果【洞察策略】要求宏观或跨界联动时，请严格输出 3-5 个高阶结论：
### 💡 [具有行业视角的小标题，如：大厂虹吸效应显著，独立游戏低价突围]
- **数据**：[提取表格中的具体金额、断层倍数或占比，核心数字必须使用**加粗**]
- **结论**：[客观说明反映的市场规律，并在句末用一句话补充“战略启示/资源倾斜建议”]

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
                status.update(label="调度终止，所有节点未能获取有效数据", state="error")

    else:
        st.warning("指令无法解析。请确保指令包含触发关键字（如：Steam畅销榜 / PC大盘 / 泛娱乐整体情况）。")
