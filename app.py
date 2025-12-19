import streamlit as st
# ... 其他 import ...

# --- 1. 全局配置与 Bootstrap 风格定义 ---
st.set_page_config(page_title="中级会计冲刺班 Pro", page_icon="🥝", layout="wide")

# 引入 Bootstrap Icons (图标库) 和 自定义高级 CSS
st.markdown("""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
<style>
    /* === 全局设定 (奶油绿主题) === */
    .stApp {
        background-color: #F9F9F0;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* 侧边栏美化 */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid rgba(0,0,0,0.05);
        box-shadow: 2px 0 10px rgba(0,0,0,0.02);
    }

    /* === Bootstrap 风格卡片 (核心) === */
    .card {
        background-color: #FFFFFF;
        border: 1px solid rgba(0,0,0,0.08); /* 淡边框 */
        border-radius: 12px; /* 圆角 */
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02); /* 初始淡阴影 */
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); /* 平滑动画 */
        position: relative;
        overflow: hidden;
    }
    
    /* 鼠标悬停特效 (Hover Effect) */
    .card:hover {
        box-shadow: 0 12px 24px rgba(0,192,144, 0.15); /* 绿色光晕 */
        transform: translateY(-4px); /* 向上浮动 */
        border-color: #00C090;
    }

    /* === 数据大屏数字 === */
    .stat-title {
        color: #6c757d; /* Bootstrap muted color */
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
        margin-bottom: 5px;
    }
    .stat-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #2C3E50;
    }
    .stat-icon {
        position: absolute;
        right: 20px;
        top: 20px;
        font-size: 2.5rem;
        color: rgba(0,192,144, 0.1); /* 浅绿色背景图标 */
    }

    /* === 按钮 Bootstrap 化 === */
    .stButton>button {
        background-color: #00C090;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        box-shadow: 0 4px 6px rgba(0, 192, 144, 0.3);
        transition: all 0.2s ease-in-out;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #00A87E;
        box-shadow: 0 6px 12px rgba(0, 192, 144, 0.4);
        transform: translateY(-1px);
    }
    .stButton>button:active {
        transform: translateY(1px);
        box-shadow: none;
    }

    /* === 选项列表美化 (List Group) === */
    .list-group-item {
        background-color: #fff;
        border: 1px solid rgba(0,0,0,.125);
        border-left: 5px solid #00C090;
        border-radius: 0.375rem;
        padding: 1rem;
        margin-bottom: 0.5rem;
        transition: background-color 0.2s;
    }
    .list-group-item:hover {
        background-color: #F0FFF9;
    }

    /* === 悬浮计时器 (Pill Badge) === */
    .timer-badge {
        position: fixed; top: 70px; right: 30px; z-index: 9999;
        background: linear-gradient(45deg, #00C090, #00E6AC);
        color: white;
        padding: 8px 20px;
        border-radius: 50px;
        font-weight: bold;
        font-size: 1.1rem;
        box-shadow: 0 4px 15px rgba(0,192,144, 0.4);
        display: flex;
        align-items: center;
        gap: 8px;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(0, 192, 144, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(0, 192, 144, 0); }
        100% { box-shadow: 0 0 0 0 rgba(0, 192, 144, 0); }
    }
    
    /* 聊天气泡优化 */
    .chat-bubble {
        padding: 15px; border-radius: 15px; margin: 10px 0; position: relative; max-width: 90%;
    }
    .chat-ai {
        background-color: #FFFFFF; 
        border-left: 4px solid #00C090;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .chat-user {
        background-color: #E3F2FD; 
        margin-left: auto;
        color: #0D47A1;
    }

</style>
""", unsafe_allow_html=True)

from openai import OpenAI
import streamlit as st
import requests
import json
import datetime
import pandas as pd
import pdfplumber
import time
import docx
from supabase import create_client
import plotly.express as px

# =========================================================
# 1. 全局配置与“奶油绿”风格定义
# =========================================================
st.set_page_config(page_title="中级会计冲刺班 Pro", page_icon="🥝", layout="wide")

st.markdown("""
<style>
    /* 全局色调 */
    .stApp { background-color: #F9F9F0; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #EEEEEE; }
    
    /* 卡片风格 */
    .css-card {
        background-color: #FFFFFF; border-radius: 15px; padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 20px; border: 1px solid #F0F0F0;
    }
    
    /* 聊天气泡风格 */
    .chat-user {
        background-color: #E3F2FD; padding: 10px; border-radius: 10px; margin: 5px 0; text-align: right;
    }
    .chat-ai {
        background-color: #F1F8E9; padding: 10px; border-radius: 10px; margin: 5px 0; border-left: 4px solid #00C090;
    }

    /* 按钮与高亮 */
    .big-number { font-size: 32px; font-weight: 800; color: #2C3E50; }
    .stButton>button {
        background-color: #00C090; color: white; border-radius: 10px; border: none;
        height: 45px; font-weight: bold; transition: all 0.2s;
    }
    .stButton>button:hover {
        background-color: #00A87E; transform: translateY(-2px); color: white;
    }
    
    /* 悬浮计时器 */
    .timer-box {
        position: fixed; top: 60px; right: 20px; z-index: 999;
        background-color: #FFFFFF; padding: 10px 20px; border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,192,144, 0.2);
        border: 2px solid #00C090; color: #00C090; font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 2. 核心连接与 Helper 函数
# =========================================================
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
except:
    st.error("🔒 请配置 .streamlit/secrets.toml")
    st.stop()




@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

@st.cache_data(ttl=3600)
def fetch_google_models(api_key):
    """
    专门获取 Google Gemini 可用模型列表
    """
    if not api_key: return []
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # 过滤出支持生成内容(generateContent)的模型，排除 embedding 模型
            models = []
            for m in data.get('models', []):
                if "generateContent" in m.get('supportedGenerationMethods', []):
                    # Google 返回格式通常是 "models/gemini-1.5-flash"，我们去掉前缀方便展示
                    name = m['name'].replace("models/", "")
                    models.append(name)
            return sorted(models, reverse=True) # 让新模型排前面
        return []
    except:
        return []

@st.cache_data(ttl=3600)
def fetch_openrouter_models(api_key):
    """
    获取 OpenRouter 模型列表，并标记是否免费
    """
    if not api_key: return []
    
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            raw_data = response.json().get('data', [])
            processed_list = []
            
            for m in raw_data:
                # 核心逻辑：检查定价是否为 0
                pricing = m.get('pricing', {})
                prompt_price = float(pricing.get('prompt', 0))
                completion_price = float(pricing.get('completion', 0))
                
                # 判定免费：价格为0 或者 ID以此为结尾
                is_free = (prompt_price == 0 and completion_price == 0) or m['id'].endswith(':free')
                
                processed_list.append({
                    "id": m['id'],
                    "name": m.get('name', m['id']),
                    "is_free": is_free
                })
            
            # 按字母排序
            return sorted(processed_list, key=lambda x: x['id'])
        return []
    except:
        return []
        

def get_user_profile(user_id):
    """获取用户档案"""
    try:
        res = supabase.table("study_profile").select("*").eq("user_id", user_id).execute()
        if not res.data:
            supabase.table("study_profile").insert({"user_id": user_id}).execute()
            return {}
        return res.data[0]
    except:
        return {}

def update_settings(user_id, settings_dict):
    """更新用户设置 (被 save_model_preference 调用)"""
    try:
        # 1. 获取旧设置
        current_data = get_user_profile(user_id)
        current_settings = current_data.get('settings') or {}
        
        # 2. 合并新设置
        current_settings.update(settings_dict)
        
        # 3. 存回数据库
        supabase.table("study_profile").update({"settings": current_settings}).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        print(f"Update settings error: {e}")
        return False

# ------------------------------------------------
def save_ai_settings():
    """
    回调函数：当用户切换 服务商 或 模型 时，自动保存配置到数据库
    """
    if st.session_state.get('user_id'):
        # 1. 获取当前选中的服务商 (从 key='ai_provider_select' 获取)
        current_provider = st.session_state.get('ai_provider_select')
        
        # 2. 获取当前选中的模型
        # 因为不同服务商对应不同的 selectbox key，我们需要判断
        current_model = None
        if current_provider and "OpenRouter" in current_provider:
            current_model = st.session_state.get('openrouter_model_select')
        elif current_provider and "DeepSeek" in current_provider:
            current_model = st.session_state.get('deepseek_model_select')
        elif current_provider and "Gemini" in current_provider:
            current_model = st.session_state.get('google_model_select')
            
        # 3. 存入数据库
        settings_to_update = {}
        if current_provider:
            settings_to_update["last_provider"] = current_provider
        if current_model:
            settings_to_update["last_used_model"] = current_model
            
        if settings_to_update:
            update_settings(st.session_state.user_id, settings_to_update)
            # st.toast("配置已同步云端", icon="☁️") # 可选：嫌烦可以注释掉提示
# ------------------------------------------------

def save_model_preference():
    """回调函数：当用户改变模型时，自动保存到 Supabase"""
    if st.session_state.get('user_id') and st.session_state.get('openrouter_model_select'):
        current_model = st.session_state.openrouter_model_select
        # 更新数据库
        update_settings(st.session_state.user_id, {"last_used_model": current_model})
        st.toast(f"已记住模型：{current_model}", icon="💾")


def call_ai_universal(prompt, history=[]):
    """
    通用 AI 调用接口 (全动态模型版)
    """
    provider = st.session_state.get('selected_provider', 'Gemini')
    
    try:
        # === 分支 A: Google Gemini 官方直连 ===
        if "Gemini" in provider:
            api_key = st.secrets["GOOGLE_API_KEY"]
            
            # 🔥 动态获取用户选择的模型，如果没有选，兜底用 1.5-flash
            model_id = st.session_state.get("google_model_id", "gemini-1.5-flash")
            
            # Google API URL 构造需要把模型名拼进去
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
            
            headers = {'Content-Type': 'application/json'}
            contents = []
            for h in history:
                role = "user" if h['role'] == 'user' else "model"
                contents.append({"role": role, "parts": [{"text": h['content']}]})
            contents.append({"role": "user", "parts": [{"text": prompt}]})
            
            data = {"contents": contents}
            response = requests.post(url, headers=headers, json=data, timeout=180)
            
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                return f"Gemini 报错 ({response.status_code}): {response.text}"

        # === 分支 B: DeepSeek 官方直连 ===
        elif "DeepSeek" in provider:
            client = OpenAI(
                api_key=st.secrets["deepseek"]["api_key"], 
                base_url=st.secrets["deepseek"]["base_url"]
            )
            # 🔥 动态获取 DeepSeek 模型 (chat 或 reasoner)
            model_id = st.session_state.get("deepseek_model_id", "deepseek-chat")
            
            messages = [{"role": "system", "content": "你是一位会计专家。"}]
            for h in history:
                messages.append({"role": h['role'], "content": h['content']})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(model=model_id, messages=messages)
            return response.choices[0].message.content

        # === 分支 C: OpenRouter ===
        elif "OpenRouter" in provider:
            client = OpenAI(
                api_key=st.secrets["openrouter"]["api_key"], 
                base_url=st.secrets["openrouter"]["base_url"]
            )
            # 🔥 动态获取 OpenRouter 模型
            model_id = st.session_state.get("openrouter_model_id", "google/gemini-2.0-flash-exp:free")
            
            messages = [{"role": "system", "content": "你是一位会计专家。"}]
            for h in history:
                role = "assistant" if h['role'] == "model" else h['role']
                messages.append({"role": role, "content": h['content']})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(model=model_id, messages=messages)
            return response.choices[0].message.content

    except Exception as e:
        return f"AI 调用异常: {str(e)}"

# --- 文档处理函数 ---
def extract_text_from_pdf(file, start_page=1, end_page=None):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            total = len(pdf.pages)
            if start_page < 1: start_page = 1
            if end_page is None or end_page > total: end_page = total
            for i in range(start_page - 1, end_page):
                text += pdf.pages[i].extract_text() + "\n"
        return text
    except: return ""

def extract_text_from_docx(file):
    try:
        doc = docx.Document(file)
        return "\n".join([para.text for para in doc.paragraphs])
    except: return ""

# --- 数据库操作 ---
def get_user_profile(user_id):
    try:
        res = supabase.table("study_profile").select("*").eq("user_id", user_id).execute()
        if not res.data:
            supabase.table("study_profile").insert({"user_id": user_id}).execute()
            return {}
        return res.data[0]
    except: return {}

def get_subjects():
    return supabase.table("subjects").select("*").execute().data

def get_chapters(sid, uid):
    return supabase.table("chapters").select("*").eq("subject_id", sid).eq("user_id", uid).execute().data

def create_chapter(sid, title, uid):
    supabase.table("chapters").insert({"subject_id": sid, "title": title, "user_id": uid}).execute()

def save_material_track_a(cid, content, title, uid):
    supabase.table("materials").insert({"chapter_id": cid, "content": content, "source_type": "textbook", "title": title, "user_id": uid}).execute()

def save_questions_batch(q_list, cid, uid):
    data = [{"chapter_id": cid, "user_id": uid, "type": "single", "content": q['question'], "options": q['options'], "correct_answer": q['answer'], "explanation": q.get('explanation', ''), "origin": "extraction"} for q in q_list]
    supabase.table("question_bank").insert(data).execute()

# =========================================================
# 3. 导航与仪表盘
# =========================================================
if 'user_id' not in st.session_state:
    st.session_state.user_id = "test_user_001" # 生产环境请接 Auth

user_id = st.session_state.user_id
profile = get_user_profile(user_id)

with st.sidebar:
    st.title("🥝 备考中心")
    
# --- 1. AI 大脑设置 (最终完整版：全动态+全记忆) ---
    
    # A. 准备服务商列表
    provider_options = ["Gemini (官方直连)", "DeepSeek (官方直连)", "OpenRouter (聚合平台)"]
    
    # B. 读取数据库里的旧设置 (用于记忆回显)
    # 确保 profile 和 user_settings 已定义
    user_settings = profile.get('settings') or {}
    saved_provider = user_settings.get('last_provider')
    saved_model = user_settings.get('last_used_model')
    
    # C. 计算服务商的默认 Index (记忆功能)
    provider_index = 0
    # 模糊匹配，防止因为选项文字微调导致匹配失败
    for i, opt in enumerate(provider_options):
        if saved_provider and saved_provider.split(" ")[0] in opt:
            provider_index = i
            break
    
    # D. 渲染服务商选择框 (绑定 on_change=save_ai_settings)
    ai_provider = st.selectbox(
        "🧠 AI 大脑", 
        provider_options,
        index=provider_index,
        key="ai_provider_select", # 绑定 Key 用于回调
        on_change=save_ai_settings # 🔥 切换服务商时自动保存
    )
    st.session_state.selected_provider = ai_provider
    
    target_model_id = None
    
    # === 分支 A: Google Gemini ===
    if "Gemini" in ai_provider:
        g_key = st.secrets["GOOGLE_API_KEY"]
        
        # 1. 联网获取
        with st.spinner("同步 Google 模型库..."):
            g_models = fetch_google_models(g_key)
        
        # 2. 保底列表
        g_backups = ["gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro"]
        final_g_opts = g_models if g_models else g_backups
        
        # 3. 计算记忆 Index
        g_idx = 0
        if saved_model in final_g_opts: 
            g_idx = final_g_opts.index(saved_model)
        
        # 4. 渲染选择框
        target_model_id = st.selectbox(
            "🔌 选择 Gemini 版本", 
            final_g_opts,
            index=g_idx,
            key="google_model_select",
            on_change=save_ai_settings
        )
        st.session_state.google_model_id = target_model_id

    # === 分支 B: DeepSeek ===
    elif "DeepSeek" in ai_provider:
        # DeepSeek 官方目前主要就是这两个
        d_opts = ["deepseek-chat", "deepseek-reasoner"]
        
        # 计算记忆 Index
        d_idx = 0
        if saved_model in d_opts: 
            d_idx = d_opts.index(saved_model)
        
        target_model_id = st.selectbox(
            "🔌 选择 DeepSeek 版本", 
            d_opts,
            index=d_idx,
            key="deepseek_model_select",
            on_change=save_ai_settings,
            help="Chat (V3) 速度快，Reasoner (R1) 逻辑强"
        )
        st.session_state.deepseek_model_id = target_model_id

    # === 分支 C: OpenRouter ===
    elif "OpenRouter" in ai_provider:
        or_key = st.secrets.get("openrouter", {}).get("api_key")
        
        # 1. 联网获取
        all_models = fetch_openrouter_models(or_key)
        
        if not all_models:
            st.caption("⚠️ 离线模式 (无法连接 OpenRouter)")
            final_ids = ["google/gemini-2.0-flash-exp:free", "deepseek/deepseek-r1:free"]
        else:
            # 2. 筛选逻辑
            filter_type = st.radio("筛选", ["🤑 免费", "🌎 全部"], horizontal=True)
            
            if "免费" in filter_type:
                filtered_models = [m for m in all_models if m['is_free']]
            else:
                filtered_models = all_models
            
            final_ids = [m['id'] for m in filtered_models]
            if not final_ids: final_ids = [m['id'] for m in all_models]

        # 3. 计算记忆 Index
        or_idx = 0
        if saved_model in final_ids:
            or_idx = final_ids.index(saved_model)
        
        # 4. 渲染选择框
        target_model_id = st.selectbox(
            "🔌 选择 OpenRouter 模型",
            final_ids,
            index=or_idx,
            key="openrouter_model_select",
            on_change=save_ai_settings
        )
        st.session_state.openrouter_model_id = target_model_id

    st.divider()

    # --- 2. 导航菜单 ---
    menu = st.radio(
        "导航", 
        ["🏠 仪表盘", "📚 资料库 (双轨录入)", "📝 章节特训 (刷题)", "⚔️ 全真模考", "📊 弱项分析", "❌ 错题本", "⚙️ 设置中心"], 
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # --- 3. 倒计时 (跨年修正版) ---
    if profile.get('exam_date'):
        try:
            target_date = datetime.datetime.strptime(profile['exam_date'], '%Y-%m-%d').date()
            today = datetime.date.today()
            
            if target_date < today:
                next_year = today.year + 1
                target_date = datetime.date(next_year, 9, 6)
                days = (target_date - today).days
                st.metric("⏳ 备战明年", f"{days} 天", delta=f"{next_year}赛季", delta_color="normal")
            else:
                days = (target_date - today).days
                if days <= 30:
                    st.metric("⏳ 距离考试", f"{days} 天", delta="冲刺阶段", delta_color="inverse")
                else:
                    st.metric("⏳ 距离考试", f"{days} 天")
        except: 
            pass

# === 🏠 仪表盘 ===
if menu == "🏠 仪表盘":
    # 1. 欢迎语与智能倒计时
    exam_date_str = profile.get('exam_date')
    today = datetime.date.today()
    days_left = 0
    is_next_year = False
    
    if exam_date_str:
        target_date = datetime.datetime.strptime(exam_date_str, '%Y-%m-%d').date()
        
        # 如果日期已过 (比如现在是12月，目标是9月)
        if target_date < today:
            # 自动切换到明年9月 (暂定)
            target_date = datetime.date(today.year + 1, 9, 6)
            is_next_year = True
            
        days_left = (target_date - today).days
    
    # 动态文案
    if is_next_year:
        title_html = f"### 🍂 2025考季已过，备战 <span style='color:#00C090'>2026</span>！还剩 <span style='color:#ff4b4b; font-size:1.2em'>{days_left}</span> 天"
        msg = "种一棵树最好的时间是十年前，其次是现在。明年必过！"
    else:
        title_html = f"### 🌞 早安，距离上岸还有 <span style='color:#ff4b4b; font-size:1.2em'>{days_left}</span> 天"
        msg = "现在的从容，就是考场上的噩梦。" if days_left > 100 else "稳住！你背的每一个分录，都是救命稻草！"

    st.markdown(title_html, unsafe_allow_html=True)
    st.info(f"👨‍🏫 **班主任说：** {msg}")

    # 2. 核心数据 Bento Grid (Bootstrap 风格)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="card">
            <i class="bi bi-collection-fill stat-icon"></i>
            <div class="stat-title">累计刷题</div>
            <div class="stat-value">{profile.get('total_questions_done', 0)}</div>
            <div style="color:#00C090; font-size:0.8rem; margin-top:5px;">
                <i class="bi bi-arrow-up-circle"></i> 持续进步中
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        # 正确率计算 (同前)
        acc = "0%"
        # ... (保留你之前的正确率计算逻辑) ...
        
        st.markdown(f"""
        <div class="card">
            <i class="bi bi-bullseye stat-icon"></i>
            <div class="stat-title">正确率</div>
            <div class="stat-value">{acc}</div>
            <div class="progress" style="height: 6px; margin-top:10px; background-color:#eee; border-radius:3px;">
                <div style="width: {acc}; height: 100%; background-color: #00C090; border-radius: 3px;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="card">
            <i class="bi bi-fire stat-icon" style="color: #FF7043;"></i>
            <div class="stat-title">连续打卡</div>
            <div class="stat-value">{profile.get('study_streak', 1)} <span style="font-size:1rem">天</span></div>
            <div style="color:#888; font-size:0.8rem; margin-top:5px;">
                <i class="bi bi-check-circle-fill" style="color:#00C090"></i> 今日已打卡
            </div>
        </div>
        """, unsafe_allow_html=True)

# === ⚙️ 设置中心 ===
elif menu == "⚙️ 设置中心":
    st.title("⚙️ 偏好设置")
    if st.button("🤖 联网自动同步考情"):
        with st.spinner("正在检索 2025 考纲..."):
            time.sleep(1)
            supabase.table("study_profile").update({"exam_date": "2025-09-06"}).eq("user_id", user_id).execute()
            st.success("已更新考试日期：2025-09-06")
            st.rerun()
            
    cur_date = datetime.date(2025,9,6)
    if profile.get('exam_date'): cur_date = datetime.datetime.strptime(profile['exam_date'], '%Y-%m-%d').date()
    new_d = st.date_input("手动设置日期", cur_date)
    if new_d != cur_date:
        supabase.table("study_profile").update({"exam_date": str(new_d)}).eq("user_id", user_id).execute()
        st.rerun()

# === 📚 资料库 (双轨录入) ===
elif menu == "📚 资料库 (双轨录入)":
    st.title("📂 资料上传中心")
    
    # 1. 选章节
    subjects = get_subjects()
    if not subjects: st.stop()
    c1, c2, c3 = st.columns([1,1,1])
    with c1: 
        sel_sub = st.selectbox("科目", [s['name'] for s in subjects])
        sel_sid = next(s['id'] for s in subjects if s['name'] == sel_sub)
    with c2:
        chaps = get_chapters(sel_sid, user_id)
        sel_chap = st.selectbox("章节", ["➕ 新建章节..."] + [c['title'] for c in chaps])
    with c3:
        if sel_chap == "➕ 新建章节...":
            new_c = st.text_input("新章节名")
            if st.button("创建") and new_c:
                create_chapter(sel_sid, new_c, user_id)
                st.rerun()
    
    # 2. 上传逻辑
    if sel_chap != "➕ 新建章节..." and chaps:
        cid = next(c['id'] for c in chaps if c['title'] == sel_chap)
        t1, t2 = st.tabs(["📖 轨道A: 教材生成", "📑 轨道B: 真题提取"])
        
        with t1:
            up_a = st.file_uploader("上传教材 (PDF/Word)", type=['pdf','docx'], key='a')
            if st.button("📥 保存教材") and up_a:
                with st.spinner("识别中..."):
                    txt = extract_text_from_pdf(up_a) if up_a.name.endswith('.pdf') else extract_text_from_docx(up_a)
                    if len(txt)>50: 
                        save_material_track_a(cid, txt, up_a.name, user_id)
                        st.success("已入库")
        
        with t2:
            up_b = st.file_uploader("上传真题 (PDF/Word)", type=['pdf','docx'], key='b')
            is_pdf = up_b and up_b.name.endswith('.pdf')
            
            if is_pdf:
                c_p1, c_p2 = st.columns(2)
                q_s = c_p1.number_input("题目开始页", 1, value=1)
                q_e = c_p2.number_input("题目结束页", 1, value=10)
                sep_ans = st.checkbox("答案在文档末尾")
                if sep_ans:
                    c_p3, c_p4 = st.columns(2)
                    a_s = c_p3.number_input("答案开始页", 1, value=1)
                    a_e = c_p4.number_input("答案结束页", 1, value=10)
            
            if st.button("🔍 提取题目") and up_b:
                with st.spinner("AI 提取中..."):
                    raw = ""
                    if is_pdf:
                        up_b.seek(0)
                        raw = extract_text_from_pdf(up_b, q_s, q_e)
                        if sep_ans: 
                            up_b.seek(0)
                            raw += "\n【答案区】\n" + extract_text_from_pdf(up_b, a_s, a_e)
                    else:
                        raw = extract_text_from_docx(up_b)
                    
                    prompt = f"提取会计题目。内容：{raw[:15000]}。要求返回纯JSON列表：[{{'question':'..','options':['A..','B..'],'answer':'A','explanation':'..'}}]。"
                    res = call_gemini(prompt)
                    if res and 'candidates' in res:
                        try:
                            clean = res['candidates'][0]['content']['parts'][0]['text'].replace("```json","").replace("```","").strip()
                            st.session_state.extracted = json.loads(clean)
                        except: st.error("AI 格式错误")
            
            if 'extracted' in st.session_state:
                st.dataframe(pd.DataFrame(st.session_state.extracted))
                if st.button("💾 确认入库"):
                    save_questions_batch(st.session_state.extracted, cid, user_id)
                    st.success("入库成功")
                    del st.session_state.extracted
# =========================================================
# 📝 章节特训 (核心交互 + AI追问功能)
# =========================================================
elif menu == "📝 章节特训 (刷题)":
    st.title("📝 章节突破")
    
    # --- 1. 计时器 (悬浮) ---
    if 'q_timer' not in st.session_state: st.session_state.q_timer = time.time()
    
    if st.session_state.get('quiz_active'):
        el = int(time.time() - st.session_state.q_timer)
        st.markdown(f"<div class='timer-box'>⏱️ {el//60:02d}:{el%60:02d}</div>", unsafe_allow_html=True)

    # --- 2. 启动区 (未开始状态) ---
    if not st.session_state.get('quiz_active'):
        subjects = get_subjects()
        if subjects:
            c1, c2 = st.columns(2)
            with c1:
                s_name = st.selectbox("科目", [s['name'] for s in subjects])
                sid = next(s['id'] for s in subjects if s['name'] == s_name)
            
            with c2:
                chaps = get_chapters(sid, user_id)
                if chaps:
                    c_title = st.selectbox("章节", [c['title'] for c in chaps])
                    cid = next(c['id'] for c in chaps if c['title'] == c_title)
                    
                    st.markdown("---")
                    
                    # === 📊 进度统计面板 ===
                    try:
                        # 1. 查总库存
                        total_q = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", cid).execute().count
                        
                        # 2. 查已掌握 (去重)
                        # 注意：Supabase client 过滤逻辑
                        done_res = supabase.table("user_answers").select("question_id").eq("user_id", user_id).eq("is_correct", True).execute().data
                        # Python端去重，获取该用户做对过的所有 question_id
                        done_ids = list(set([d['question_id'] for d in done_res]))
                        
                        # 计算本章节已掌握的数量 (交集)
                        # 简单做法：直接用 done_ids 去 filter question_bank，或者由后端统计
                        # 这里为了性能，只在Python端做简单估算（假设 done_ids 覆盖了）
                        # 更严谨的做法是用 SQL 联表，这里简化：
                        mastered_count = 0
                        if total_q > 0:
                            # 查一下 done_ids 里有多少属于当前 chapter
                            # 如果 done_ids 太多，in_ 查询会报错。这里做个防御性编程：
                            if len(done_ids) > 0:
                                mastered_count = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", cid).in_("id", done_ids).execute().count
                            else:
                                mastered_count = 0
                        
                        # 进度条展示
                        prog = mastered_count / total_q if total_q > 0 else 0
                        st.caption(f"📈 本章进度：已掌握 {mastered_count} / 库存 {total_q}")
                        st.progress(prog)
                        
                    except Exception as e:
                        st.error(f"统计加载失败: {e}")
                        total_q = 0
                        done_ids = []

                    st.divider()
                    
                    # === 🎯 练习模式选择 ===
                    mode = st.radio("请选择策略", [
                        "🧹 消灭库存 (只做未掌握的题)", 
                        "🎲 随机巩固 (全库随机抽)", 
                        "🧠 AI 基于教材出新题"
                    ], horizontal=True)
                    
                    if st.button("🚀 开始练习", type="primary", use_container_width=True):
                        st.session_state.quiz_cid = cid
                        st.session_state.q_timer = time.time()
                        
                        # --- 策略 A: 消灭库存 ---
                        if "消灭" in mode:
                            if total_q == 0:
                                st.error("题库为空，请先去资料库录入真题！")
                            elif mastered_count >= total_q:
                                st.balloons()
                                st.success("🎉 太强了！本章库存题目已全部掌握！建议切换到随机模式复习。")
                            else:
                                # 核心逻辑：找出当前章节中，不在 done_ids 里的题目
                                query = supabase.table("question_bank").select("*").eq("chapter_id", cid)
                                if done_ids:
                                    query = query.not_.in_("id", done_ids)
                                
                                qs = query.limit(10).execute().data
                                
                                if qs:
                                    st.session_state.quiz_data = qs
                                    st.session_state.q_idx = 0
                                    st.session_state.quiz_active = True
                                    st.rerun()
                                else:
                                    st.warning("数据加载异常，请重试")

                        # --- 策略 B: 随机巩固 ---
                        elif "随机" in mode:
                            if total_q == 0:
                                st.error("题库为空！")
                            else:
                                # 简单随机：取前50个然后在内存洗牌 (Supabase 随机需RPC)
                                qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).limit(50).execute().data
                                if qs:
                                    import random
                                    random.shuffle(qs)
                                    st.session_state.quiz_data = qs[:10] # 每次练10题
                                    st.session_state.q_idx = 0
                                    st.session_state.quiz_active = True
                                    st.rerun()

                        # --- 策略 C: AI 出题 ---
                        else:
                            mats = supabase.table("materials").select("content").eq("chapter_id", cid).execute().data
                            if mats:
                                txt = "\n".join([m['content'] for m in mats])
                                with st.spinner("AI 正在阅读教材并出题..."):
                                    p = f"基于内容出3道单选题。内容：{txt[:6000]}。格式JSON：[{{'content':'..','options':['A..'],'correct_answer':'A','explanation':'..'}}]。"
                                    r = call_ai_universal(p)
                                    if r:
                                        try:
                                            clean = r.replace("```json","").replace("```","").strip()
                                            d = json.loads(clean)
                                            # 存入库
                                            fmt_qs = [{'question':x['content'], 'options':x['options'], 'answer':x['correct_answer'], 'explanation':x['explanation']} for x in d]
                                            save_questions_batch(fmt_qs, cid, user_id)
                                            # 开始做
                                            st.session_state.quiz_data = d
                                            st.session_state.q_idx = 0
                                            st.session_state.quiz_active = True
                                            st.rerun()
                                        except: st.error("生成失败")
                            else: st.error("该章节无教材资料")
                else:
                    st.warning("暂无章节")

    # --- 3. 做题交互界面 (Active) ---
    if st.session_state.get('quiz_active'):
        idx = st.session_state.q_idx
        total = len(st.session_state.quiz_data)
        
        # 顶部工具栏
        col_prog, col_exit = st.columns([4, 1])
        with col_prog:
            st.progress((idx+1)/total)
            st.caption(f"进度: {idx+1}/{total}")
        with col_exit:
            # 🏁 结束按钮
            if st.button("🏁 结束", help="退出本次练习，返回菜单"):
                st.session_state.quiz_active = False
                st.rerun()

        q = st.session_state.quiz_data[idx]
        
        # 数据兼容
        q_text = q.get('content') or q.get('question')
        q_ans = q.get('correct_answer') or q.get('answer')
        q_exp = q.get('explanation', '暂无解析')
        q_opts = q.get('options', [])
        
        st.markdown(f"""
        <div class='css-card'>
            <h4>Q{idx+1}: {q_text}</h4>
        </div>
        """, unsafe_allow_html=True)
        
        sel = st.radio("请选择答案：", q_opts, key=f"q_{idx}")
        
        sub_key = f"sub_{idx}"
        if sub_key not in st.session_state: st.session_state[sub_key] = False
        
        if st.button("✅ 提交", use_container_width=True) and not st.session_state[sub_key]:
            st.session_state[sub_key] = True
            
        # 判分与保存
        if st.session_state[sub_key]:
            user_val = sel[0] if sel else ""
            
            if user_val == q_ans: 
                st.markdown(f"<div class='success-box'>🎉 回答正确！</div>", unsafe_allow_html=True)
                # 做对时，标记为已掌握 (可选)
                # if q.get('id'): supabase.table("user_answers").update({"is_correct": True}).eq("user_id", user_id).eq("question_id", q['id']).execute()
            else: 
                st.error(f"❌ 遗憾答错。正确答案是：{q_ans}")
                # 存错题 (带防重复逻辑)
                if q.get('id'):
                    try:
                        existing = supabase.table("user_answers").select("id").eq("user_id", user_id).eq("question_id", q['id']).eq("is_correct", False).execute().data
                        if existing:
                            # 更新时间
                            supabase.table("user_answers").update({"created_at": datetime.datetime.now().isoformat()}).eq("id", existing[0]['id']).execute()
                        else:
                            # 新增
                            supabase.table("user_answers").insert({
                                "user_id": user_id, 
                                "question_id": q['id'], 
                                "user_response": user_val, 
                                "is_correct": False
                            }).execute()
                    except: pass
            
            # 解析与AI交互
            st.info(f"💡 **解析：** {q_exp}")
            
            # AI 举例区
            exp_key = f"q_chat_{idx}"
            if exp_key not in st.session_state: st.session_state[exp_key] = []
            
            if st.button("🤔 不理解？AI 举个栗子"):
                with st.spinner("Thinking..."):
                    res = call_ai_universal(f"解释会计题：{q_text}。答案{q_ans}。用生活案例比喻。")
                    if res: st.session_state[exp_key].append({"role":"model", "content":res})
            
            for msg in st.session_state[exp_key]:
                css = "chat-ai" if msg['role'] == "model" else "chat-user"
                st.markdown(f"<div class='{css}'>{msg['content']}</div>", unsafe_allow_html=True)
            
            if st.session_state[exp_key]:
                ask = st.text_input("追问...", key=f"ask_{idx}")
                if st.button("发送", key=f"b_{idx}") and ask:
                    st.session_state[exp_key].append({"role":"user", "content":ask})
                    with st.spinner("..."):
                        r = call_ai_universal(ask, history=st.session_state[exp_key][:-1])
                        st.session_state[exp_key].append({"role":"model", "content":r})
                        st.rerun()

            st.markdown("---")
            if st.button("➡️ 下一题", use_container_width=True):
                if idx < total-1:
                    st.session_state.q_idx += 1
                    st.rerun()
                else:
                    st.balloons()
                    st.success("本轮结束！")
                    if st.button("返回"):
                        st.session_state.quiz_active = False
                        st.rerun()
# =========================================================
# ⚔️ 全真模考
# =========================================================
elif menu == "⚔️ 全真模考":
    st.title("⚔️ 全真模拟")
    if 'exam' not in st.session_state: st.session_state.exam = None
    
    if not st.session_state.exam:
        subjects = get_subjects()
        if subjects:
            sn = st.selectbox("科目", [s['name'] for s in subjects])
            mode = st.radio("类型", ["精简 (5题)", "完整 (20题)"])
            if st.button("🚀 开始考试"):
                sid = next(s['id'] for s in subjects if s['name'] == sn)
                # 简单随机抽题逻辑
                qs = supabase.table("question_bank").select("*").eq("chapter_id", sid).limit(20).execute().data # 实际应跨章节抽
                if qs:
                    st.session_state.exam = {"qs": qs[:5] if "精简" in mode else qs, "start": time.time(), "ans": {}}
                    st.rerun()
                else: st.error("题库题目不足")
    else:
        # 考试进行中
        qs = st.session_state.exam['qs']
        el = int(time.time() - st.session_state.exam['start'])
        st.markdown(f"<div class='timer-box'>⏳ 已用 {el//60}:{el%60:02d}</div>", unsafe_allow_html=True)
        
        for i, q in enumerate(qs):
            st.markdown(f"**{i+1}. {q['content']}**")
            st.session_state.exam['ans'][i] = st.radio("选", q['options'], key=f"e_{i}")
            st.divider()
        
        if st.button("交卷"):
            score = 0
            for i, q in enumerate(qs):
                if st.session_state.exam['ans'][i][0] == q['correct_answer']: score += 10
            st.balloons()
            st.success(f"得分：{score}")
            st.session_state.exam = None

# =========================================================
# 📊 弱项分析 & ❌ 错题本
# =========================================================
elif menu == "📊 弱项分析":
    st.title("📊 数据分析")
    ans = supabase.table("user_answers").select("*").eq("user_id", user_id).execute().data
    if ans:
        df = pd.DataFrame(ans)
        fig = px.pie(df, names='is_correct', title="正确率", color_discrete_sequence=['#00C090', '#FF7043'])
        st.plotly_chart(fig)
        if st.button("生成 AI 建议"):
            with st.spinner("AI 分析中..."):
                r = call_gemini(f"用户做题记录：{len(df)}题，错{len(df[df['is_correct']==False])}题。请给出备考建议。")
                if r: st.info(r['candidates'][0]['content']['parts'][0]['text'])
    else: st.info("暂无数据")

elif menu == "❌ 错题本":
    st.title("❌ 错题集 & 智能私教")
    
    # 1. 获取所有错题 (按时间倒序)
    try:
        errs = supabase.table("user_answers").select("*, question_bank(*)").eq("user_id", user_id).eq("is_correct", False).order("created_at", desc=True).execute().data
    except Exception as e:
        st.error(f"数据加载失败: {e}")
        errs = []
    
    if not errs:
        st.markdown("""
        <div style="text-align:center; padding:40px; color:#888;">
            <h3>🎉 太棒了！目前没有错题</h3>
            <p>去刷几道新题挑战一下吧！</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # --- 🔥 核心去重逻辑 (防止报错的关键) ---
        unique_mistakes = []
        seen_qids = set()
        
        for e in errs:
            # 确保数据完整
            if not e.get('question_bank'): continue
            
            qid = e['question_id']
            # 只有当这个题目ID第一次出现时才显示 (保留最近的一条记录)
            if qid not in seen_qids:
                unique_mistakes.append(e)
                seen_qids.add(qid)
        
        st.info(f"当前共有 {len(unique_mistakes)} 道错题待复习 (已自动合并重复记录)")
        
        # 2. 循环渲染
        for i, e in enumerate(unique_mistakes):
            q = e['question_bank']
            
            # 使用 record_id 作为唯一 Key，配合去重逻辑，确保绝对不报错
            rec_id = e['id']
            q_id = q['id']
            
            # 获取历史对话
            db_chat_history = e.get('ai_chat_history') or []
            
            # 卡片展示
            with st.expander(f"🔴 {q['content'][:30]}... (点击展开)"):
                st.markdown(f"### 📄 题目：\n{q['content']}")
                st.divider() # 加条分割线更清晰
                # --- 🎨 选项美化开始 ---
                if q.get('options') and isinstance(q['options'], list):
                    st.write("**选项：**")
                    for opt in q['options']:
                        # 使用 HTML/CSS 渲染漂亮的选项卡片
                        st.markdown(f"""
                        <div class="list-group-item">
                            <i class="bi bi-circle"></i> {opt}
                        </div>
                            {opt}
                        </div>
                        """, unsafe_allow_html=True)
                # --- 🎨 选项美化结束 ---
                
                c1, c2 = st.columns(2)
                c1.error(f"你的错选：{e['user_response']}")
                c2.success(f"正确答案：{q['correct_answer']}")
                
                st.info(f"💡 **标准解析：** {q['explanation']}")
                
                st.divider()
                
                # --- 功能按钮区 ---
                col_ask, col_clear, col_del = st.columns([1.2, 1, 1])
                
                # 按钮 1: AI 举例 (带 Key 防止冲突)
                # 逻辑：如果没有历史，显示"举例子"；如果有历史，显示"继续追问"的提示
                btn_label = "🤔 我不理解 (AI举例)" if not db_chat_history else "✨ 继续追问 AI"
                
                # 仅当没有历史记录时，这个按钮触发初始化举例
                if not db_chat_history:
                    if col_ask.button(btn_label, key=f"btn_ask_{rec_id}"):
                        prompt = f"用户做错题：'{q['content']}'。答案{q['correct_answer']}。解析{q['explanation']}。请用生活案例通俗解释。"
                        with st.spinner("AI 正在思考..."):
                            res = call_ai_universal(prompt)
                            if res:
                                new_h = [{"role": "model", "content": res}]
                                supabase.table("user_answers").update({"ai_chat_history": new_h}).eq("id", rec_id).execute()
                                st.rerun()
                else:
                    col_ask.caption("👇 在下方对话框继续提问")

                # 按钮 2: 清除记忆
                if db_chat_history:
                    if col_clear.button("🗑️ 清除记忆", key=f"btn_clr_{rec_id}"):
                        supabase.table("user_answers").update({"ai_chat_history": []}).eq("id", rec_id).execute()
                        st.rerun()

                # 按钮 3: 移除错题 (批量移除该题目的所有记录)
                if col_del.button("✅ 已掌握", key=f"btn_rm_{rec_id}"):
                    # 🔥 关键：根据 question_id 把所有重复的错误记录都标记为正确，防止旧记录复活
                    supabase.table("user_answers").update({"is_correct": True}).eq("user_id", user_id).eq("question_id", q_id).execute()
                    st.toast("已彻底移出！")
                    time.sleep(0.5)
                    st.rerun()

                # --- 聊天流展示 ---
                if db_chat_history:
                    st.markdown("---")
                    st.caption("🤖 AI 私教对话记录")
                    for msg in db_chat_history:
                        css = "chat-ai" if msg['role'] == "model" else "chat-user"
                        prefix = "🤖 AI" if msg['role'] == "model" else "👤 我"
                        st.markdown(f"<div class='{css}'><b>{prefix}:</b><br>{msg['content']}</div>", unsafe_allow_html=True)
                    
                    # 追问输入框 (使用 Form 避免刷新重置)
                    with st.form(key=f"form_chat_{rec_id}"):
                        user_input = st.text_input("继续追问...", placeholder="例如：那如果是反过来呢？")
                        if st.form_submit_button("发送 ⬆️"):
                            if user_input:
                                # 构建新历史
                                temp_history = db_chat_history + [{"role": "user", "content": user_input}]
                                
                                with st.spinner("AI 正在回复..."):
                                    ai_reply = call_ai_universal(user_input, history=db_chat_history)
                                    if ai_reply:
                                        final_history = temp_history + [{"role": "model", "content": ai_reply}]
                                        supabase.table("user_answers").update({"ai_chat_history": final_history}).eq("id", rec_id).execute()
                                        st.rerun()











