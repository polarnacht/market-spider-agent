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
    st.caption("🟢 四源复合引擎: 就绪")

# --- 3. 数据源与指令说明 (升级为 2x2 网格) ---
with st.expander("📌 数据源规格与指令说明 (点击展开)", expanded=True):
    st.markdown("本系统支持**单点精细查询**与**跨界宏观大盘分析**，底层依托四大核心模块：")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📱 手游大盘 (TapTap 预约榜)")
        st.markdown("""
        * **时效**：实时快照，无历史回溯。
        * **价值**：反映国内中长期的产品潜力与玩家关注度。
        """)
        st.markdown("### 📅 手游节点 (玩匠 开测榜)")
        st.markdown("""
        * **时效**：按月检索，获取近期密集开测的标的。
        * **价值**：追踪厂商短线宣发节点与测试期热度转化。
        """)
    with col2:
        st.markdown("### 💻 PC 端游大盘 (Steam 愿望榜)")
        st.markdown("""
        * **时效**：实时动能（含近7日/30日热度变化）。
        * **价值**：全球独立游戏与 3A 商业大作的买断制大盘。
        """)
        st.markdown("### 🎬 泛娱乐大盘 (IMDb 影视榜)")
        st.markdown("""
        * **时效**：自然月度历史回溯。
        * **价值**：跨越游戏边界，洞察全球影视 IP 流行趋势。
        """)
    
    st.divider()
    st.markdown("""
    #### 💡 指令范例 (支持智能参数缺省)
    * **【单点精细提取】**：`提取 玩匠 2026年2月 开测榜前 10 名`
    * **【手游生命周期联动】**：`分析国内手游整体情况` *(联动 TapTap预约 + 玩匠开测，看穿大盘长短线)*
    * **【跨端游戏联动】**：`分析目前所有游戏大盘情况` *(联动 手游 + PC)*
    * **【全局聚合研报】**：`生成泛娱乐全行业分析简报` *(四源并发，终极跨界研报)*
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

# --- 5. 复合意图解析器 (新增对 玩匠/开测 的路由) ---
def parse_intent(prompt):
    p_lower = prompt.lower()
    
    limit_match = re.search(r'(\d+)名|前\s*(\d+)|(\d+)条', prompt)
    explicit_limit = limit_match.group(1) or limit_match.group(2) or limit_match.group(3) if limit_match else None
    
    date_match = re.search(r'(\d{4})[年-]\s*(\d{1,2})', prompt)
    now = datetime.now()
    year = date_match.group(1) if date_match else str(now.year)
    month = date_match.group(2) if date_match else str(now.month).zfill(2)

    is_macro = any(kw in p_lower for kw in ["所有", "整体", "大盘", "全局", "全行业"])
    
    # 玩匠由于需要搜索TapTap详情，耗时较长，宏观模式限制在20条以内保证体验
    wanjiang_limit = explicit_limit if explicit_limit else ("20" if is_macro else "5")
    final_limit = explicit_limit if explicit_limit else ("200" if is_macro else "5")

    tasks = []
    
    # 路由一：全局全行业联动 (四源并发)
    if "全行业" in p_lower or "泛娱乐" in p_lower or ("所有市场" in p_lower):
        tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": wanjiang_limit, "YEAR": year, "MONTH": month}})
        tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": final_limit}})
        tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": final_limit}})
        tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": final_limit, "YEAR": year, "MONTH": month}})
        
    # 路由二：跨端游戏联动 (三大游戏源)
    elif "所有游戏" in p_lower or ("游戏" in p_lower and is_macro):
        tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": wanjiang_limit, "YEAR": year, "MONTH": month}})
        tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": final_limit}})
        tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": final_limit}})
        
    # 路由三：国内手游生命周期联动 (开测 + 预约)
    elif "手游" in p_lower and is_macro:
        tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": wanjiang_limit, "YEAR": year, "MONTH": month}})
        tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": final_limit}})

    # 路由四：精准单模块
    else:
        if "手游" in p_lower or "tap" in p_lower or "预约" in p_lower:
            tasks.append({"script": "taptap.py", "env": {"SCRAPE_LIMIT": final_limit}})
        if "端游" in p_lower or "pc" in p_lower or "steam" in p_lower:
            tasks.append({"script": "steam.py", "env": {"SCRAPE_LIMIT": final_limit}})
        if "影视" in p_lower or "imdb" in p_lower:
            tasks.append({"script": "imdb.py", "env": {"SCRAPE_LIMIT": final_limit, "YEAR": year, "MONTH": month}})
        # 新增玩匠入口
        if "玩匠" in p_lower or "开测" in p_lower or "测试" in p_lower:
            tasks.append({"script": "wanjiang.py", "env": {"SCRAPE_LIMIT": wanjiang_limit, "YEAR": year, "MONTH": month}})
            
    return tasks

# --- 6. 核心对话流 ---
if "history" not in st.session_state:
    st.session_state.history = []

for chat in st.session_state.history:
    with st.chat_message(chat["role"]):
        st.markdown(chat["content"])

if prompt := st.chat_input("输入提取指令 (例：分析国内手游整体情况)..."):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    tasks = parse_intent(prompt)

    if tasks:
        combined_md_list = []
        total_data_count = 0
        has_error = False

        with st.status(f"🚀 任务解析完毕：识别到 {len(tasks)} 个并发采集路由，正在下发调度...", expanded=True) as status:
            for task in tasks:
                script_file = task["script"]
                env_vars = task["env"]
                
                module_name = "近期开测(玩匠)" if "wanjiang" in script_file else "手游预约(TapTap)" if "tap" in script_file else "PC端游(Steam)" if "steam" in script_file else "影视(IMDb)"
                st.write(f"🔄 正在拉起 `{module_name}` 引擎...")
                
                ret_code, res_csv, final_logs = run_spider_with_progress(script_file, env_vars)

                if ret_code == 0 and os.path.exists(res_csv):
                    df = pd.read_csv(res_csv)
                    data_len = len(df)
                    total_data_count += data_len
                    st.success(f"✅ `{module_name}` 抓取完成，加载 {data_len} 条数据。")
                    
                    st.dataframe(df)
                    combined_md_list.append(f"### 【{module_name} 模块数据】\n" + df.to_markdown(index=False))
                    os.remove(res_csv)
                else:
                    has_error = True
                    st.error(f"❌ `{module_name}` 执行失败，请检查诊断日志：")
                    with st.expander("展开内核诊断日志"):
                        st.code(final_logs)

            if not has_error and total_data_count > 0:
                status.update(label=f"数据汇集完毕！共计 {total_data_count} 条，正在调用 AI 引擎生成洞察...", state="running")
                
                # === 动态分析策略引擎 ===
                if len(tasks) >= 3:
                    analysis_strategy = "本次分析包含【跨界大盘】多源数据。请在宏观概览基础上，重点提炼各平台/生态的竞争特征差异，输出具有顶层视角的全局商业洞察。"
                elif any("wanjiang" in t["script"] for t in tasks) and any("tap" in t["script"] for t in tasks):
                    analysis_strategy = "本次分析联动了手游市场的【即将开测（短线热度）】与【长期预约（中长线潜力）】双榜单。请交叉对比两份数据，分析厂商的宣发节奏特征与赛道布局规律。"
                elif total_data_count <= 10:
                    analysis_strategy = "提取核心标的信息。请直接以精炼的无序列表形式输出关键数据表现，不做发散性的宏观趋势分析。"
                else:
                    analysis_strategy = "进行垂直赛道的宏观数据概览。重点关注：1. 头部资源的集中度；2. 增速最快或关注度最高的标的；3. 整体品类/题材特征。"

                final_data_md = "\n\n".join(combined_md_list)

                with st.chat_message("assistant"):
                    ai_prompt = f"""
你是一位顶尖的【泛娱乐与游戏行业商业分析师】。
请基于提供的实时抓取数据，精准响应用户需求。你的输出将直接作为高管汇报的 Brief，必须具备极高的“信息密度”和“专业度”。

【核心输入】
- 用户需求：{prompt}
- 洞察策略：{analysis_strategy}
- 原始数据表：
{final_data_md}

【分析准则：三大纪律】
1. 事实绝对保真：所有结论必须且只能从《原始数据表》中推导，严禁引入外部记忆或主观猜测。
2. 拒绝数据复读：必须提炼出数据背后的“业务特征”（如：长短线生命周期分布、赛道壁垒等）。
3. 拒绝废话文学：严禁使用“整体表现良好”等无信息量空话。若数据不足直接跳过。

【输出排版规范】
请严格遵循以下排版（无需开场白或解释过程，直接输出）：

👉 如果【洞察策略】要求简报（单点少量数据时）：
直接使用紧凑的无序列表，提炼各标的的核心数值特征。

👉 如果【洞察策略】要求宏观概览或跨平台对比时，请严格按照以下格式输出 3-5 个高阶结论：
### 💡 [提炼具有行业视角的小标题，如：中长线RPG霸榜，短线休闲品类密集测试]
- **数据**：[提取表格中的具体排名、数值差距或集中度占比]
- **结论**：[客观说明该数据反映的市场规律或宣发节点特征]

【高阶报告要求（极其重要）】
- 数据张力：在【数据】部分，请多计算并使用“倍数、占比、差距”等对比性词汇，并将核心数字用 **加粗** 标出。
- 行动启示：在【结论】的末尾，请务必用一句话补充该现象带来的“战略启示或应对建议”。

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
                status.update(label="调度终止，未获取到有效数据", state="error")

    else:
        st.warning("指令无法解析。请确保指令包含触发关键字（如：玩匠开测榜 / 手游整体情况 / 泛娱乐大盘）。")
