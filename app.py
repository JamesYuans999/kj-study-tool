import streamlit as st
import requests
import json
import datetime
import pandas as pd
import pdfplumber
from supabase import create_client
import time

# --- 1. 核心配置与风格定义 ---
st.set_page_config(page_title="中级会计冲刺班", page_icon="🥝", layout="wide")

# 🎨 注入自定义 CSS (实现奶油绿 + 卡片风格)
st.markdown("""
<style>
    /* 全局背景色：奶油白 */
    .stApp {
        background-color: #F9F9F0;
    }
    
    /* 侧边栏背景 */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #EEEEEE;
    }

    /* 卡片通用样式 */
    .css-card {
        background-color: #FFFFFF;
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        border: 1px solid #F0F0F0;
    }

    /* 绿色强调色文字 */
    .green-text {
        color: #00C090;
        font-weight: bold;
    }

    /* 大数字样式 */
    .big-number {
        font-size: 32px;
        font-weight: 800;
        color: #2C3E50;
    }

    /* 按钮样式覆盖 */
    .stButton>button {
        background-color: #00C090;
        color: white;
        border-radius: 10px;
        border: none;
        height: 45px;
        font-weight: bold;
        box-shadow: 0 4px 0 #009670; /* 按钮立体感 */
        transition: all 0.2s;
    }
    .stButton>button:hover {
        background-color: #00A87E;
        box-shadow: 0 2px 0 #009670;
        transform: translateY(2px);
        color: white;
    }
    
    /* 进度条颜色 */
    .stProgress > div > div > div > div {
        background-color: #00C090;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. 连接数据库 ---
try:
    # 兼容本地开发和云端部署的 Secrets 获取
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
except:
    st.error("🔒 请配置 Secrets 才能启动系统")
    st.stop()

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# --- 3. 辅助函数 ---

def get_user_profile(user_id):
    """获取用户档案，如果没有则创建"""
    try:
        res = supabase.table("study_profile").select("*").eq("user_id", user_id).execute()
        if not res.data:
            # 初始化一个空档案
            supabase.table("study_profile").insert({"user_id": user_id}).execute()
            return {}
        return res.data[0]
    except:
        return {}

def update_exam_date(user_id, date_obj):
    """更新考试日期"""
    try:
        supabase.table("study_profile").update({"exam_date": str(date_obj)}).eq("user_id", user_id).execute()
        st.toast("考试日期已更新，战斗开始！", icon="🔥")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"设置失败: {e}")

def get_teacher_message(days_left):
    """🤖 AI 班主任：根据剩余天数生成毒舌/鼓励语录"""
    # 这里我们用简单的逻辑模拟，实际上你可以调用 Gemini 生成
    # 为了响应速度，首页建议先用预设语录，或者异步调用 AI
    if days_left > 100:
        return "时间还多？那是你的错觉。现在的从容，就是考场上的噩梦。"
    elif days_left > 60:
        return "基础不牢，地动山摇。别假努力，结果不会陪你演戏。"
    elif days_left > 30:
        return "只有一个月了！现在多做一道题，考试少流一滴泪。"
    elif days_left > 7:
        return "最后冲刺！别看手机了，看我干嘛？去看书！"
    elif days_left > 0:
        return "稳住！你背的每一个分录，都是救命稻草！"
    elif days_left == 0:
        return "就是今天！乾坤未定，你我皆是黑马！"
    else:
        return "考试结束了？希望不用明年再见。"

# --- 4. 主程序逻辑 ---

# 模拟用户登录 (实际部署对接 Auth)
# 这里为了演示效果，我们先硬编码一个 user_id，或者你需要先去 Supabase Auth 创建一个用户
# 在实际 app 中，使用 st.login() 或 supabase.auth
if 'user_id' not in st.session_state:
    # 暂时使用一个固定的测试 ID，方便你立刻看到效果
    # ⚠️ 部署前请改为真实的 Auth 逻辑
    st.session_state.user_id = "test_user_001" 

user_id = st.session_state.user_id
profile = get_user_profile(user_id)

# 侧边栏导航
with st.sidebar:
    st.title("🥝 备考中心")
    st.write(f"你好，同学")
    
    menu = st.radio(
        "导航", 
        ["🏠 学习仪表盘", "📚 资料库 (双轨)", "📝 章节特训", "⚔️ 全真模考", "📊 弱项分析"],
        label_visibility="collapsed"
    )
    
    st.divider()
    # 考试日期设置
    st.write("📅 **考试日期设置**")
    default_date = datetime.date(2025, 9, 7)
    if profile and profile.get('exam_date'):
        try:
            default_date = datetime.datetime.strptime(profile['exam_date'], '%Y-%m-%d').date()
        except:
            pass
            
    new_date = st.date_input("目标日期", default_date, label_visibility="collapsed")
    if new_date != default_date:
        update_exam_date(user_id, new_date)

# === 页面：仪表盘 (Bento Grid 风格) ===
if menu == "🏠 学习仪表盘":
    
    # 1. 计算倒计时
    today = datetime.date.today()
    days_left = (new_date - today).days
    
    # 2. 顶部欢迎语 + 倒计时卡片
    st.markdown(f"### 🌞 早安，离上岸还有 <span style='color:#ff4b4b; font-size:1.2em'>{days_left}</span> 天", unsafe_allow_html=True)
    
    # AI 老师语录
    teacher_msg = get_teacher_message(days_left)
    st.info(f"👨‍🏫 **班主任说：** {teacher_msg}")

    # 3. Bento Grid 核心数据
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="css-card">
            <div style="color: #888; font-size: 14px;">📚 累计刷题</div>
            <div class="big-number">{profile.get('total_questions_done', 0)} <span style="font-size:16px; color:#aaa;">题</span></div>
            <div style="margin-top:10px;">
                <span style="background-color:#E8F5E9; color:#00C090; padding:2px 8px; border-radius:10px; font-size:12px;">今日 +5</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        # 模拟数据
        correct_rate = 68 
        st.markdown(f"""
        <div class="css-card">
            <div style="color: #888; font-size: 14px;">🎯 正确率</div>
            <div class="big-number">{correct_rate}%</div>
            <div style="margin-top:10px; height: 6px; background-color: #eee; border-radius: 3px;">
                <div style="width: {correct_rate}%; height: 100%; background-color: #00C090; border-radius: 3px;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        streak = profile.get('study_streak', 1)
        st.markdown(f"""
        <div class="css-card">
            <div style="color: #888; font-size: 14px;">🔥 连续打卡</div>
            <div class="big-number">{streak} <span style="font-size:16px; color:#aaa;">天</span></div>
            <div style="margin-top:10px; font-size:12px; color:#aaa;">
                保持 3 天以上有奖励
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 4. 科目进度概览
    st.markdown("#### 📖 科目攻克进度")
    
    # 模拟数据，后续从 DB 读取
    subjects = [
        {"name": "中级会计实务", "progress": 0.45, "color": "#00C090"},
        {"name": "财务管理", "progress": 0.30, "color": "#FFB74D"},
        {"name": "经济法", "progress": 0.15, "color": "#64B5F6"}
    ]
    
    col_sub1, col_sub2, col_sub3 = st.columns(3)
    
    for i, sub in enumerate(subjects):
        with [col_sub1, col_sub2, col_sub3][i]:
            st.markdown(f"""
            <div class="css-card" style="border-top: 4px solid {sub['color']};">
                <div style="font-weight: bold; margin-bottom: 10px;">{sub['name']}</div>
                <div style="font-size: 12px; color: #888; margin-bottom: 5px;">完成度 {int(sub['progress']*100)}%</div>
            </div>
            """, unsafe_allow_html=True)
            st.progress(sub['progress'])

elif menu == "📚 资料库 (双轨)":
    st.title("📂 资料上传中心")
    st.caption("请选择你要上传的资料类型，AI 将采用不同的处理策略。")
    
    type_tab1, type_tab2 = st.tabs(["📖 教科书/讲义 (生成题)", "📑 真题/练习卷 (录题)"])
    
    with type_tab1:
        st.success("✅ 模式 A：AI 将阅读内容，并结合网络考点，为你生成全新题目。")
        # 这里放置之前的上传逻辑，加上章节选择
        
    with type_tab2:
        st.warning("⚠️ 模式 B：AI 将严格提取文档中的题目和答案，不做修改。")
        
        c1, c2 = st.columns(2)
        with c1:
            ans_pos = st.selectbox("答案在哪里？", ["每道题紧接着答案", "文档末尾", "章节末尾"])
        with c2:
            st.text_input("给 AI 的特别叮嘱", placeholder="例如：忽略页眉水印，只提取选择题...")
            
        st.file_uploader("上传真题 PDF (支持 pdfplumber 增强解析)", type="pdf")

elif menu == "⚔️ 全真模考":
    st.title("⚔️ 全真模拟考试")
    
    col_set1, col_set2 = st.columns([2, 1])
    with col_set1:
        st.selectbox("选择科目", ["中级会计实务", "财务管理", "经济法"])
        mode = st.radio("试卷类型", ["🐢 完整版 (3小时/题量大)", "🐇 精简版 (快速自测/题量减半)"], horizontal=True)
        st.text_area("重点侧重 (提示词)", placeholder="例如：多出一点关于‘所得税’的题，少出一点‘存货’...")
        
        if st.button("🚀 生成并开始考试"):
            st.toast("正在联网搜索最新考纲并组卷...预计需要 30 秒")
            # 后续接入 Module 4 的逻辑

    with col_set2:
        st.markdown("""
        <div class="css-card">
            <h4>📜 历史记录</h4>
            <ul style="font-size: 13px; color: #666; padding-left: 20px;">
                <li>2025实务模拟一 (78分)</li>
                <li>财管专项突击 (55分) <span style="color:red">⚠️</span></li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

# ... 其他页面占位符 ...
