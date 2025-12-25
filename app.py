import streamlit as st
import requests
import json
import datetime
import pandas as pd
import pdfplumber
import time
import docx
import random
from supabase import create_client
import plotly.express as px
from openai import OpenAI
import streamlit.components.v1 as components
import os
import openpyxl

# ==============================================================================
# 1. 全局配置与“奶油绿便当盒”风格还原 (CSS)
# ==============================================================================
st.set_page_config(page_title="中级会计 AI 私教 Pro (Ultimate)", page_icon="🥝", layout="wide")

st.markdown("""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
<style>
    /* === 基础设定：还原 V2 的暖色调奶油白背景 === */
    .stApp {
        background-color: #F9F9F0; /* 暖色奶油白 */
        font-family: 'Segoe UI', 'Roboto', sans-serif;
    }
    
    /* === 侧边栏：纯白卡片感 === */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid rgba(0,0,0,0.05);
        box-shadow: 4px 0 15px rgba(0,0,0,0.02);
    }

    /* === 卡片：Bento Grid 风格 (圆角、悬浮、微阴影) === */
    .css-card {
        background-color: #FFFFFF;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        border: 1px solid #F0F0F0; /* 极淡边框 */
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        position: relative;
        overflow: hidden;
    }
    
    .css-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 24px rgba(0, 192, 144, 0.15); /* 绿色柔光 */
        border-color: #00C090;
    }

    /* === 统计数字 === */
    .stat-title {
        font-size: 0.85rem; color: #888; text-transform: uppercase; letter-spacing: 1px; font-weight: 700;
    }
    .stat-value {
        font-size: 2.2rem; font-weight: 800; color: #2C3E50; letter-spacing: -1px;
    }
    .stat-icon {
        position: absolute; right: 20px; top: 20px; font-size: 2rem; color: rgba(0,192,144, 0.1);
    }

    /* === 按钮：高饱和度绿色渐变 === */
    .stButton>button {
        background: linear-gradient(135deg, #00C090 0%, #00a87e 100%);
        color: white; border: none; border-radius: 12px; height: 48px; font-weight: 600;
        box-shadow: 0 4px 10px rgba(0, 192, 144, 0.2); transition: all 0.3s ease; padding: 0 25px;
    }
    .stButton>button:hover {
        transform: translateY(-2px); box-shadow: 0 6px 15px rgba(0, 192, 144, 0.4); filter: brightness(1.05); color: white;
    }
    .stButton>button:active { transform: translateY(1px); }

    /* === 选项列表美化 === */
    .option-item {
        background: #fff; border: 1px solid #f0f0f0; padding: 12px 15px; border-radius: 10px; margin-bottom: 8px;
        border-left: 4px solid #e0e0e0; transition: all 0.2s; color: #495057;
    }
    .option-item:hover { border-left-color: #00C090; background-color: #fcfdfc; box-shadow: 0 2px 5px rgba(0,0,0,0.03); }

    /* === 聊天气泡 === */
    .chat-user {
        background-color: #E3F2FD; padding: 12px 18px; border-radius: 15px 15px 0 15px;
        margin: 10px 0 10px auto; max-width: 85%; color: #1565C0; box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .chat-ai {
        background-color: #FFFFFF; padding: 12px 18px; border-radius: 15px 15px 15px 0;
        margin: 10px auto 10px 0; max-width: 85%; border-left: 4px solid #00C090; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    
    /* === 成功/警告框 === */
    .success-box { padding: 15px; background: #E8F5E9; border-radius: 10px; color: #2E7D32; border: 1px solid #C8E6C9; margin-bottom: 10px;}
    .warn-box { padding: 15px; background: #FFF8E1; border-radius: 10px; color: #F57F17; border: 1px solid #FFE082; margin-bottom: 10px;}

    /* 隐藏 Streamlit 默认 Header */
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. 数据库连接与配置
# ==============================================================================
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
    
    # 代理配置 (如果 Secrets 里有)
    if "env" in st.secrets:
        os.environ["http_proxy"] = st.secrets["env"]["http_proxy"]
        os.environ["https_proxy"] = st.secrets["env"]["https_proxy"]
except:
    st.error("🔒 Secrets 配置丢失！请检查 .streamlit/secrets.toml 文件。")
    st.stop()

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# 用户身份模拟 (生产环境需对接 st.login)
if 'user_id' not in st.session_state:
    st.session_state.user_id = "test_user_001"
user_id = st.session_state.user_id

# ==============================================================================
# 3. 核心功能函数 (AI / DB / File)
# ==============================================================================

# --- 数据库 Helper 函数 ---
def get_user_profile(uid):
    try:
        res = supabase.table("study_profile").select("*").eq("user_id", uid).execute()
        if not res.data:
            supabase.table("study_profile").insert({"user_id": uid}).execute()
            return {}
        return res.data[0]
    except: return {}

def update_settings(uid, settings_dict):
    """更新用户设置"""
    try:
        curr = get_user_profile(uid).get('settings') or {}
        curr.update(settings_dict)
        supabase.table("study_profile").update({"settings": curr}).eq("user_id", uid).execute()
    except: pass

def save_ai_pref():
    """回调：保存模型选择"""
    p = st.session_state.get('ai_provider_select')
    m = None
    if "OpenRouter" in str(p): m = st.session_state.get('or_model_select')
    elif "DeepSeek" in str(p): m = st.session_state.get('ds_model_select')
    elif "Gemini" in str(p): m = st.session_state.get('gl_model_select')
    elif "Glama" in str(p): m = st.session_state.get('glama_model_id')
    if p: update_settings(user_id, {"last_provider": p, "last_used_model": m})

# --- AI 调用 (通用版 + 动态超时) ---
# --- AI 调用 (通用版：支持模型覆盖 + 超时豁免) ---
# --- AI 调用 (通用版：修复模型混淆 Bug + 动态超时) ---
# --- AI 调用 (通用版：支持 Google / DeepSeek / OpenRouter / Glama) ---
def call_ai_universal(prompt, history=[], model_override=None, timeout_override=None):
    """
    timeout_override: 如果传入整数(秒)，将无视用户的全局设置，强制使用该时间。
    """
    # 1. 确定超时时间
    if timeout_override is not None:
        current_timeout = timeout_override
    else:
        profile = get_user_profile(st.session_state.get('user_id'))
        settings = profile.get('settings') or {}
        current_timeout = settings.get('ai_timeout', 60)

    # 2. 确定当前通道与模型
    provider = st.session_state.get('selected_provider', 'Gemini')
    
    target_model = None
    if model_override:
        target_model = model_override
    elif "Gemini" in provider:
        target_model = st.session_state.get('google_model_id', 'gemini-1.5-flash')
    elif "DeepSeek" in provider:
        target_model = st.session_state.get('deepseek_model_id', 'deepseek-chat')
    elif "OpenRouter" in provider:
        target_model = st.session_state.get('openrouter_model_id', 'google/gemini-2.0-flash-exp:free')
    elif "Glama" in provider:  # <--- 新增 Glama
        target_model = st.session_state.get('glama_model_id', 'glama-model') # 默认模型ID
    
    if not target_model: target_model = "gemini-1.5-flash"
    
    try:
        # A. Google Gemini 官方协议
        if "Gemini" in provider and not model_override:
            # ... (保持原有的 Gemini 代码不变) ...
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={API_KEY}"
            headers = {'Content-Type': 'application/json'}
            contents = []
            for h in history:
                role = "user" if h['role'] == 'user' else "model"
                contents.append({"role": role, "parts": [{"text": h['content']}]})
            contents.append({"role": "user", "parts": [{"text": prompt}]})
            
            resp = requests.post(url, headers=headers, json={"contents": contents}, timeout=current_timeout)
            if resp.status_code == 200:
                return resp.json()['candidates'][0]['content']['parts'][0]['text']
            return f"Gemini Error {resp.status_code}: {resp.text}"

        # B. OpenAI 兼容协议 (DeepSeek / OpenRouter / Glama)
        else:
            client = None
            
            # 1. OpenRouter (Gemini Override 拆书专用)
            if model_override and "gemini" in model_override and "openrouter" in st.secrets:
                 client = OpenAI(api_key=st.secrets["openrouter"]["api_key"], base_url=st.secrets["openrouter"]["base_url"])
            
            # 2. DeepSeek
            elif "DeepSeek" in provider:
                if "deepseek" in st.secrets:
                    client = OpenAI(api_key=st.secrets["deepseek"]["api_key"], base_url=st.secrets["deepseek"]["base_url"])
                else: return "❌ DeepSeek Secrets 未配置"
            
            # 3. OpenRouter
            elif "OpenRouter" in provider:
                if "openrouter" in st.secrets:
                    client = OpenAI(api_key=st.secrets["openrouter"]["api_key"], base_url=st.secrets["openrouter"]["base_url"])
                else: return "❌ OpenRouter Secrets 未配置"
            
            # 4. Glama (新增) <--- 新增逻辑
            elif "Glama" in provider:
                if "glama" in st.secrets:
                    client = OpenAI(
                        api_key=st.secrets["glama"]["api_key"], 
                        base_url=st.secrets["glama"]["base_url"]
                    )
                else: return "❌ Glama Secrets 未配置 (请在 .streamlit/secrets.toml 中添加 [glama])"
            
            if not client: return "AI Client 初始化失败"

            messages = [{"role": "system", "content": "你是一位资深会计讲师。回答请使用 Markdown 格式。"}]
            for h in history:
                role = "assistant" if h['role'] == "model" else h['role']
                messages.append({"role": role, "content": h['content']})
            messages.append({"role": "user", "content": prompt})

            resp = client.chat.completions.create(
                model=target_model, 
                messages=messages, 
                temperature=0.7,
                timeout=current_timeout
            )
            return resp.choices[0].message.content

    except Exception as e:
        return f"❌ 失败: AI 处理超时或中断 (当前限制 {current_timeout}s): {e}"



# --- 新增：主观题 AI 评分函数 ---
def ai_grade_subjective(user_ans, std_ans, question_content):
    """
    专门用于主观题评分
    返回: {'score': 0-100, 'feedback': '...'}
    """
    if not user_ans or len(user_ans.strip()) < 2:
        return {'score': 0, 'feedback': '未检测到有效作答。'}
        
    prompt = f"""
    【角色】你是一位严谨的会计阅卷老师。
    【任务】请对考生的主观题答案进行评分。
    
    【题目】
    {question_content}
    
    【标准答案】
    {std_ans}
    
    【考生答案】
    {user_ans}
    
    【评分标准】
    1. 满分 100 分。
    2. 核心会计分录、计算结果、关键术语正确即可得分，不纠结文字表述差异。
    3. 如果分录借贷方向反了，直接 0 分。
    4. 如果金额错误但逻辑正确，给 30-50% 分数。
    
    请以纯 JSON 格式返回：
    {{
        "score": 85,
        "feedback": "分录正确，但折旧计算金额有误（应为1000而非1200）。"
    }}
    """
    try:
        # 强制较短超时，避免卡死，评分通常较快
        res = call_ai_universal(prompt, timeout_override=45)
        clean = res.replace("```json","").replace("```","").strip()
        s = clean.find('{'); e = clean.rfind('}')+1
        return json.loads(clean[s:e])
    except Exception as e:
        return {'score': 0, 'feedback': f"AI 阅卷失败: {e}"}


# --- 动态获取模型列表函数 ---
@st.cache_data(ttl=3600)
def fetch_google_models(api_key):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        data = requests.get(url, timeout=10).json()
        return [m['name'].replace("models/", "") for m in data.get('models', []) if "generateContent" in m.get('supportedGenerationMethods', [])]
    except: return []

@st.cache_data(ttl=3600)
def fetch_openrouter_models(api_key):
    try:
        url = "https://openrouter.ai/api/v1/models"
        resp = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get('data', [])
            return sorted([
                {'id': m['id'], 'is_free': (float(m.get('pricing',{}).get('prompt',0))==0) or ':free' in m['id']} 
                for m in data
            ], key=lambda x: x['id'])
        return []
    except: return []

# --- 新增：动态获取 Glama 模型列表 ---
@st.cache_data(ttl=3600)
def fetch_glama_models(api_key, base_url):
    """
    从 Glama 获取可用模型列表
    """
    try:
        # 自动修正 Base URL (防止用户填错)
        # Glama 的标准 Base URL 通常是 https://glama.ai/api/gateway/openai/v1
        # 但获取 models 时只需 base_url + /models
        target_url = base_url.rstrip("/") + "/models"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        resp = requests.get(target_url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json().get('data', [])
            # 提取模型 ID 并排序
            return sorted([m['id'] for m in data], key=lambda x: x)
        else:
            print(f"Glama Fetch Error: {resp.status_code} - {resp.text}")
            return []
    except Exception as e:
        print(f"Glama Fetch Exception: {e}")
        return []

# --- 数据库 CRUD Helper ---
def get_subjects():
    return supabase.table("subjects").select("*").execute().data

def get_books(sid):
    return supabase.table("books").select("*").eq("subject_id", sid).eq("user_id", user_id).execute().data

def get_chapters(book_id):
    return supabase.table("chapters").select("*").eq("book_id", book_id).order("start_page", desc=False).execute().data

def save_material_v3(chapter_id, content, uid):
    supabase.table("materials").insert({
        "chapter_id": chapter_id, "content": content, "user_id": uid
    }).execute()

def save_questions_v3(q_list, chapter_id, uid, origin="ai"):
    data = [{
        "chapter_id": chapter_id,
        "user_id": uid,
        "content": q['question'],
        "options": q['options'],
        "correct_answer": q['answer'],
        "explanation": q.get('explanation', ''),
        "type": "multi" if len(q['answer']) > 1 else "single",
        "origin": origin,
        "batch_source": f"Batch-{int(time.time())}"
    } for q in q_list]
    supabase.table("question_bank").insert(data).execute()

# --- 文件解析 (PDF/Docx) ---
def extract_pdf(file, start=1, end=None):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            total = len(pdf.pages)
            if end is None or end > total: end = total
            # 确保索引不越界
            start = max(1, start)
            end = min(total, end)
            
            for i in range(start-1, end):
                page_obj = pdf.pages[i]
                # 核心修复：有些页提取出来是 None，必须转为空字符串，否则报错
                page_text = page_obj.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        print(f"PDF Err: {e}") # 后台打印错误但不中断
        return ""

def extract_docx(file):
    try:
        doc = docx.Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    except: return ""

# ==============================================================================
# 4. 侧边栏与导航 (修复版：统一菜单名称)
# ==============================================================================
profile = get_user_profile(user_id)
settings = profile.get('settings') or {}

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=50)
    st.markdown("### 会计私教 Pro")
    
    # --- AI 设置 (保持不变) ---
    provs = ["Gemini (官方直连)", "DeepSeek (官方直连)", "OpenRouter (聚合平台)", "Glama (聚合平台)"] # <--- 加在这里
    saved_p = settings.get('last_provider')
    idx_p = 0
    if saved_p:
        for i, x in enumerate(provs):
            if saved_p in x: idx_p = i; break
            
    prov = st.selectbox("🧠 AI 大脑", provs, index=idx_p, key="ai_provider_select", on_change=save_ai_pref)
    st.session_state.selected_provider = prov
    
    saved_m = settings.get('last_used_model')
    
    # 1. Gemini
    if "Gemini" in prov:
        opts = fetch_google_models(st.secrets["GOOGLE_API_KEY"]) or ["gemini-1.5-flash"]
        idx_m = opts.index(saved_m) if saved_m in opts else 0
        st.session_state.google_model_id = st.selectbox("🔌 模型", opts, index=idx_m, key="gl_model_select", on_change=save_ai_pref)
        
    # 2. DeepSeek
    elif "DeepSeek" in prov:
        opts = ["deepseek-chat", "deepseek-reasoner"]
        idx_m = opts.index(saved_m) if saved_m in opts else 0
        st.session_state.deepseek_model_id = st.selectbox("🔌 模型", opts, index=idx_m, key="ds_model_select", on_change=save_ai_pref)
        
    # 3. OpenRouter
    elif "OpenRouter" in prov:
        # (保持原有的 OpenRouter 代码不变...)
        try:
            all_ms = fetch_openrouter_models(st.secrets["openrouter"]["api_key"])
            if not all_ms: final_ids = ["google/gemini-2.0-flash-exp:free"]
            else:
                ft = st.radio("筛选", ["🤑 免费", "🌎 全部"], horizontal=True)
                subset = [m for m in all_ms if m['is_free']] if "免费" in ft else all_ms
                final_ids = [m['id'] for m in subset]
                if not final_ids: final_ids = [m['id'] for m in all_ms]
            idx_m = final_ids.index(saved_m) if saved_m in final_ids else 0
            st.session_state.openrouter_model_id = st.selectbox("🔌 模型", final_ids, index=idx_m, key="or_model_select", on_change=save_ai_pref)
        except: st.error("OpenRouter 连接失败")

    # 4. Glama (自动获取模型版)
# -------------------------------------------------------
    # Glama (稳定版：预设列表 + 手动输入)
    # -------------------------------------------------------
    elif "Glama" in prov:
        st.caption("🚀 已启用 Glama 网关加速")
        
        # 1. 定义 Glama 支持的常用模型 (根据官方文档整理)
        glama_presets = [
            "google-vertex/gemini-2.0-flash-exp",  # 👈 加上 google-vertex/ 前缀
            "google-vertex/gemini-1.5-pro",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "anthropic/claude-3-5-sonnet",
            "meta-llama/llama-3.1-405b-instruct"
        ]
        
        # 2. 提供切换方式：选常用的 vs 手输冷门的
        input_mode = st.radio("模型选择", ["⚡ 常用模型", "⌨️ 手动输入"], horizontal=True, label_visibility="collapsed")
        
        if "常用" in input_mode:
            # 自动定位上次选的模型
            idx_m = glama_presets.index(saved_m) if saved_m in glama_presets else 0
            st.session_state.glama_model_id = st.selectbox(
                "🔌 选择模型", 
                glama_presets, 
                index=idx_m, 
                key="glama_list_select", 
                on_change=save_ai_pref
            )
        else:
            st.session_state.glama_model_id = st.text_input(
                "请输入模型 ID", 
                value=saved_m or "gemini-2.0-flash-exp", 
                placeholder="例如: google-vertex/gemini-1.5-flash",
                key="glama_manual_input",
                on_change=save_ai_pref
            )
            st.caption("提示：可在 Glama 后台查看完整的 Model ID")

    
    # --- 导航菜单 (关键修改点：名字与下方主逻辑严格一致) ---
    # 定义菜单列表
    MENU_OPTIONS = [
        "🏠 仪表盘",
        "📂 智能拆书 & 资料",
        "🎓 AI 课堂 (讲义)",
        "📝 章节特训",    # 注意：这里去掉了"(刷题)"
        "⚔️ 全真模考",
        "📊 弱项分析",
        "❌ 错题本",
        "🛠️ 数据管理 & 补录",
        "⚙️ 设置中心"
    ]
    
    menu = st.radio("功能导航", MENU_OPTIONS, label_visibility="collapsed")
    
    # --- 倒计时 ---
    if profile.get('exam_date'):
        try:
            target = datetime.datetime.strptime(profile['exam_date'], '%Y-%m-%d').date()
            today = datetime.date.today()
            if target < today:
                next_y = today.year + 1
                target = datetime.date(next_y, 9, 6)
                st.metric("⏳ 备战明年", f"{(target-today).days} 天", delta=f"{next_y}赛季")
            else:
                days = (target - today).days
                st.metric("⏳ 距离考试", f"{days} 天", delta="冲刺" if days<30 else "稳住")
        except: pass

# ==============================================================================
# 5. 各页面主逻辑 (V3.0 完整复刻版)
# ==============================================================================

# === 🏠 仪表盘 (Bento Grid 风格) ===
if menu == "🏠 仪表盘":
    # 1. 欢迎语与智能倒计时
    exam_date_str = profile.get('exam_date')
    today = datetime.date.today()
    days_left = 0
    is_next_year = False
    
    if exam_date_str:
        target_date = datetime.datetime.strptime(exam_date_str, '%Y-%m-%d').date()
        if target_date < today:
            target_date = datetime.date(today.year + 1, 9, 6)
            is_next_year = True
        days_left = (target_date - today).days
    
    title_html = f"### 🍂 备战 <span style='color:#00C090'>2026</span>" if is_next_year else f"### 🌞 冲刺 <span style='color:#ff4b4b'>{days_left}</span> 天"
    msg = "种一棵树最好的时间是十年前，其次是现在。" if is_next_year else ("稳住！你背的每一个分录，都是救命稻草！" if days_left < 60 else "现在的从容，就是考场上的噩梦。")

    st.markdown(title_html, unsafe_allow_html=True)
    st.info(f"👨‍🏫 **班主任说：** {msg}")

    # 2. 核心数据 Bento Grid
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="css-card">
            <i class="bi bi-collection-fill stat-icon"></i>
            <div class="stat-title">累计刷题</div>
            <div class="stat-value">{profile.get('total_questions_done', 0)}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="css-card">
            <i class="bi bi-fire stat-icon" style="color:#FF7043"></i>
            <div class="stat-title">连续打卡</div>
            <div class="stat-value">{profile.get('study_streak', 0)} <span style="font-size:1rem">天</span></div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        # 简单计算错题数
        try:
            err_count = supabase.table("user_answers").select("id", count="exact").eq("user_id", user_id).eq("is_correct", False).execute().count
        except: err_count = 0
        st.markdown(f"""
        <div class="css-card">
            <i class="bi bi-bookmark-x-fill stat-icon" style="color:#dc3545"></i>
            <div class="stat-title">待消灭错题</div>
            <div class="stat-value">{err_count}</div>
        </div>
        """, unsafe_allow_html=True)

# =========================================================
# 📂 智能拆书 & 资料 (V7.0 终极完整版：PDF智能拆解 + Excel直导 + 高级管理)
# =========================================================
elif menu == "📂 智能拆书 & 资料":
    st.title("📂 资料库管理 (Pro)")
    
    # --- 局部辅助函数 ---
    def clean_textbook_content(text):
        """简单的文本清洗"""
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            if len(line.strip()) < 3 or line.strip().isdigit(): continue
            cleaned.append(line)
        return "\n".join(cleaned)

    subjects = get_subjects()
    if not subjects: st.error("请先初始化科目数据"); st.stop()
    
    # 1. 顶层选择区
    c1, c2 = st.columns([1, 2])
    with c1:
        s_name = st.selectbox("1. 所属科目", [s['name'] for s in subjects])
        sid = next(s['id'] for s in subjects if s['name'] == s_name)
    with c2:
        books = get_books(sid)
        book_map = {f"{b['title']} (ID:{b['id']})": b['id'] for b in books}
        b_opts = ["➕ 上传新资料...", "---"] + list(book_map.keys())
        sel_book_label = st.selectbox("2. 选择书籍/文件", b_opts)
    
    st.divider()

    # =====================================================
    # 场景 A: 上传新资料 (双模式：PDF智能拆分 / Excel直导)
    # =====================================================
    if "➕ 上传新资料" in sel_book_label:
        st.markdown("#### 📤 第一步：选择导入方式")
        
        # 模式切换
        import_mode = st.radio("请选择资料类型", 
            ["📄 PDF 智能拆分 (适合整本扫描书/习题册)", 
             "📊 Excel/CSV 结构化导入 (适合已整理的讲义/考点/法条)"], 
            horizontal=True
        )

        # -------------------------------------------------
        # 模式 1: PDF 智能拆分 (含 AI 识别、跨页修正)
        # -------------------------------------------------
        if "PDF" in import_mode:
            st.info("💡 AI 将自动分析目录结构，并提取题目或正文。支持主观题识别。")
            
            doc_type = st.radio("文件内容是？", ["📑 习题库 (录入题目)", "📖 纯教材 (AI导学)"], horizontal=True)
            up_file = st.file_uploader("拖入 PDF 文件", type="pdf")
            
            if up_file:
                try:
                    with pdfplumber.open(up_file) as pdf: 
                        total_pages = len(pdf.pages)
                    
                    # 初始化配置状态
                    if 'toc_config' not in st.session_state:
                        st.session_state.toc_config = {
                            "toc_s": 1, "toc_e": min(10, total_pages),
                            "content_s": 1
                        }
                    
                    # --- Step 1: 目录分析配置 ---
                    if 'toc_result' not in st.session_state:
                        c_info = st.container()
                        with c_info:
                            st.info(f"✅ 文件已加载，共 {total_pages} 页。")
                            
                            col_toc, col_body = st.columns(2)
                            with col_toc:
                                st.markdown("**1. 目录范围**")
                                ts = st.number_input("目录开始页", 1, total_pages, st.session_state.toc_config['toc_s'])
                                te = st.number_input("目录结束页", 1, total_pages, st.session_state.toc_config['toc_e'])
                            
                            with col_body:
                                st.markdown("**2. 正文起始**")
                                cs = st.number_input("正文(第一章)开始页", 1, total_pages, st.session_state.toc_config['content_s'])
                            
                            # 答案位置配置
                            ans_mode = "无"
                            as_page = 0
                            if "习题库" in doc_type:
                                st.markdown("**3. 答案位置**")
                                ans_mode = st.radio("答案在哪？", ["🅰️ 紧跟在题目后面", "🅱️ 集中在文件末尾", "🇨 集中在每一章末尾"])
                                if ans_mode == "🅱️ 集中在文件末尾":
                                    as_page = st.number_input("答案区域开始页", 1, total_pages, value=max(1, total_pages-5))

                            # --- Prompt 控制区 (目录) ---
                            st.markdown("---")
                            with st.expander("🛠️ AI 指令微调 (目录分析)", expanded=False):
                                default_toc_prompt = f"""
任务：分析目录文本，推算物理页码。
总页数：{total_pages}。
正文起始偏移：用户称第一章始于第 {cs} 页。

请提取章节名称，并推算每一章在PDF的【物理起始页码】。
要求：
1. 返回纯 JSON 列表。
2. 格式：[{{ "title": "第一章 存货", "start_page": 5, "end_page": 10 }}]
3. 忽略前言、附录。
                                """
                                user_toc_prompt = st.text_area("提示词", value=default_toc_prompt.strip(), height=150)

                            if st.button("🚀 执行目录分析"):
                                with st.spinner("AI 正在阅读目录..."):
                                    up_file.seek(0)
                                    toc_txt = extract_pdf(up_file, ts, te)
                                    full_p = f"{user_toc_prompt}\n\n目录文本：\n{toc_txt[:10000]}"
                                    
                                    res = call_ai_universal(full_p)
                                    
                                    if not res:
                                        st.error("AI 未返回任何内容。")
                                    elif "QuotaFailure" in res:
                                        st.error("⚠️ Google API 调用频繁，请稍候再试。")
                                    else:
                                        try:
                                            clean = res.replace("```json","").replace("```","").strip()
                                            s = clean.find('['); e = clean.rfind(']')+1
                                            data = json.loads(clean[s:e])
                                            
                                            if not isinstance(data, list) or len(data) == 0 or 'title' not in data[0]:
                                                st.error("❌ AI 返回格式异常。")
                                            else:
                                                for row in data:
                                                    row['ans_start_page'] = as_page if "文件末尾" in ans_mode else 0
                                                    row['ans_end_page'] = total_pages if "文件末尾" in ans_mode else 0

                                                st.session_state.toc_result = data
                                                st.session_state.ans_mode_cache = ans_mode
                                                st.rerun()
                                        except Exception as e: 
                                            st.error(f"AI 解析失败: {e}")

                    # --- Step 2: 确认结构 ---
                    if 'toc_result' in st.session_state:
                        st.divider()
                        c_head, c_re = st.columns([4, 1])
                        with c_head: st.markdown("#### 📝 第二步：确认章节结构")
                        with c_re: 
                            if st.button("🔄 重做第一步"):
                                del st.session_state.toc_result
                                st.rerun()

                        cached_ans_mode = st.session_state.get('ans_mode_cache', '无')

                        col_cfg = {
                            "title": "章节名称",
                            "start_page": st.column_config.NumberColumn("题目起始", format="%d"),
                            "end_page": st.column_config.NumberColumn("题目结束", format="%d")
                        }
                        if "文件末尾" in cached_ans_mode:
                            col_cfg["ans_start_page"] = st.column_config.NumberColumn("答案起始", format="%d")
                            col_cfg["ans_end_page"] = st.column_config.NumberColumn("答案结束", format="%d")

                        try:
                            edited_df = st.data_editor(st.session_state.toc_result, column_config=col_cfg, num_rows="dynamic", use_container_width=True)
                        except:
                            del st.session_state.toc_result; st.rerun()
                        
                        # --- Step 3: 提取与入库 (含跨页缓冲与主观题支持) ---
                        if "习题库" in doc_type:
                            st.divider()
                            st.markdown("#### 🧪 第三步：入库配置与测试")
                            
                            st.info("💡 如果题目不全或答案丢失，请增大【跨页缓冲】。")
                            page_buffer = st.slider("📐 跨页缓冲 (自动多读N页)", 0, 5, 1, help="防止答案刚好在下一页被截断。")
                            
                            st.markdown("🛠️ **AI 指令微调 (题目提取)**")
                            
                            # 增强版提示词：支持主观题不拆分 + 合并背景资料
                            default_extract_prompt = """
任务：从文本提取题目和答案。
重点：**解决内容跨页断裂，合并主观题背景资料。**

处理规则：
1. 【计算分析/综合题/主观题】：
   - 务必将“背景资料”与“所有小问的要求”合并，存入 question 字段。
   - 如果资料中途断开，请自动向下文寻找衔接内容。
   - 不要把(1)(2)拆成多条，合并为一道大题。
   - type 设为 subjective。
   - answer 字段必须包含对应的计算过程或分录。

2. 【客观题】：type 设为 single 或 multi。

返回 JSON 示例：
[
  {
    "question": "【计算题】甲公司...(完整背景)... 要求：(1)...",
    "type": "subjective",
    "options": [],
    "answer": "参考解析：(1) ...",
    "explanation": "..."
  }
]
                            """
                            user_extract_prompt = st.text_area("提取提示词", value=default_extract_prompt.strip(), height=250)

                            # 预览功能
                            preview_idx = st.selectbox("选择章节测试", range(len(edited_df)), format_func=lambda x: edited_df[x]['title'])
                            
                            if st.button("🔍 抽取 5 题测试"):
                                row = edited_df[preview_idx]
                                try:
                                    # 提取题目文本
                                    p_s = int(float(row['start_page']))
                                    p_e = min(p_s + 3, int(float(row['end_page'])))
                                    up_file.seek(0)
                                    q_text = extract_pdf(up_file, p_s, p_e)
                                    
                                    # 提取答案文本 (应用 Buffer)
                                    if "文件末尾" in cached_ans_mode:
                                        a_s = int(float(row['ans_start_page']))
                                        # 预览时多读 Buffer + 3 页
                                        a_e = min(a_s + 3 + page_buffer, int(float(row['ans_end_page'])))
                                        
                                        up_file.seek(0)
                                        a_text = extract_pdf(up_file, a_s, a_e)
                                        q_text += f"\n\n====== 答案区域 (缓冲 {page_buffer} 页) ======\n{a_text}"
                                    
                                    full_p = f"{user_extract_prompt}\n\n待提取文本：\n{q_text[:25000]}"
                                    
                                    with st.spinner("AI 正在提取..."):
                                        res = call_ai_universal(full_p)
                                        if "QuotaFailure" in str(res):
                                            st.error("⚠️ API 配额超限。")
                                        elif res:
                                            cln = res.replace("```json","").replace("```","").strip()
                                            s = cln.find('['); e = cln.rfind(']')+1
                                            st.session_state.preview_data = json.loads(cln[s:e])
                                except Exception as e: st.error(f"测试失败: {e}")

                            # 展示结果
                            if st.session_state.get('preview_data'):
                                st.write("##### 👀 识别结果预览")
                                p_df = pd.DataFrame(st.session_state.preview_data)
                                st.dataframe(p_df[['type', 'question', 'answer']], use_container_width=True)
                                
                                # 执行全量
                                if st.button("💾 确认无误，执行全量入库", type="primary"):
                                    progress_bar = st.progress(0)
                                    st_text = st.empty()
                                    
                                    # 1. 建书
                                    b_res = supabase.table("books").insert({
                                        "user_id": user_id, "subject_id": sid, "title": up_file.name.replace(".pdf",""), "total_pages": total_pages
                                    }).execute()
                                    bid = b_res.data[0]['id']
                                    
                                    try:
                                        for i, row in enumerate(edited_df):
                                            st_text.text(f"正在处理：{row['title']}...")
                                            c_s = int(float(row['start_page'])); c_e = int(float(row['end_page']))
                                            
                                            c_res = supabase.table("chapters").insert({
                                                "book_id": bid, "title": row['title'], "start_page": c_s, "end_page": c_e, "user_id": user_id
                                            }).execute()
                                            cid = c_res.data[0]['id']
                                            
                                            # 提取题目文本
                                            up_file.seek(0)
                                            txt = extract_pdf(up_file, c_s, c_e)
                                            
                                            # 提取答案文本 (全量时应用 Buffer)
                                            if "文件末尾" in cached_ans_mode:
                                                a_s = int(float(row['ans_start_page']))
                                                a_e_original = int(float(row['ans_end_page']))
                                                a_e_safe = min(a_e_original + page_buffer, total_pages)
                                                
                                                if a_s > 0:
                                                    up_file.seek(0)
                                                    a_text = extract_pdf(up_file, a_s, a_e_safe)
                                                    txt += f"\n\n====== 答案区域 ======\n{a_text}"
                                            
                                            # 调用 AI
                                            final_p = f"{user_extract_prompt}\n\n文本：\n{txt[:60000]}"
                                            r = call_ai_universal(final_p, timeout_override=300)
                                            
                                            if r and "QuotaFailure" not in str(r):
                                                try:
                                                    cln = r.replace("```json","").replace("```","").strip()
                                                    s = cln.find('['); e = cln.rfind(']')+1
                                                    qs = json.loads(cln[s:e])
                                                    
                                                    db_data = []
                                                    for q in qs:
                                                        q_type = q.get('type', 'single')
                                                        # 自动纠正主观题
                                                        if 'subjective' in q_type or not q.get('options') or len(str(q.get('answer'))) > 10:
                                                            q_type = 'subjective'
                                                        else:
                                                            if len(str(q.get('answer'))) > 1: q_type = 'multi'
                                                        
                                                        db_data.append({
                                                            "chapter_id": cid, "user_id": user_id,
                                                            "content": q['question'],
                                                            "options": q.get('options', []),
                                                            "correct_answer": q.get('answer', ''),
                                                            "explanation": q.get('explanation', ''),
                                                            "type": q_type,
                                                            "origin": "extract",
                                                            "batch_source": "PDF-V7.0"
                                                        })
                                                    if db_data:
                                                        supabase.table("question_bank").insert(db_data).execute()
                                                except: pass
                                            elif "QuotaFailure" in str(r):
                                                st.warning(f"章节 {row['title']} 处理时遇到 API 限流，跳过。")
                                            
                                            progress_bar.progress((i+1)/len(edited_df))
                                        
                                        st.success("🎉 入库完成！")
                                        time.sleep(2); st.rerun()
                                    except Exception as e: st.error(f"出错: {e}")

                        # --- 纯教材保存逻辑 ---
                        elif "纯教材" in doc_type:
                             if st.button("💾 确认保存教材"):
                                try:
                                    b_res = supabase.table("books").insert({
                                        "user_id": user_id, "subject_id": sid, "title": up_file.name.replace(".pdf",""), "total_pages": total_pages
                                    }).execute()
                                    bid = b_res.data[0]['id']
                                    
                                    bar = st.progress(0)
                                    for i, row in enumerate(edited_df):
                                        c_s = int(float(row['start_page']))
                                        c_e = int(float(row['end_page']))
                                        c_res = supabase.table("chapters").insert({
                                            "book_id": bid, "title": row['title'], "start_page": c_s, "end_page": c_e, "user_id": user_id
                                        }).execute()
                                        
                                        up_file.seek(0)
                                        txt = extract_pdf(up_file, c_s, c_e)
                                        save_material_v3(c_res.data[0]['id'], clean_textbook_content(txt), user_id)
                                        bar.progress((i+1)/len(edited_df))
                                    
                                    st.success("教材入库成功！")
                                    time.sleep(1); st.rerun()
                                except Exception as e: st.error(f"失败: {e}")

                except Exception as e: st.error(f"文件处理错误: {e}")

        # -------------------------------------------------
        # 模式 2: Excel 结构化导入 (零 Token / 高质量)
        # -------------------------------------------------
        else:
            st.markdown("#### 📥 Excel 教材导入")
            st.info("💡 适合导入已整理好的笔记、考点汇总、法条大全。**无需消耗 AI Token，内容 100% 准确。**")
            
            # 1. 模版下载
            data_template = [
                {"章节名称": "第一章 总论", "正文内容": "这里填入第一章的所有知识点文本..."},
                {"章节名称": "第二章 存货", "正文内容": "存货的初始计量包括：\n1. 购买价款..."}
            ]
            df_temp = pd.DataFrame(data_template)
            csv = df_temp.to_csv(index=False).encode('utf-8-sig')
            st.download_button("⬇️ 下载导入模版 (.csv)", csv, "教材导入模版.csv", "text/csv")
            
            st.divider()
            
            # 2. 上传处理
            up_excel = st.file_uploader("上传填好的文件", type=["csv", "xlsx"])
            book_name_input = st.text_input("给这份资料起个名字", placeholder="例如：2025中级实务-考点狂背版")
            
            if up_excel and book_name_input:
                if st.button("🚀 立即导入数据库", type="primary"):
                    try:
                        # 读取文件
                        if up_excel.name.endswith('.csv'):
                            df = pd.read_csv(up_excel)
                        else:
                            df = pd.read_excel(up_excel)
                        
                        bar = st.progress(0)
                        
                        # 1. 建书
                        b_res = supabase.table("books").insert({
                            "user_id": user_id, "subject_id": sid, "title": book_name_input, "total_pages": 0
                        }).execute()
                        bid = b_res.data[0]['id']
                        
                        # 2. 循环插入
                        total_rows = len(df)
                        for i, row in df.iterrows():
                            # 兼容不同列名
                            chap_title = str(row.get('章节名称') or row.get('title') or f'第 {i+1} 节').strip()
                            content = str(row.get('正文内容') or row.get('content') or '').strip()
                            
                            if not content: continue
                            
                            # 建章
                            c_res = supabase.table("chapters").insert({
                                "book_id": bid, "title": chap_title, "start_page": 0, "end_page": 0, "user_id": user_id
                            }).execute()
                            cid = c_res.data[0]['id']
                            
                            # 存教材
                            save_material_v3(cid, content, user_id)
                            
                            bar.progress((i+1)/total_rows)
                            
                        st.success(f"🎉 导入成功！已创建书籍：《{book_name_input}》")
                        time.sleep(2)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"导入失败: {e}。\n请确保 Excel 包含【章节名称】和【正文内容】两列。")

    # =====================================================
    # 场景 B: 已有书籍管理 (含科目迁移/重命名/章节管理)
    # =====================================================
    elif books:
        if sel_book_label == "---":
            st.info("👈 请选择一本书籍进行管理")
        else:
            bid = book_map[sel_book_label]
            
            # 获取书籍元数据
            curr_book_info = next((b for b in books if b['id'] == bid), {})
            
            c_tit, c_act = st.columns([5, 1])
            with c_tit: 
                st.markdown(f"### 📘 {curr_book_info.get('title', '未知书籍')}")
            with c_act:
                if st.button("🗑️ 删除本书", type="primary"):
                    try:
                        supabase.table("books").delete().eq("id", bid).execute()
                        st.toast("书籍已删除")
                        time.sleep(1); st.rerun()
                    except: st.error("删除失败")
            
            # --- 🔧 书籍设置 (移动/重命名) ---
            with st.expander("🔧 书籍设置 (修正科目 / 重命名)", expanded=False):
                c_set1, c_set2, c_set3 = st.columns([2, 2, 1])
                
                with c_set1:
                    new_title = st.text_input("📖 书籍名称", value=curr_book_info.get('title', ''))
                
                with c_set2:
                    all_subs = get_subjects()
                    all_sub_names = [s['name'] for s in all_subs]
                    curr_sub_idx = all_sub_names.index(s_name) if s_name in all_sub_names else 0
                    target_sub_name = st.selectbox("🔀 归属科目", all_sub_names, index=curr_sub_idx, help="选错科目了？在此修改。")
                
                with c_set3:
                    st.write("") 
                    st.write("") 
                    if st.button("💾 保存变更"):
                        try:
                            target_sid = next(s['id'] for s in all_subs if s['name'] == target_sub_name)
                            supabase.table("books").update({
                                "title": new_title,
                                "subject_id": target_sid
                            }).eq("id", bid).execute()
                            
                            st.success("✅ 书籍信息已更新！")
                            if target_sid != sid:
                                st.info(f"书籍已迁移至【{target_sub_name}】，请切换科目查看。")
                            time.sleep(2); st.rerun()
                        except Exception as e: st.error(f"修改失败: {e}")

            st.divider()

            # --- 下方章节列表 ---
            chapters = get_chapters(bid)
            if not chapters: st.info("本书暂无章节")
            else:
                for chap in chapters:
                    try: q_cnt = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", chap['id']).execute().count
                    except: q_cnt = 0
                    try: m_cnt = supabase.table("materials").select("id", count="exact").eq("chapter_id", chap['id']).execute().count
                    except: m_cnt = 0
                    
                    with st.expander(f"📑 {chap['title']} (题库: {q_cnt} | 教材: {'✅' if m_cnt else '❌'})"):
                        c_op1, c_op2 = st.columns([1, 5])
                        with c_op1:
                            if st.button("🗑️ 清空", key=f"del_c_{chap['id']}", help="删除该章节所有数据"):
                                supabase.table("materials").delete().eq("chapter_id", chap['id']).execute()
                                supabase.table("question_bank").delete().eq("chapter_id", chap['id']).execute()
                                st.toast("章节数据已清空")
                                time.sleep(1); st.rerun()
                        with c_op2:
                            st.caption(f"页码范围: P{chap['start_page']} - P{chap['end_page']}")

# =========================================================
# 📝 章节特训 (V6.3: 完整逻辑修复版 - 含数据库查询与主观题支持)
# =========================================================
elif menu == "📝 章节特训":
    st.title("📝 章节突破")
    
    # --- 1. JS 实时悬浮计时器 ---
    if st.session_state.get('quiz_active'):
        if 'js_start_time' not in st.session_state:
            st.session_state.js_start_time = int(time.time() * 1000)
        
        components.html(f"""
        <div style='position:fixed;top:60px;right:20px;z-index:9999;background:linear-gradient(45deg, #00C090, #00E6AC);color:white;padding:8px 20px;border-radius:30px;font-family:monospace;font-size:18px;font-weight:bold;box-shadow:0 4px 15px rgba(0,192,144,0.3)'>
            ⏱️ <span id='t'>00:00</span>
        </div>
        <script>
            setInterval(()=>{{
                var d=Math.floor((Date.now()-{st.session_state.js_start_time})/1000);
                var m=Math.floor(d/60).toString().padStart(2,'0');
                var s=(d%60).toString().padStart(2,'0');
                document.getElementById('t').innerText=m+':'+s;
            }},1000)
        </script>
        """, height=0)

    # --- 2. 启动配置区 (未开始状态) ---
    if not st.session_state.get('quiz_active'):
        subjects = get_subjects()
        if subjects:
            # 级联选择器
            c1, c2, c3 = st.columns(3)
            with c1: 
                s_name = st.selectbox("1. 选择科目", [s['name'] for s in subjects])
                sid = next(s['id'] for s in subjects if s['name'] == s_name)
            
            with c2:
                books = get_books(sid)
                if not books:
                    st.warning("该科目下无书籍")
                    bid = None
                else:
                    b_map = {f"{b['title']} (ID:{b['id']})": b['id'] for b in books}
                    sel_b_label = st.selectbox("2. 选择书籍", list(b_map.keys()))
                    bid = b_map[sel_b_label]
            
            with c3:
                cid = None
                if bid:
                    chaps = get_chapters(bid)
                    if not chaps:
                        st.warning("本书无章节")
                    else:
                        c_map = {f"{c['title']} (ID:{c['id']})": c['id'] for c in chaps}
                        sel_c_label = st.selectbox("3. 选择章节", list(c_map.keys()))
                        cid = c_map[sel_c_label]

            # 选中章节后的逻辑
            if cid:
                st.markdown("---")
                
                # === 📊 智能进度看板 ===
                try:
                    q_res = supabase.table("question_bank").select("id").eq("chapter_id", cid).execute().data
                    total_q = len(q_res)
                    
                    mastered_count = 0
                    done_ids = []
                    if total_q > 0:
                        user_correct = supabase.table("user_answers").select("question_id").eq("user_id", user_id).eq("is_correct", True).execute().data
                        chapter_q_ids = set([q['id'] for q in q_res])
                        user_correct_ids = set([a['question_id'] for a in user_correct])
                        mastered_ids = user_correct_ids.intersection(chapter_q_ids)
                        mastered_count = len(mastered_ids)
                        done_ids = list(mastered_ids)
                    
                    prog = mastered_count / total_q if total_q > 0 else 0
                    st.caption(f"📈 掌握进度：{mastered_count} / {total_q} 题")
                    st.progress(prog)
                    
                except:
                    total_q = 0; done_ids = []

                st.divider()
                
                # === 🎯 练习模式选择 ===
                mode = st.radio("练习策略", [
                    "🧹 消灭库存 (只做未掌握的题)", 
                    "🎲 随机巩固 (全库随机抽)", 
                    "🧠 AI 基于教材出新题"
                ], horizontal=True)
                
                if st.button("🚀 开始练习", type="primary", use_container_width=True):
                    # --- 策略 A: 消灭库存 ---
                    if "消灭" in mode:
                        if total_q == 0:
                            st.error("题库为空，请先去【资料库】录入真题！")
                        elif mastered_count == total_q:
                            st.balloons()
                            st.success("🎉 本章题目已全部掌握！")
                        else:
                            # 修复：确保 not_.in_ 参数格式正确
                            qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).not_.in_("id", done_ids).limit(20).execute().data
                            if qs:
                                random.shuffle(qs)
                                st.session_state.quiz_data = qs[:10]
                                st.session_state.q_idx = 0
                                st.session_state.quiz_active = True
                                st.session_state.js_start_time = int(time.time() * 1000)
                                st.rerun()
                            else:
                                st.warning("数据加载异常，请重试")

                    # --- 策略 B: 随机巩固 ---
                    elif "随机" in mode:
                        if total_q == 0:
                            st.error("题库为空")
                        else:
                            qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).limit(50).execute().data
                            if qs:
                                random.shuffle(qs)
                                st.session_state.quiz_data = qs[:10]
                                st.session_state.q_idx = 0
                                st.session_state.quiz_active = True
                                st.session_state.js_start_time = int(time.time() * 1000)
                                st.rerun()
                    
                    # --- 策略 C: AI 出题 ---
                    else:
                        mats = supabase.table("materials").select("content").eq("chapter_id", cid).execute().data
                        if not mats:
                            st.error("该章节没有上传教材资料！请去【资料库】上传 PDF/Word。")
                        else:
                            full_text = "\n".join([m['content'] for m in mats])
                            with st.spinner("🤖 AI 正在研读教材并出题..."):
                                prompt = f"""
                                请基于以下教材内容，生成 3 道选择题（含单选/多选）。
                                教材片段：{full_text[:10000]}
                                必须返回纯 JSON 列表格式：
                                [
                                  {{
                                    "content": "题目描述...",
                                    "options": ["A.选项1", "B.选项2", "C.选项3", "D.选项4"],
                                    "correct_answer": "AB", 
                                    "explanation": "详细解析...",
                                    "type": "multi"
                                  }}
                                ]
                                """
                                res = call_ai_universal(prompt)
                                if res:
                                    try:
                                        clean = res.replace("```json","").replace("```","").strip()
                                        s = clean.find('['); e = clean.rfind(']')+1
                                        d = json.loads(clean[s:e])
                                        
                                        # 存入数据库
                                        db_qs = [{
                                            'chapter_id': cid, 'user_id': user_id,
                                            'type': 'multi' if len(str(x.get('correct_answer','')))>1 else 'single',
                                            'content': x['content'],
                                            'options': x['options'],
                                            'correct_answer': x['correct_answer'],
                                            'explanation': x['explanation'],
                                            'origin': 'ai_gen',
                                            'batch_source': f'AI-{int(time.time())}'
                                        } for x in d]
                                        supabase.table("question_bank").insert(db_qs).execute()
                                        
                                        st.session_state.quiz_data = d
                                        st.session_state.q_idx = 0
                                        st.session_state.quiz_active = True
                                        st.session_state.js_start_time = int(time.time() * 1000)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"AI 生成格式错误: {e}")
        else:
            st.warning("请先去【资料库】初始化科目和上传书籍")

    # --- 3. 做题交互界面 ---
    if st.session_state.get('quiz_active'):
        # === 🛡️ 安全检查：防止状态丢失导致的报错 ===
        if 'q_idx' not in st.session_state or 'quiz_data' not in st.session_state:
            st.session_state.quiz_active = False
            st.rerun()

        idx = st.session_state.q_idx
        data_len = len(st.session_state.quiz_data)
        
        if idx >= data_len:
            st.balloons()
            st.success("🎉 本轮练习完成！")
            if st.button("🔙 返回章节菜单"):
                st.session_state.quiz_active = False
                st.rerun()
        else:
            q = st.session_state.quiz_data[idx]
            
            # 顶部进度
            st.progress((idx + 1) / data_len)
            c_idx, c_end = st.columns([5, 1])
            with c_idx: st.caption(f"当前进度：{idx + 1} / {data_len}")
            with c_end:
                if st.button("🏁 结束"):
                    st.session_state.quiz_active = False
                    st.rerun()

            # 数据解析
            q_text = q.get('content') or q.get('question')
            q_type = q.get('type', 'single') # single, multi, subjective
            q_opts = q.get('options', [])
            std_ans = q.get('correct_answer') or q.get('answer')
            q_exp = q.get('explanation', '暂无解析')

            # 徽章显示
            badges = {
                "single": ("单选题", "#00C090"),
                "multi": ("多选题", "#ff9800"),
                "subjective": ("🧠 主观题", "#9c27b0")
            }
            b_label, b_color = badges.get(q_type, ("未知", "#888"))
            
            st.markdown(f"""
            <div class='css-card'>
                <div style="margin-bottom:10px">
                    <span style='background:{b_color};color:white;padding:2px 8px;border-radius:4px;font-size:12px'>{b_label}</span>
                </div>
                <h4 style="line-height:1.6; white-space: pre-wrap;">{q_text}</h4>
            </div>
            """, unsafe_allow_html=True)
            
            # --- 输入区域 ---
            user_val = ""
            sub_key = f"sub_state_{idx}"
            if sub_key not in st.session_state: st.session_state[sub_key] = False

            # 1. 主观题渲染
            if q_type == 'subjective':
                st.info("📝 请在下方输入你的计算过程或分录：")
                user_val = st.text_area("作答区", height=150, key=f"q_subj_{idx}", disabled=st.session_state[sub_key])
            
            # 2. 客观题渲染
            elif q_type == 'multi':
                st.caption("请选择所有正确选项（多选）：")
                selected = []
                for opt in q_opts:
                    if st.checkbox(opt, key=f"q_{idx}_{opt}", disabled=st.session_state[sub_key]):
                        selected.append(opt[0].upper())
                user_val = "".join(sorted(selected))
            else:
                st.caption("请选择唯一正确选项：")
                sel = st.radio("选项", q_opts, key=f"q_rad_{idx}", disabled=st.session_state[sub_key], label_visibility="collapsed")
                user_val = sel[0].upper() if sel else ""

            # --- 提交按钮 ---
            if st.button("✅ 提交答案", use_container_width=True) and not st.session_state[sub_key]:
                st.session_state[sub_key] = True
                st.rerun()
            
            # --- 判分与反馈 ---
            if st.session_state[sub_key]:
                is_correct_bool = False
                ai_feedback = ""
                
                # A. 主观题：AI 评分
                if q_type == 'subjective':
                    with st.spinner("🤖 AI 阅卷老师正在批改你的答案..."):
                        # 如果还没评过分，就评一次并存Session防止刷新消失
                        grade_key = f"grade_res_{idx}"
                        if grade_key not in st.session_state:
                            grade_res = ai_grade_subjective(user_val, std_ans, q_text)
                            st.session_state[grade_key] = grade_res
                        
                        res = st.session_state[grade_key]
                        score = res.get('score', 0)
                        ai_feedback = res.get('feedback', '')
                        
                        is_correct_bool = (score >= 60)
                        
                        color = "#00C090" if score >= 80 else ("#ff9800" if score >= 60 else "#dc3545")
                        st.markdown(f"""
                        <div style="padding:15px; background:{color}20; border-left:5px solid {color}; border-radius:5px; margin:10px 0;">
                            <h3 style="color:{color}; margin:0">得分：{score} / 100</h3>
                            <p style="margin-top:5px"><b>👩‍🏫 点评：</b>{ai_feedback}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        with st.expander("查看参考答案"):
                            st.code(std_ans, language="markdown")

                # B. 客观题：逻辑匹配
                else:
                    clean_std = str(std_ans).replace(" ","").replace(",","").upper()
                    if user_val == clean_std:
                        st.markdown(f"<div class='success-box'>🎉 回答正确！</div>", unsafe_allow_html=True)
                        is_correct_bool = True
                    else:
                        st.error(f"❌ 遗憾答错。正确答案是：{clean_std}")
                        is_correct_bool = False
                    st.info(f"💡 **解析：** {q_exp}")

                # --- 存库逻辑 (通用) ---
                save_key = f"saved_db_{idx}"
                if save_key not in st.session_state:
                    try:
                         # 构造存库数据，主观题把 score 放入 user_response 或 备注
                         resp_text = user_val
                         if q_type == 'subjective':
                             # 将分数追加到答案文本前，便于后续回顾
                             score_val = st.session_state.get(f"grade_res_{idx}", {}).get('score', 0)
                             resp_text = f"[AI评分:{score_val}] {user_val}"
                         
                         supabase.table("user_answers").insert({
                            "user_id": user_id, 
                            "question_id": q.get('id'), # 注意：AI出题可能没有ID，这里可能报错
                            "user_response": resp_text, 
                            "is_correct": is_correct_bool
                        }).execute()
                         st.session_state[save_key] = True
                    except Exception as e:
                        # 只有当题目有 ID (即已入库) 时才能存做题记录
                        # 纯AI生成的临时题目如果没有ID，则跳过存储
                        pass

            # 下一题
            st.divider()
            if st.button("➡️ 下一题", type="primary", use_container_width=True):
                if idx < data_len - 1:
                    st.session_state.q_idx += 1
                    st.rerun()
                else:
                    st.balloons()
                    st.success("🎉 本轮练习全部完成！")
                    if st.button("返回主菜单"):
                        st.session_state.quiz_active = False
                        st.rerun()


# =========================================================
# ⚔️ 全真模考 (V6.0: 混合题型 + 批量 AI 阅卷)
# =========================================================
elif menu == "⚔️ 全真模考":
    st.title("⚔️ 全真模拟考试")
    
    if 'exam_session' not in st.session_state:
        st.session_state.exam_session = None

    # 1. 配置台 (保持逻辑不变，只展示关键改动)
    if not st.session_state.exam_session:
        # ... (省略历史记录和选择科目代码) ...
        if st.button("🚀 生成试卷"):
             # ... (省略组卷逻辑，假设 final_paper 已生成) ...
             # 确保 final_paper 里包含了 subjective 类型的题
             st.session_state.exam_session = {
                 "paper": final_paper, # List of questions
                 "answers": {}, 
                 "submitted": False,
                 # ... 其他字段
             }
             st.rerun()

    # 2. 考试进行中
    elif not st.session_state.exam_session['submitted']:
        session = st.session_state.exam_session
        paper = session['paper']
        
        # ... (倒计时组件略) ...
        
        with st.form("exam_paper_form"):
            for idx, q in enumerate(paper):
                st.markdown(f"**第 {idx+1} 题**")
                
                # 渲染题干
                st.write(q['content'])
                
                q_type = q.get('type', 'single')
                
                # 区分渲染
                if q_type == 'subjective':
                    st.text_area("请输入答案/分录", key=f"ex_sub_{idx}", height=100)
                    # 注意：Form 里的 text_area 不需要 on_change，提交时会自动获取 session_state
                elif q_type == 'multi':
                    cols = st.columns(2)
                    for i, opt in enumerate(q.get('options',[])):
                        cols[i%2].checkbox(opt, key=f"ex_mul_{idx}_{i}")
                else:
                    st.radio("单选", q.get('options',[]), key=f"ex_sin_{idx}")
                
                st.divider()
            
            if st.form_submit_button("🏁 交卷"):
                # 收集答案
                for idx, q in enumerate(paper):
                    q_type = q.get('type', 'single')
                    if q_type == 'subjective':
                        session['answers'][idx] = st.session_state.get(f"ex_sub_{idx}", "")
                    elif q_type == 'multi':
                        sel = []
                        for i, opt in enumerate(q.get('options',[])):
                            if st.session_state.get(f"ex_mul_{idx}_{i}"): sel.append(opt[0].upper())
                        session['answers'][idx] = "".join(sorted(sel))
                    else:
                        val = st.session_state.get(f"ex_sin_{idx}")
                        session['answers'][idx] = val[0].upper() if val else ""
                
                session['submitted'] = True
                st.rerun()

    # 3. 考后报告 (含批量阅卷)
    else:
        session = st.session_state.exam_session
        paper = session['paper']
        user_ans_map = session['answers']
        
        # 如果还没出报告，先计算
        if 'report_data' not in session:
            total_score = 0
            detail_report = []
            
            # 创建进度条
            st.info("🤖 AI 正在逐题批改主观题，请稍候...")
            bar = st.progress(0)
            
            for idx, q in enumerate(paper):
                u_ans = user_ans_map.get(idx, "")
                q_type = q.get('type', 'single')
                std_ans = q.get('correct_answer', '')
                
                item_score = 0
                is_correct = False
                feedback = ""
                
                # 分支 A: 主观题 (调用 AI)
                if q_type == 'subjective':
                    res = ai_grade_subjective(u_ans, std_ans, q['content'])
                    # 假设每题权重平均，换算成百分制
                    # 比如试卷共10题，每题10分。AI给的 res['score'] 是0-100。
                    # 得分 = (res['score'] / 100) * (100 / len(paper))
                    weight = 100 / len(paper)
                    item_score = (res['score'] / 100) * weight
                    is_correct = (res['score'] >= 60)
                    feedback = res['feedback']
                
                # 分支 B: 客观题
                else:
                    weight = 100 / len(paper)
                    clean_std = str(std_ans).replace(" ","").upper()
                    if u_ans == clean_std:
                        item_score = weight
                        is_correct = True
                    else:
                        item_score = 0
                        is_correct = False
                
                total_score += item_score
                detail_report.append({
                    "q": q, "u_ans": u_ans, "score": item_score, 
                    "is_correct": is_correct, "feedback": feedback
                })
                bar.progress((idx+1)/len(paper))
            
            session['report_data'] = detail_report
            session['final_score'] = int(total_score)
            st.rerun()

        # 展示报告
        final_score = session['final_score']
        st.balloons()
        st.markdown(f"# 🏆 最终得分：{final_score}")
        
        for idx, item in enumerate(session['report_data']):
            q = item['q']
            status = "✅" if item['is_correct'] else "❌"
            with st.expander(f"第 {idx+1} 题 {status} (得分: {item['score']:.1f})"):
                st.write(q['content'])
                st.markdown(f"**你的答案：**\n{item['u_ans']}")
                st.markdown(f"**参考答案：**\n{q['correct_answer']}")
                if item['feedback']:
                    st.info(f"AI 点评：{item['feedback']}")
                    
        if st.button("退出"):
            st.session_state.exam_session = None
            st.rerun()

# === 📊 弱项分析 ===
elif menu == "📊 弱项分析":
    st.title("📊 学习效果")
    try:
        rows = supabase.table("user_answers").select("*").limit(500).execute().data
        if rows:
            df = pd.DataFrame(rows)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"<div class='css-card'>总刷题<div class='stat-value'>{len(df)}</div></div>", unsafe_allow_html=True)
            with c2:
                ok = len(df[df['is_correct']==True])
                st.markdown(f"<div class='css-card'>正确率<div class='stat-value'>{int(ok/len(df)*100)}%</div></div>", unsafe_allow_html=True)
            
            fig = px.pie(df, names='is_correct', title='正确率分布', color_discrete_sequence=['#00C090', '#FF7043'])
            st.plotly_chart(fig)
        else: st.info("暂无数据")
    except: st.error("数据加载失败")

# === ❌ 错题本 ===
elif menu == "❌ 错题本":
    st.title("❌ 错题集")
    try:
        errs = supabase.table("user_answers").select("*, question_bank(*)").eq("user_id", user_id).eq("is_correct", False).order("created_at", desc=True).execute().data
    except: errs = []
    
    uq = {}
    for e in errs:
        if e['question_id'] not in uq: uq[e['question_id']] = e
        
    if not uq: st.success("无错题")
    else:
        for qid, e in uq.items():
            q = e['question_bank']
            if not q: continue
            with st.expander(f"🔴 {q['content'][:30]}..."):
                st.markdown(f"**{q['content']}**")
                for o in q['options']: st.markdown(f"<div class='option-item'>{o}</div>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                c1.error(f"错: {e['user_response']}"); c2.success(f"对: {q['correct_answer']}")
                st.info(q['explanation'])
                
                # 功能区
                h = e.get('ai_chat_history') or []
                c_ai, c_rm = st.columns([3,1])
                if c_ai.button("🤔 AI 举例", key=f"x_ai_{qid}"):
                    r = call_ai_universal(f"举例解释：{q['content']}。")
                    if r:
                        h.append({"role":"model", "content":r})
                        supabase.table("user_answers").update({"ai_chat_history":h}).eq("id", e['id']).execute()
                        st.rerun()
                
                if c_rm.button("✅ 移除", key=f"x_rm_{qid}"):
                    supabase.table("user_answers").update({"is_correct":True}).eq("question_id", qid).execute()
                    st.rerun()
                    
                for m in h:
                    st.markdown(f"<div class='chat-{'ai' if m['role']=='model' else 'user'}'>{m['content']}</div>", unsafe_allow_html=True)



# =========================================================
# 🛠️ 数据管理 & 补录 (V7.0: 人工兜底与 Excel 导入)
# =========================================================
elif menu == "🛠️ 数据管理 & 补录":
    st.title("🛠️ 数据管理中心")
    st.caption("在此处手动修正 AI 的错误，或通过 Excel 批量导入自有题库。")

    tab_edit, tab_upload = st.tabs(["✏️ 题库可视编辑", "📥 Excel 批量导入"])

    # --- 辅助工具：选项格式转换 ---
    def list_to_str(lst):
        """将 ['A.xx', 'B.xx'] 转为 'A.xx | B.xx' 方便编辑"""
        if isinstance(lst, list): return " | ".join(lst)
        return str(lst) if lst else ""

    def str_to_list(s):
        """将 'A.xx | B.xx' 转回 JSON 数组"""
        if not s: return []
        return [x.strip() for x in s.split("|") if x.strip()]

    # ---------------------------------------------------------
    # Tab 1: 数据库直接编辑 (CRUD)
    # ---------------------------------------------------------
    with tab_edit:
        st.info("💡 提示：双击单元格修改，修改后点击下方“💾 保存修改”生效。勾选行首可删除。")
        
        # 1. 筛选数据
        subjects = get_subjects()
        if not subjects: st.warning("请先初始化科目"); st.stop()
        
        c1, c2, c3 = st.columns(3)
        with c1:
            s_name = st.selectbox("科目", [s['name'] for s in subjects], key="man_sub")
            sid = next(s['id'] for s in subjects if s['name'] == s_name)
        with c2:
            books = get_books(sid)
            bid = None
            if books:
                b_map = {b['title']: b['id'] for b in books}
                b_name = st.selectbox("书籍", list(b_map.keys()), key="man_book")
                bid = b_map[b_name]
        with c3:
            cid = None
            if bid:
                chaps = get_chapters(bid)
                if chaps:
                    c_map = {c['title']: c['id'] for c in chaps}
                    c_name = st.selectbox("章节", list(c_map.keys()), key="man_chap")
                    cid = c_map[c_name]

        # 2. 加载数据
        if cid:
            # 拉取该章节所有题目
            qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).order("id").execute().data
            
            if not qs:
                st.warning("该章节暂无题目，请去【Excel 批量导入】或【智能拆书】添加。")
            else:
                # 转换数据格式以适应 DataEditor (主要是 options 数组转字符串)
                edit_data = []
                for q in qs:
                    edit_data.append({
                        "id": q['id'],
                        "type": q['type'],
                        "content": q['content'],
                        "options_str": list_to_str(q['options']), # 拍扁数组
                        "correct_answer": q['correct_answer'],
                        "explanation": q.get('explanation', ''),
                        "del": False # 删除标记
                    })
                
                df = pd.DataFrame(edit_data)
                
                # 3. 显示编辑器
                edited_df = st.data_editor(
                    df,
                    column_config={
                        "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                        "del": st.column_config.CheckboxColumn("删除?", width="small"),
                        "type": st.column_config.SelectboxColumn("题型", options=["single","multi","subjective"], width="medium"),
                        "content": st.column_config.TextColumn("题目内容 (支持换行)", width="large"),
                        "options_str": st.column_config.TextColumn("选项 (用 | 分隔)", help="例如: A.对 | B.错", width="medium"),
                        "correct_answer": st.column_config.TextColumn("答案", width="small"),
                        "explanation": st.column_config.TextColumn("解析", width="medium"),
                    },
                    use_container_width=True,
                    num_rows="dynamic", # 允许添加新行
                    key=f"editor_{cid}"
                )

                # 4. 保存逻辑
                if st.button("💾 保存修改 (Save Changes)", type="primary"):
                    try:
                        changes_count = 0
                        # 转换 dataframe 为 list of dicts
                        rows = edited_df.to_dict('records')
                        
                        for row in rows:
                            # A. 删除逻辑
                            if row.get('del') == True:
                                if row.get('id'): # 只有已存在的才能删
                                    supabase.table("question_bank").delete().eq("id", row['id']).execute()
                                    changes_count += 1
                                continue
                            
                            # B. 数据清洗
                            clean_opts = str_to_list(row['options_str'])
                            
                            # 构造 Payload
                            payload = {
                                "chapter_id": cid,
                                "user_id": user_id,
                                "type": row['type'],
                                "content": row['content'],
                                "options": clean_opts,
                                "correct_answer": row['correct_answer'],
                                "explanation": row['explanation'],
                                "origin": "manual_edit"
                            }
                            
                            # C. 更新或新增
                            if row.get('id'):
                                # 更新
                                supabase.table("question_bank").update(payload).eq("id", row['id']).execute()
                            else:
                                # 新增 (ID为空)
                                if row['content']: # 防止空行
                                    supabase.table("question_bank").insert(payload).execute()
                            
                            changes_count += 1
                        
                        st.success(f"成功处理 {changes_count} 条变更！")
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"保存失败: {e}")

    # ---------------------------------------------------------
    # Tab 2: Excel 批量导入 (Token Saver)
    # ---------------------------------------------------------
    with tab_upload:
        st.markdown("#### 📥 零消耗导入")
        st.markdown("如果你的资料已经是整理好的（如机构给的题库Excel），直接在这里上传，**无需消耗 AI Token**，且准确率 100%。")
        
        # 1. 下载模板
        template_data = [
            {
                "题型(必填)": "single", 
                "题目内容(必填)": "下列属于资产的是？", 
                "选项(用|分隔)": "A.存货 | B.员工 | C.计划", 
                "正确答案(必填)": "A", 
                "解析": "资产定义..."
            },
            {
                "题型(必填)": "subjective", 
                "题目内容(必填)": "计算甲公司2024净利润...", 
                "选项(用|分隔)": "", 
                "正确答案(必填)": "净利润=100-20=80万", 
                "解析": ""
            }
        ]
        df_temp = pd.DataFrame(template_data)
        
        # 转换 CSV 用于下载
        csv = df_temp.to_csv(index=False).encode('utf-8-sig')
        st.download_button("⬇️ 下载 Excel/CSV 模板", data=csv, file_name="题库导入模板.csv", mime="text/csv")
        
        st.divider()
        
        # 2. 上传与解析
        c_up1, c_up2 = st.columns(2)
        with c_up1:
            # 必须先选章节
            st.info("请先在上方【题库可视编辑】标签页中选中**目标章节**，数据将导入该章节。")
            target_cid = cid # 复用上面的变量
            if not target_cid:
                st.error("未选择目标章节，无法导入！")
            
        with c_up2:
            up_excel = st.file_uploader("上传填好的 CSV/Excel", type=["csv", "xlsx"])
        
        if up_excel and target_cid:
            if st.button("🚀 开始导入", type="primary"):
                try:
                    # 读取文件
                    if up_excel.name.endswith('.csv'):
                        df_new = pd.read_csv(up_excel)
                    else:
                        df_new = pd.read_excel(up_excel)
                    
                    # 进度条
                    bar = st.progress(0)
                    total = len(df_new)
                    success_cnt = 0
                    
                    batch_data = []
                    
                    for i, row in df_new.iterrows():
                        # 容错处理列名
                        content = row.get('题目内容(必填)') or row.get('题目内容') or row.get('content')
                        ans = row.get('正确答案(必填)') or row.get('正确答案') or row.get('correct_answer')
                        typ = row.get('题型(必填)') or row.get('题型') or row.get('type') or 'single'
                        exp = row.get('解析') or row.get('explanation') or ''
                        opts_raw = row.get('选项(用|分隔)') or row.get('选项') or row.get('options')
                        
                        if pd.isna(content) or pd.isna(ans): continue # 跳过无效行
                        
                        # 选项清洗
                        opts_list = []
                        if opts_raw and not pd.isna(opts_raw):
                            opts_list = [str(x).strip() for x in str(opts_raw).split("|") if str(x).strip()]
                        
                        batch_data.append({
                            "chapter_id": target_cid,
                            "user_id": user_id,
                            "type": str(typ).strip(),
                            "content": str(content),
                            "correct_answer": str(ans),
                            "explanation": str(exp),
                            "options": opts_list,
                            "origin": "excel_import",
                            "batch_source": f"Upload-{datetime.date.today()}"
                        })
                        
                        if len(batch_data) >= 10: # 10条一批插入
                            supabase.table("question_bank").insert(batch_data).execute()
                            batch_data = []
                            
                        bar.progress((i+1)/total)
                        success_cnt += 1
                        
                    # 插入剩余的
                    if batch_data:
                        supabase.table("question_bank").insert(batch_data).execute()
                        
                    st.success(f"🎉 导入成功！共加入 {success_cnt} 道题。")
                    time.sleep(2)
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"导入失败: {e}\n请确保使用了正确的模板格式。")



# =========================================================
# ⚙️ 设置中心 (V3.1 修复版：配置回显 + 连通测试 + 考期同步)
# =========================================================
elif menu == "⚙️ 设置中心":
    st.title("⚙️ 系统设置")
    
    # 1. 读取云端配置 (核心修复)
    # 必须先从 profile 里读出来，否则滑块永远是默认值
    current_settings = profile.get('settings') or {}
    saved_timeout = current_settings.get('ai_timeout', 60) # 读不到就默认60
    
    # --- A. AI 模型参数 ---
    st.markdown("#### 🤖 AI 参数配置")
    
    col_test, col_set = st.columns([1, 2])
    
    with col_test:
        st.info(f"当前通道：**{st.session_state.get('selected_provider')}**")
        # 连通性测试功能
        if st.button("📡 测试 AI 连通性"):
            with st.spinner("发送 Hello World..."):
                start_t = time.time()
                res = call_ai_universal("Say 'OK' in one word.", timeout_override=10)
                cost_t = time.time() - start_t
                
                if "Error" in res or "异常" in res:
                    st.error(f"❌ 失败: {res}")
                else:
                    st.success(f"✅ 通畅! 耗时 {cost_t:.2f}s")
                    st.caption(f"回复: {res}")

    with col_set:
        # 修复：value 设置为 saved_timeout (从数据库读)
        new_timeout = st.slider(
            "⏳ AI 回答超时限制 (秒)", 
            min_value=10, 
            max_value=300, 
            value=saved_timeout, 
            help="如果是生成整章讲义或全量入库，建议调大此值 (如 120秒)"
        )
        
        if st.button("💾 保存参数"):
            if new_timeout != saved_timeout:
                update_settings(user_id, {"ai_timeout": new_timeout})
                st.success(f"已保存！超时限制改为 {new_timeout} 秒")
                time.sleep(1)
                st.rerun() # 强制刷新页面，让变量生效
            else:
                st.info("配置未变更")

    st.divider()
    
    # --- B. 考试时间设置 (保留联网功能) ---
    st.markdown("#### 📅 考试倒计时")
    
    # 自动同步
    if st.button("🌐 联网推测 2025 考试日期 (AI)"):
        with st.spinner("正在分析历史考情..."):
            # 模拟 AI 决策
            p = f"根据中国会计资格评价中心惯例，推测 {datetime.date.today().year} 年中级会计考试日期。仅返回 YYYY-MM-DD 格式。"
            ai_date = call_ai_universal(p)
            try:
                clean_d = ai_date.strip()[:10]
                # 简单校验格式
                datetime.datetime.strptime(clean_d, '%Y-%m-%d')
                
                supabase.table("study_profile").update({"exam_date": clean_d}).eq("user_id", user_id).execute()
                st.success(f"已更新为: {clean_d}")
                time.sleep(1)
                st.rerun()
            except:
                st.warning("AI 返回日期格式有误，请手动设置")

    # 手动设置
    curr_date = datetime.date(2025, 9, 6)
    if profile.get('exam_date'):
        try: curr_date = datetime.datetime.strptime(profile['exam_date'], '%Y-%m-%d').date()
        except: pass
        
    set_date = st.date_input("手动设定目标日期", curr_date)
    if set_date != curr_date:
        supabase.table("study_profile").update({"exam_date": str(set_date)}).eq("user_id", user_id).execute()
        st.toast("日期已更新")
        time.sleep(1)
        st.rerun()

    st.divider()
    
    # --- C. 危险区域 ---
    with st.expander("🗑️ 危险操作 (数据清理)"):
        c_del1, c_del2 = st.columns(2)
        with c_del1:
            if st.button("清空所有错题记录"):
                supabase.table("user_answers").delete().eq("user_id", user_id).execute()
                st.success("错题本已清空")
                
        with c_del2:
            if st.button("清空所有书籍资料"):
                supabase.table("books").delete().eq("user_id", user_id).execute()
                # 因为设置了级联删除(Cascade)，章节、题目、内容会自动删除
                st.success("资料库已格式化")
















