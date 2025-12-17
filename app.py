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
    .stApp { background-color: #F9F9F0; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #EEEEEE; }
    .css-card {
        background-color: #FFFFFF; border-radius: 15px; padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 20px; border: 1px solid #F0F0F0;
    }
    .big-number { font-size: 32px; font-weight: 800; color: #2C3E50; }
    .stButton>button {
        background-color: #00C090; color: white; border-radius: 10px; border: none;
        height: 45px; font-weight: bold; box-shadow: 0 4px 0 #009670; transition: all 0.2s;
    }
    .stButton>button:hover {
        background-color: #00A87E; box-shadow: 0 2px 0 #009670; transform: translateY(2px); color: white;
    }
    .stProgress > div > div > div > div { background-color: #00C090; }
</style>
""", unsafe_allow_html=True)

# --- 2. 连接数据库 & 获取 Secrets ---
try:
    # 这里读取 .streamlit/secrets.toml 文件中的配置
    API_KEY = st.secrets["GOOGLE_API_KEY"] # 对应 secrets.toml 里的变量名
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
except FileNotFoundError:
    st.error("🔒 未找到 secrets.toml 文件！请在项目根目录下创建 .streamlit/secrets.toml 并配置 Key。")
    st.stop()
except KeyError:
    st.error("🔒 Secrets 配置不完整！请检查 GOOGLE_API_KEY 和 supabase 节点是否都已填写。")
    st.stop()

@st.cache_resource
def init_supabase():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"连接数据库失败: {e}")
        return None

supabase = init_supabase()

# --- 3. 核心 AI 调用函数 (已修改为你指定的模型) ---

def call_gemini(prompt):
    """调用 Google Gemini (Robotics ER 1.5 Preview 模型)"""
    # ⚠️ 这里使用了你指定的特殊模型端点
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-robotics-er-1.5-preview:generateContent?key={API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            # 如果这个特殊模型不可用，打印错误信息方便调试
            st.error(f"AI 请求失败 (代码 {response.status_code}): {response.text}")
            return None
    except Exception as e:
        st.error(f"网络请求错误: {e}")
        return None

# --- 4. 辅助业务函数 ---

def get_user_profile(user_id):
    if not supabase: return {}
    try:
        res = supabase.table("study_profile").select("*").eq("user_id", user_id).execute()
        if not res.data:
            supabase.table("study_profile").insert({"user_id": user_id}).execute()
            return {}
        return res.data[0]
    except:
        return {}

def update_exam_date(user_id, date_obj):
    if not supabase: return
    try:
        supabase.table("study_profile").update({"exam_date": str(date_obj)}).eq("user_id", user_id).execute()
        st.toast("考试日期已更新！", icon="🔥")
        time.sleep(1)
        st.rerun()
    except:
        pass

def get_teacher_message(days_left):
    if days_left > 100: return "现在的从容，就是考场上的噩梦。"
    elif days_left > 60: return "基础不牢，地动山摇。别假努力。"
    elif days_left > 30: return "最后30天，多做一道题，少流一滴泪。"
    elif days_left > 0: return "别看手机了！看书！"
    elif days_left == 0: return "乾坤未定，你我皆是黑马！"
    else: return "希望能有好消息。"

# --- 5. 界面主逻辑 ---

if 'user_id' not in st.session_state:
    st.session_state.user_id = "test_user_001" # 暂用测试ID

user_id = st.session_state.user_id
profile = get_user_profile(user_id)

with st.sidebar:
    st.title("🥝 备考中心")
    st.write("你好，同学")
    menu = st.radio("导航", ["🏠 学习仪表盘", "📚 资料库 (双轨)", "📝 章节特训", "⚔️ 全真模考"], label_visibility="collapsed")
    st.divider()
    
    st.write("📅 **目标设定**")
    default_date = datetime.date(2025, 9, 7)
    if profile.get('exam_date'):
        try: default_date = datetime.datetime.strptime(profile['exam_date'], '%Y-%m-%d').date()
        except: pass
    
    new_date = st.date_input("考试日期", default_date, label_visibility="collapsed")
    if new_date != default_date:
        update_exam_date(user_id, new_date)

# === 仪表盘 ===
if menu == "🏠 学习仪表盘":
    today = datetime.date.today()
    days_left = (new_date - today).days
    
    st.markdown(f"### 🌞 距离考试还有 <span style='color:#ff4b4b; font-size:1.2em'>{days_left}</span> 天", unsafe_allow_html=True)
    st.info(f"👨‍🏫 **班主任：** {get_teacher_message(days_left)}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""<div class="css-card"><div style="color:#888;">📚 累计刷题</div><div class="big-number">{profile.get('total_questions_done', 0)}</div></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div class="css-card"><div style="color:#888;">🎯 正确率</div><div class="big-number">--%</div></div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div class="css-card"><div style="color:#888;">🔥 连续打卡</div><div class="big-number">{profile.get('study_streak', 0)} 天</div></div>""", unsafe_allow_html=True)

    st.markdown("#### 📖 科目进度")
    # 模拟展示
    for sub, color in [("中级会计实务", "#00C090"), ("财务管理", "#FFB74D"), ("经济法", "#64B5F6")]:
        st.markdown(f"""<div class="css-card" style="border-left:5px solid {color}; padding:15px;"><b>{sub}</b><br><span style="color:#888;font-size:12px">完成度 0%</span></div>""", unsafe_allow_html=True)

# === 资料库 ===
elif menu == "📚 资料库 (双轨)":
    st.title("📂 资料上传")
    t1, t2 = st.tabs(["📖 教科书/讲义", "📑 真题/试卷"])
    
    with t1:
        st.success("模式 A：上传教材，AI 将阅读并为你出题。")
        # 上传逻辑留空待填
        
    with t2:
        st.warning("模式 B：上传真题，AI 仅提取录入，不修改内容。")
        c1, c2 = st.columns(2)
        with c1: st.selectbox("答案位置", ["每题后", "文档末尾"])
        with c2: st.text_input("给AI的提示 (Prompt)", placeholder="例如：忽略水印...")
        st.file_uploader("上传 PDF", type="pdf")

# === 简单的连通性测试 ===
elif menu == "📝 章节特训":
    st.title("🤖 AI 模型测试")
    st.write("点击下方按钮，测试你指定的特殊模型是否能正常工作。")
    if st.button("测试 Gemini 连接"):
        with st.spinner("正在呼叫 Gemini Robotics 模型..."):
            res = call_gemini("你好，请用一句话通过会计的角度解释什么是‘资产’。")
            if res and 'candidates' in res:
                st.success("✅ 连接成功！模型回复如下：")
                st.write(res['candidates'][0]['content']['parts'][0]['text'])
            else:
                st.error("❌ 连接失败，请检查 API Key 或确认该模型权限。")
