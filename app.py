import streamlit as st
import pandas as pd
import time
from datetime import datetime

# ================= 1. 全局配置与视觉样式 =================
st.set_page_config(page_title="泛娱乐数据抓取 Agent", layout="wide", page_icon="🌐")

# 注入自定义 CSS，强化层级结构与卡片质感
st.markdown("""
    <style>
    .main { background-color: #F9FAFB; }
    /* 卡片样式 */
    .feature-card {
        background-color: #ffffff;
        border: 1px solid #E5E7EB;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        height: 100%;
    }
    .feature-card h4 { color: #1F2937; margin-top: 0; font-size: 1.1rem; border-bottom: 2px solid #3B82F6; display: inline-block; padding-bottom: 4px;}
    .feature-card p { color: #4B5563; font-size: 0.9rem; margin-top: 10px; line-height: 1.5; }
    /* 弱化辅助文字 */
    .helper-text { color: #9CA3AF; font-size: 0.85rem; }
    </style>
    """, unsafe_allow_html=True)

# ================= 2. 左侧侧边栏 (弱化技术，强化使用) =================
with st.sidebar:
    st.image("https://api.dicebear.com/7.x/shapes/svg?seed=agent&backgroundColor=3b82f6", width=50)
    st.markdown("### 📌 运行状态")
    st.caption("🎯 当前模式：泛娱乐分析")
    st.caption("📡 数据源状态：正常连接")
    st.caption(f"🕘 当前时间：{datetime.now().strftime('%Y-%m-%d')}")
    
    st.divider()
    
    st.markdown("### ⭐ 历史记录")
    st.button("📄 豆瓣电影TOP20_0416", use_container_width=True)
    st.button("📄 IMDb热门剧集_0415", use_container_width=True)
    st.button("📄 手游日韩出海对比_0410", use_container_width=True)

# ================= 3. 顶部导航与模块切换 =================
st.title("🌐 泛娱乐数据抓取 Agent")

# 模块切换 Tabs
tab_mobile, tab_pc, tab_pan = st.tabs(["👉 手游模块", "👉 PC 端游", "👉 泛娱乐综合（当前选中）"])

with tab_pan:
    # ================= 4. 主操作区 (第一视觉焦点) =================
    st.markdown("### 🤖 告诉 Agent 你需要什么数据")
    
    # 状态管理：用于快捷模板的点击填充
    if 'search_query' not in st.session_state:
        st.session_state.search_query = ""

    def update_query(new_query):
        st.session_state.search_query = new_query

    # 大输入框与主按钮
    col_input, col_btn = st.columns([5, 1])
    with col_input:
        query = st.text_input(
            "指令输入", 
            value=st.session_state.search_query,
            placeholder="请输入抓取指令，例如：获取豆瓣2026年高评分电影TOP10...", 
            label_visibility="collapsed"
        )
    with col_btn:
        submit = st.button("🔍 开始抓取", type="primary", use_container_width=True)

    # 快捷模板（可点击填充）
    st.markdown('<p class="helper-text">✨ 快捷模板（点击直接填充）：</p>', unsafe_allow_html=True)
    t1, t2, t3, t4 = st.columns(4)
    t1.button("📊 抓取豆瓣高评电影 TOP20", on_click=update_query, args=("抓取豆瓣高评分电影 TOP20",), use_container_width=True)
    t2.button("🎬 获取 IMDb 本月热门剧集", on_click=update_query, args=("获取 IMDb 本月热门剧集",), use_container_width=True)
    t3.button("🎮 抓取某手游详情页数据", on_click=update_query, args=("抓取《黑神话》手游详情页商业数据",), use_container_width=True)
    t4.button("📈 对比日韩 vs 欧美评分", on_click=update_query, args=("对比日韩 vs 欧美影视评分趋势",), use_container_width=True)

    # ================= 5. 参数筛选区 (辅助，选填) =================
    with st.expander("⚙️ 结构化参数筛选 (选填，不填则默认智能推断)"):
        f1, f2, f3 = st.columns(3)
        f1.selectbox("📍 地区筛选", ["自动推断", "欧美", "日韩", "国产"])
        f2.text_input("📅 时间范围", placeholder="例如：2026年3月")
        f3.selectbox("🔢 抓取数量", ["智能默认", "TOP10", "TOP20", "自定义"])

    st.divider()

    # ================= 6. 抓取能力与数据源说明 (结构化卡片) =================
    st.markdown("### 🎯 抓取能力模式")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class="feature-card">
            <h4>📍 单点深挖模式</h4>
            <p>• 输入具体对象（电影/游戏/主页）<br>• 获取完整详情（评分、评论、受众画像等）</p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="feature-card">
            <h4>📋 榜单聚合模式</h4>
            <p>• 支持 TOP N 批量提取<br>• 支持精确的分类/地区交叉筛选</p>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="feature-card">
            <h4>⏱️ 时间线回溯模式</h4>
            <p>• 支持 YEAR / MONTH 周期截取<br>• 可无缝回溯历史趋势与热度浮动</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.write("")
    
    # 动态数据源说明
    st.markdown("### 📊 挂载数据源能力")
    ds1, ds2 = st.columns(2)
    ds1.info("**🎬 豆瓣 (Douban)**\n* 获取核心评分、评论人数、内容分类标签\n* 深度查看用户口碑与本土受众偏好")
    ds2.info("**🌍 IMDb**\n* 获取全球权威热度排名与评分\n* 宏观分析国际流行趋势变化")

    # Prompt 使用说明 (折叠隐藏，弱化规则感)
    with st.expander("✏️ 进阶：如何写出更精准的抓取指令（点击展开参考）"):
        st.markdown("""
        系统采用智能 NLP 路由，但包含以下**核心要素**效果更佳：
        * **动作**：获取 / 抓取 / 对比
        * **数据源**：豆瓣 / IMDb / 手游榜单
        * **时间**：可选（如 2026年3月）
        * **数量**：可选（TOP10 / TOP20）

        **标准示例**：
        > *获取豆瓣2026年高评分电影TOP10*
        """)

    # ================= 7. 状态反馈与结果展示 (执行时触发) =================
    if submit and query:
        st.divider()
        st.markdown("### 📈 抓取结果看板")
        
        # 状态反馈区
        with st.status("📡 正在执行 Agent 调度网络...", expanded=True) as status:
            st.write("⏳ 正在解析自然语言指令特征...")
            time.sleep(0.8)
            st.write(f"📡 穿透请求目标数据源 (指令匹配: {query})...")
            time.sleep(1.2)
            st.write("📊 正在清洗并整理结构化结果...")
            time.sleep(1)
            status.update(label="✅ 抓取与清洗完毕！", state="complete", expanded=False)

        # 结果摘要
        r1, r2, r3 = st.columns(3)
        r1.metric("📦 已抓取数据量", "20 条")
        r2.metric("📅 覆盖时间跨度", "2026年全年")
        r3.metric("🎯 命中的数据源", "豆瓣 Douban")

        # 数据列表 (模拟展示)
        mock_data = pd.DataFrame({
            "排名": [1, 2, 3, 4, 5],
            "影视名称": ["星际穿越 (重映)", "肖申克的救赎 (4K)", "盗梦空间", "沙丘2", "三体 (腾讯版)"],
            "豆瓣评分": [9.4, 9.7, 9.4, 8.6, 8.9],
            "评价人数": ["250万+", "310万+", "210万+", "85万+", "120万+"],
            "地区": ["欧美", "欧美", "欧美", "欧美", "国产"]
        })
        st.dataframe(mock_data, use_container_width=True, hide_index=True)

        # 可选操作
        action1, action2, _ = st.columns([1, 1, 4])
        action1.button("📥 导出 CSV 报表", type="primary", use_container_width=True)
        action2.button("🧠 唤醒 AI 深度分析", use_container_width=True)
