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
    if p: update_settings(user_id, {"last_provider": p, "last_used_model": m})

# --- AI 调用 (通用版 + 动态超时) ---
# --- AI 调用 (通用版：支持模型覆盖 + 超时豁免) ---
def call_ai_universal(prompt, history=[], model_override=None, timeout_override=None):
    """
    timeout_override: 如果传入整数(秒)，将无视用户的全局设置，强制使用该时间。
    传入 1200 (20分钟) 几乎等同于不限制，只依赖 API 服务端超时。
    """
    # 1. 确定超时时间
    if timeout_override is not None:
        current_timeout = timeout_override
    else:
        # 读取用户设置，默认60秒
        profile = get_user_profile(st.session_state.get('user_id'))
        settings = profile.get('settings') or {}
        current_timeout = settings.get('ai_timeout', 60)

    # 2. 确定模型
    provider = st.session_state.get('selected_provider', 'Gemini')
    target_model = model_override or st.session_state.get('openrouter_model_id') or st.session_state.get('google_model_id') or st.session_state.get('deepseek_model_id')
    
    if not target_model: target_model = "gemini-1.5-flash"
    
    try:
        # A. Google Gemini
        if "Gemini" in provider and not model_override:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={API_KEY}"
            headers = {'Content-Type': 'application/json'}
            contents = []
            for h in history:
                role = "user" if h['role'] == 'user' else "model"
                contents.append({"role": role, "parts": [{"text": h['content']}]})
            contents.append({"role": "user", "parts": [{"text": prompt}]})
            
            # 使用计算出的超时时间
            resp = requests.post(url, headers=headers, json={"contents": contents}, timeout=current_timeout)
            if resp.status_code == 200:
                return resp.json()['candidates'][0]['content']['parts'][0]['text']
            return f"Gemini Error {resp.status_code}: {resp.text}"

        # B. OpenAI 兼容 (DeepSeek / OpenRouter / 或 Override 的 Gemini)
        else:
            client = None
            # 特殊逻辑：如果是 Override 的 Gemini (用于拆书)，尝试走 OpenRouter 协议或 Gemini 协议
            # 这里为了简化，假设拆书时 override 走的是 OpenRouter 的 Gemini，或者我们需要在这里特判
            # 为了保证拆书稳定，建议拆书时如果 override="google/gemini-..."，我们还是走 OpenRouter 通道比较稳
            
            if model_override and "gemini" in model_override:
                 if "openrouter" in st.secrets:
                     client = OpenAI(api_key=st.secrets["openrouter"]["api_key"], base_url=st.secrets["openrouter"]["base_url"])
            elif "DeepSeek" in provider:
                client = OpenAI(api_key=st.secrets["deepseek"]["api_key"], base_url=st.secrets["deepseek"]["base_url"])
            elif "OpenRouter" in provider:
                client = OpenAI(api_key=st.secrets["openrouter"]["api_key"], base_url=st.secrets["openrouter"]["base_url"])
            
            if not client: return "AI Client 初始化失败"

            messages = [{"role": "system", "content": "你是一位资深会计讲师。回答请使用 Markdown 格式。"}]
            for h in history:
                role = "assistant" if h['role'] == "model" else h['role']
                messages.append({"role": role, "content": h['content']})
            messages.append({"role": "user", "content": prompt})

            # 使用计算出的超时时间
            resp = client.chat.completions.create(
                model=target_model, 
                messages=messages, 
                temperature=0.7,
                timeout=current_timeout # 🔥 关键应用
            )
            return resp.choices[0].message.content

    except Exception as e:
        return f"AI 处理超时或中断 (当前限制 {current_timeout}s): {e}"

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
    provs = ["Gemini (官方直连)", "DeepSeek (官方直连)", "OpenRouter (聚合平台)"]
    saved_p = settings.get('last_provider')
    idx_p = 0
    if saved_p:
        for i, x in enumerate(provs):
            if saved_p in x: idx_p = i; break
            
    prov = st.selectbox("🧠 AI 大脑", provs, index=idx_p, key="ai_provider_select", on_change=save_ai_pref)
    st.session_state.selected_provider = prov
    
    saved_m = settings.get('last_used_model')
    
    if "Gemini" in prov:
        opts = fetch_google_models(st.secrets["GOOGLE_API_KEY"]) or ["gemini-1.5-flash"]
        idx_m = opts.index(saved_m) if saved_m in opts else 0
        st.session_state.google_model_id = st.selectbox("🔌 模型", opts, index=idx_m, key="gl_model_select", on_change=save_ai_pref)
        
    elif "DeepSeek" in prov:
        opts = ["deepseek-chat", "deepseek-reasoner"]
        idx_m = opts.index(saved_m) if saved_m in opts else 0
        st.session_state.deepseek_model_id = st.selectbox("🔌 模型", opts, index=idx_m, key="ds_model_select", on_change=save_ai_pref)
        
    elif "OpenRouter" in prov:
        all_ms = fetch_openrouter_models(st.secrets["openrouter"]["api_key"])
        if not all_ms:
            st.warning("OpenRouter 连接失败")
            final_ids = ["google/gemini-2.0-flash-exp:free"]
        else:
            ft = st.radio("筛选", ["🤑 免费", "🌎 全部"], horizontal=True)
            subset = [m for m in all_ms if m['is_free']] if "免费" in ft else all_ms
            final_ids = [m['id'] for m in subset]
            if not final_ids: final_ids = [m['id'] for m in all_ms]
            
        idx_m = final_ids.index(saved_m) if saved_m in final_ids else 0
        st.session_state.openrouter_model_id = st.selectbox("🔌 模型", final_ids, index=idx_m, key="or_model_select", on_change=save_ai_pref)

    st.divider()
    
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
# 📂 智能拆书 & 资料 (V4.2 完美融合版：试读预览 + 超时豁免)
# =========================================================
elif menu == "📂 智能拆书 & 资料":
    st.title("📂 资料库管理")
    
    # --- 内部辅助函数 ---
    def clean_textbook_content(text):
        """清洗教材：去页眉页脚"""
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            if len(line.strip()) < 3 or line.strip().isdigit(): continue
            cleaned.append(line)
        return "\n".join(cleaned)

    def sanitize_answer(raw_ans):
        """清洗答案：只保留 A-H"""
        if not raw_ans: return ""
        s = str(raw_ans).upper()
        import re
        clean_s = re.sub(r'[^A-H]', '', s)
        return "".join(sorted(list(set(clean_s))))

    # --- 初始化检查 ---
    subjects = get_subjects()
    if not subjects: 
        st.error("请先初始化科目数据")
        st.stop()
    
    # --- 1. 顶层选择 (科目 -> 书籍) ---
    c1, c2 = st.columns([1, 2])
    with c1:
        s_name = st.selectbox("1. 所属科目", [s['name'] for s in subjects])
        sid = next(s['id'] for s in subjects if s['name'] == s_name)
    with c2:
        books = get_books(sid)
        # ID 防重名
        book_map = {f"{b['title']} (ID:{b['id']})": b['id'] for b in books}
        b_opts = ["➕ 上传新资料 (智能拆分)..."] + list(book_map.keys())
        sel_book_label = st.selectbox("2. 选择书籍/文件", b_opts)
    
    st.divider()

    # =====================================================
    # 场景 A: 上传新资料 (向导模式)
    # =====================================================
    if "上传新" in sel_book_label:
        st.markdown("#### 📤 第一步：上传与定性")
        
        # 1. 定性
        doc_type = st.radio("这份文件是？", ["📖 纯教材 (用于学习/出新题)", "📑 习题库/真题集 (用于录入库存)"], horizontal=True)
        
        # 2. 上传
        up_file = st.file_uploader("拖入 PDF 文件", type="pdf")
        
        if up_file:
            try:
                with pdfplumber.open(up_file) as pdf: 
                    total_pages = len(pdf.pages)
                st.success(f"文件已加载：{up_file.name} (共 {total_pages} 页)")
                
                # Session 初始化
                if 'toc_step' not in st.session_state: st.session_state.toc_step = 1
                
                # --- Step 1: AI 分析目录 ---
                if st.session_state.toc_step == 1:
                    # >>> 分支 1: 纯教材 <<<
                    if "纯教材" in doc_type:
                        st.info("💡 逻辑：AI 扫描目录 -> 按章节切分 -> 存入教材库。")
                        if st.button("🚀 开始拆解教材"):
                            with st.spinner("AI 正在阅读目录 (前20页)..."):
                                toc_text = extract_pdf(up_file, 1, min(20, total_pages))
                                p = f"分析教材目录。总页数{total_pages}。返回JSON列表: [{{'title':'章节名','start_page':5,'end_page':10}}]\n文本：{toc_text[:8000]}"
                                res = call_ai_universal(p, model_override="google/gemini-1.5-flash")
                                if res:
                                    try:
                                        clean = res.replace("```json","").replace("```","").strip()
                                        s = clean.find('['); e = clean.rfind(']')+1
                                        st.session_state.toc_result = json.loads(clean[s:e])
                                        st.session_state.toc_step = 2
                                        st.rerun()
                                    except: st.error("目录解析失败，请重试")
                
                    # >>> 分支 2: 习题库 <<<
                    else: 
                        st.info("💡 逻辑：AI 分析结构 -> **用户试读校对** -> 确认无误后批量入库。")
                        ans_mode = st.radio("答案位置", ["🅰️ 紧跟在题目后面", "🅱️ 集中在文件末尾 (需拼接)"])
                        user_hint = st.text_input("特殊情况备注", placeholder="例：忽略水印，第四章答案缺失...")
                        
                        if st.button("🚀 开始分析习题结构"):
                            with st.spinner("AI 正在分析结构..."):
                                toc_text = extract_pdf(up_file, 1, min(30, total_pages))
                                p = f"分析习题集结构。总页数{total_pages}。请划分出【题目区域】。返回JSON列表: [{{'title':'章节名','start_page':1,'end_page':5}}]\n文本：{toc_text[:8000]}"
                                res = call_ai_universal(p)
                                if res:
                                    try:
                                        clean = res.replace("```json","").replace("```","").strip()
                                        s = clean.find('['); e = clean.rfind(']')+1
                                        toc_data = json.loads(clean[s:e])
                                        # 初始化答案页码
                                        for item in toc_data:
                                            item['ans_start_page'] = 0
                                            item['ans_end_page'] = 0
                                        st.session_state.toc_result = toc_data
                                        st.session_state.toc_step = 2
                                        st.session_state.ans_mode_cache = ans_mode
                                        st.session_state.user_hint_cache = user_hint
                                        st.rerun()
                                    except: st.error("结构分析失败")

                # --- Step 2: 确认与执行 (通用步骤) ---
                if st.session_state.get('toc_step') == 2 and 'toc_result' in st.session_state:
                    st.divider()
                    st.markdown("#### 📝 第二步：配置页码结构")
                    
                    col_cfg = {
                        "title": "章节/分类名称",
                        "start_page": st.column_config.NumberColumn("题目起始页", min_value=1, format="%d"),
                        "end_page": st.column_config.NumberColumn("题目结束页", min_value=1, format="%d")
                    }
                    
                    is_ans_split = st.session_state.get('ans_mode_cache') and "文件末尾" in st.session_state.get('ans_mode_cache')
                    if is_ans_split:
                        st.warning("⚠️ 答案后置模式：请务必填写【答案起始页】！")
                        col_cfg["ans_start_page"] = st.column_config.NumberColumn("答案起始", min_value=1, format="%d")
                        col_cfg["ans_end_page"] = st.column_config.NumberColumn("答案结束", min_value=1, format="%d")

                    edited_df = st.data_editor(st.session_state.toc_result, column_config=col_cfg, num_rows="dynamic", use_container_width=True)
                    
                    # --- 🔥 [复活] 试读校对功能 ---
                    if "习题库" in doc_type:
                        st.markdown("#### 🧪 第三步：试读校对 (强烈推荐)")
                        st.caption("先让 AI 试着提取 5 道题，确认题目和答案是否对齐。")
                        
                        # 选择一个章节进行测试
                        preview_options = [f"{i}. {row['title']}" for i, row in enumerate(edited_df)]
                        sel_preview = st.selectbox("选择一个章节进行试读：", preview_options)
                        preview_idx = int(sel_preview.split(".")[0])
                        
                        # Session 用于存试读结果
                        if 'sample_data' not in st.session_state: st.session_state.sample_data = None
                        
                        if st.button("🔍 抽取 5 题进行试读"):
                            row = edited_df[preview_idx]
                            try:
                                # 强制转 int
                                p_s = int(float(row['start_page']))
                                p_e = min(p_s + 2, int(float(row['end_page']))) # 只读前2-3页题目
                                
                                up_file.seek(0)
                                q_text = extract_pdf(up_file, p_s, p_e)
                                
                                # 拼接答案 (只读前1-2页答案)
                                if is_ans_split:
                                    a_s = int(float(row.get('ans_start_page', 0)))
                                    a_e = min(a_s + 2, int(float(row.get('ans_end_page', 0))))
                                    if a_s > 0:
                                        up_file.seek(0)
                                        a_text = extract_pdf(up_file, a_s, a_e)
                                        q_text += f"\n\n====== 答案参考区域 ======\n{a_text}"
                                
                                with st.spinner("AI 正在试读并配对..."):
                                    hint = st.session_state.get('user_hint_cache', '')
                                    p_test = f"""
                                    任务：试读并提取前 5 道题目。确保题目和答案对应。
                                    用户提示：{hint}
                                    规则：答案只填字母A-H。
                                    返回JSON: [{{ "question": "...", "answer": "A", "options": ["A.","B."] }}]
                                    文本：{q_text[:15000]}
                                    """
                                    res = call_ai_universal(p_test)
                                    if res:
                                        cln = res.replace("```json","").replace("```","").strip()
                                        s = cln.find('['); e = cln.rfind(']')+1
                                        data = json.loads(cln[s:e])
                                        
                                        # 预清洗展示
                                        for d in data:
                                            d['answer'] = sanitize_answer(d.get('answer',''))
                                            
                                        st.session_state.sample_data = data
                            except Exception as e:
                                st.error(f"试读失败: {e}")

                        # 显示试读结果表格
                        if st.session_state.sample_data:
                            st.markdown("##### 👀 试读结果预览")
                            sample_df = pd.DataFrame(st.session_state.sample_data)
                            st.table(sample_df[['question', 'answer']])
                            
                            st.info("👆 如果题目和答案对齐无误，请点击下方绿色按钮执行全量入库。")
                    
                    st.divider()

                    # --- 🔥 [保留] 全量入库 (带超时豁免) ---
                    btn_label = "💾 第四步：执行全量入库 (超时豁免)" if "习题库" in doc_type else "💾 第三步：执行拆分并保存"
                    
                    if st.button(btn_label, type="primary"):
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        try:
                            # 1. 创建书
                            book_res = supabase.table("books").insert({
                                "user_id": user_id, "subject_id": sid, "title": up_file.name.replace(".pdf",""), "total_pages": total_pages
                            }).execute()
                            bid = book_res.data[0]['id']
                            
                            total_tasks = len(edited_df)
                            for i, row in enumerate(edited_df):
                                status_text.text(f"正在全量处理：{row['title']} (AI 思考中，请勿刷新)...")
                                
                                c_start = int(float(row['start_page']))
                                c_end = int(float(row['end_page']))
                                
                                # 建章
                                c_res = supabase.table("chapters").insert({
                                    "book_id": bid, "title": row['title'], "start_page": c_start, "end_page": c_end, "user_id": user_id
                                }).execute()
                                cid = c_res.data[0]['id']
                                
                                # 提取全文
                                up_file.seek(0)
                                q_text = extract_pdf(up_file, c_start, c_end)
                                
                                # 纯教材
                                if "纯教材" in doc_type:
                                    clean_txt = clean_textbook_content(q_text)
                                    if len(clean_txt) > 10:
                                        save_material_v3(cid, clean_txt, user_id)
                                
                                # 习题库 (AI 提取)
                                else:
                                    final_text = q_text
                                    if is_ans_split and int(float(row.get('ans_start_page', 0))) > 0:
                                        a_start = int(float(row['ans_start_page']))
                                        a_end = int(float(row['ans_end_page']))
                                        up_file.seek(0)
                                        a_text = extract_pdf(up_file, a_start, a_end)
                                        final_text += f"\n\n====== 答案参考区域 ======\n{a_text}"
                                    
                                    if len(final_text) > 50:
                                        hint = st.session_state.get('user_hint_cache', '')
                                        p_extract = f"""
                                        任务：全量提取题目。自动对齐答案。
                                        用户提示：{hint}
                                        规则：答案仅限A-H。
                                        返回JSON: [{{ "question": "...", "options": ["A.","B."], "answer": "A", "explanation": "..." }}]
                                        文本：{final_text[:25000]}
                                        """
                                        try:
                                            # 🔥 关键：使用 900秒 超时豁免
                                            r = call_ai_universal(p_extract, timeout_override=900)
                                            if r:
                                                cln = r.replace("```json","").replace("```","").strip()
                                                s = cln.find('['); e = cln.rfind(']')+1
                                                qs_data = json.loads(cln[s:e])
                                                
                                                fmt_qs = []
                                                for q in qs_data:
                                                    clean_ans = sanitize_answer(q.get('answer',''))
                                                    fmt_qs.append({
                                                        "question": q['question'], 
                                                        "options": q['options'], 
                                                        "answer": clean_ans, 
                                                        "explanation": q.get('explanation', ''), 
                                                        "type": "multi" if len(clean_ans)>1 else "single"
                                                    })
                                                save_questions_v3(fmt_qs, cid, user_id, origin="extract")
                                        except Exception as e:
                                            print(f"Chapter failed: {e}")
                                
                                progress_bar.progress((i + 1) / total_tasks)
                            
                            st.balloons()
                            st.success(f"🎉 全部入库完成！")
                            # 清空状态
                            del st.session_state.toc_step
                            del st.session_state.toc_result
                            if 'sample_data' in st.session_state: del st.session_state.sample_data
                            time.sleep(2)
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"入库失败: {e}")

            except Exception as e: st.error(f"文件读取错误: {e}")

    # =====================================================
    # 场景 B: 已有书籍管理 (保持不变)
    # =====================================================
    elif books:
        bid = book_map[sel_book_label]
        c_tit, c_act = st.columns([5, 1])
        with c_tit: st.markdown(f"### 📘 {sel_book_label.split(' (ID')[0]}")
        with c_act:
            if st.button("🗑️ 删除本书"):
                try:
                    supabase.table("books").delete().eq("id", bid).execute()
                    st.toast("书籍已删除")
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error(f"删除失败: {e}")

        chapters = get_chapters(bid)
        if not chapters: st.info("本书暂无章节")
        else:
            for chap in chapters:
                q_cnt = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", chap['id']).execute().count
                m_cnt = supabase.table("materials").select("id", count="exact").eq("chapter_id", chap['id']).execute().count
                with st.expander(f"📑 {chap['title']} (题:{q_cnt} | 教材:{'有' if m_cnt else '无'})"):
                    if st.button("🗑️ 清空本章数据", key=f"c_{chap['id']}"):
                         supabase.table("materials").delete().eq("chapter_id", chap['id']).execute()
                         supabase.table("question_bank").delete().eq("chapter_id", chap['id']).execute()
                         st.toast("已清空")
                         time.sleep(1)
                         st.rerun()

# === 🎓 AI 课堂 (讲义) ===
elif menu == "🎓 AI 课堂 (讲义)":
    st.title("🎓 智能讲义")
    books = supabase.table("books").select("*").eq("user_id", user_id).execute().data
    if not books: st.warning("请先去资料库上传书籍"); st.stop()
    
    c1, c2 = st.columns(2)
    with c1: 
        b_name = st.selectbox("书籍", [b['title'] for b in books])
        bid = next(b['id'] for b in books if b['title'] == b_name)
    with c2:
        chaps = get_chapters(bid)
        if chaps:
            c_name = st.selectbox("章节", [c['title'] for c in chaps])
            cid = next(c['id'] for c in chaps if c['title'] == c_name)
        else: cid = None; st.empty()

    if cid:
        lessons = supabase.table("ai_lessons").select("*").eq("chapter_id", cid).order("created_at", desc=True).execute().data
        if lessons:
            tabs = st.tabs([l['title'] or "未命名" for l in lessons])
            for i, tab in enumerate(tabs):
                with tab:
                    st.markdown(f"<div class='lesson-card'>{lessons[i]['content']}</div>", unsafe_allow_html=True)
                    if st.button("删除", key=f"dl_{i}"):
                        supabase.table("ai_lessons").delete().eq("id", lessons[i]['id']).execute()
                        st.rerun()
        else:
            st.info("本章暂无讲义，请去资料库生成。")

# =========================================================
# 📝 章节特训 (V3.8 终极版：进度管理 + 智能题型 + AI闭环)
# =========================================================
elif menu == "📝 章节特训":
    st.title("📝 章节突破")
    
    # --- 1. JS 实时悬浮计时器 (仅在刷题时显示) ---
    if st.session_state.get('quiz_active'):
        if 'js_start_time' not in st.session_state:
            st.session_state.js_start_time = int(time.time() * 1000)
        
        # 注入倒计时组件
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
                    # 使用 ID 映射防止同名书混淆
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
                    # 1. 题库总量
                    q_res = supabase.table("question_bank").select("id").eq("chapter_id", cid).execute().data
                    total_q = len(q_res)
                    
                    # 2. 用户已掌握量 (做对过的题)
                    mastered_count = 0
                    done_ids = []
                    if total_q > 0:
                        # 查用户在该章节所有做对的记录
                        user_correct = supabase.table("user_answers").select("question_id").eq("user_id", user_id).eq("is_correct", True).execute().data
                        # 取交集：即属于本章且已做对的
                        chapter_q_ids = set([q['id'] for q in q_res])
                        user_correct_ids = set([a['question_id'] for a in user_correct])
                        mastered_ids = user_correct_ids.intersection(chapter_q_ids)
                        mastered_count = len(mastered_ids)
                        done_ids = list(mastered_ids)
                    
                    # 进度条展示
                    prog = mastered_count / total_q if total_q > 0 else 0
                    st.caption(f"📈 掌握进度：{mastered_count} / {total_q} 题")
                    st.progress(prog)
                    
                except:
                    total_q = 0
                    done_ids = []

                st.divider()
                
                # === 🎯 练习模式选择 ===
                mode = st.radio("练习策略", [
                    "🧹 消灭库存 (只做未掌握的题)", 
                    "🎲 随机巩固 (全库随机抽)", 
                    "🧠 AI 基于教材出新题"
                ], horizontal=True)
                
                if st.button("🚀 开始练习", type="primary", use_container_width=True):
                    st.session_state.quiz_cid = cid
                    st.session_state.js_start_time = int(time.time() * 1000) # 重置计时
                    
                    # --- 策略 A: 消灭库存 ---
                    if "消灭" in mode:
                        if total_q == 0:
                            st.error("题库为空，请先去【资料库】录入真题！")
                        elif mastered_count == total_q:
                            st.balloons()
                            st.success("🎉 太棒了！本章题目已全部掌握！建议切换到随机模式复习。")
                        else:
                            # 核心逻辑：从题库中排除已掌握的 ID
                            # 注意：Supabase 的 not_.in_ 语法
                            qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).not_.in_("id", done_ids).limit(20).execute().data
                            if qs:
                                random.shuffle(qs)
                                st.session_state.quiz_data = qs[:10] # 每次推10题
                                st.session_state.q_idx = 0
                                st.session_state.quiz_active = True
                                st.rerun()
                            else:
                                st.warning("数据加载异常，请重试")

                    # --- 策略 B: 随机巩固 ---
                    elif "随机" in mode:
                        if total_q == 0:
                            st.error("题库为空")
                        else:
                            # 简单随机：取前 100 个乱序 (生产环境可用 RPC random)
                            qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).limit(100).execute().data
                            if qs:
                                random.shuffle(qs)
                                st.session_state.quiz_data = qs[:10]
                                st.session_state.q_idx = 0
                                st.session_state.quiz_active = True
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
                                    "explanation": "详细解析..."
                                  }}
                                ]
                                注意：如果是多选，correct_answer 请设为 "AB" 格式。
                                """
                                res = call_ai_universal(prompt)
                                if res:
                                    try:
                                        clean = res.replace("```json","").replace("```","").strip()
                                        d = json.loads(clean)
                                        
                                        # 存入数据库 (变成真题库存)
                                        db_qs = [{
                                            'chapter_id': cid,
                                            'user_id': user_id,
                                            'type': 'multi' if len(x['correct_answer'])>1 else 'single',
                                            'content': x['content'],
                                            'options': x['options'],
                                            'correct_answer': x['correct_answer'],
                                            'explanation': x['explanation'],
                                            'origin': 'ai_gen',
                                            'batch_source': f'AI生成-{datetime.date.today()}'
                                        } for x in d]
                                        
                                        supabase.table("question_bank").insert(db_qs).execute()
                                        
                                        # 载入练习
                                        st.session_state.quiz_data = d
                                        st.session_state.q_idx = 0
                                        st.session_state.quiz_active = True
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"AI 生成格式错误: {e}")
                                        st.write(res) # 调试
        else:
            st.warning("请先去【资料库】初始化科目和上传书籍")

    # --- 3. 做题交互界面 (Active State) ---
    if st.session_state.get('quiz_active'):
        idx = st.session_state.q_idx
        data_len = len(st.session_state.quiz_data)
        
        if idx >= data_len:
            st.balloons()
            st.success("🎉 本轮练习完成！")
            c_back, c_space = st.columns([1, 4])
            with c_back:
                if st.button("🔙 返回章节菜单"):
                    st.session_state.quiz_active = False
                    st.rerun()
        else:
            q = st.session_state.quiz_data[idx]
            
            # 顶部进度条
            st.progress((idx + 1) / data_len)
            c_idx, c_end = st.columns([5, 1])
            with c_idx: st.caption(f"当前进度：{idx + 1} / {data_len}")
            with c_end:
                if st.button("🏁 结束"):
                    st.session_state.quiz_active = False
                    st.rerun()

            # 数据清洗
            q_text = q.get('content') or q.get('question')
            raw_ans = q.get('correct_answer') or q.get('answer')
            # 统一转为无空格大写 "AB"
            q_ans = "".join(sorted(list(str(raw_ans).replace(",", "").replace("，", "").replace(" ", "").upper())))
            q_exp = q.get('explanation', '暂无解析')
            q_opts = q.get('options', [])

            # --- 智能题型识别 ---
            is_multi = len(q_ans) > 1 or q.get('type') == 'multi'
            type_badge = "<span style='background:#ff9800;color:white;padding:2px 8px;border-radius:4px;font-size:12px'>多选题</span>" if is_multi else "<span style='background:#00C090;color:white;padding:2px 8px;border-radius:4px;font-size:12px'>单选题</span>"

            # 题目卡片
            st.markdown(f"""
            <div class='css-card'>
                <div style="margin-bottom:10px">{type_badge}</div>
                <h4 style="line-height:1.6">{q_text}</h4>
            </div>
            """, unsafe_allow_html=True)
            
            # 选项渲染
            user_val = ""
            if is_multi:
                st.caption("请选择所有正确选项：")
                selected_opts = []
                for opt in q_opts:
                    # 使用唯一 Key 防止组件冲突
                    if st.checkbox(opt, key=f"q_{idx}_opt_{opt}"):
                        selected_opts.append(opt[0].upper()) # 假设选项格式为 "A. xxx"
                user_val = "".join(sorted(selected_opts))
            else:
                st.caption("请选择唯一正确选项：")
                sel = st.radio("单选", q_opts, key=f"q_{idx}_radio", label_visibility="collapsed")
                user_val = sel[0].upper() if sel else ""
            
            # 提交状态控制
            sub_key = f"sub_state_{idx}"
            if sub_key not in st.session_state: st.session_state[sub_key] = False
            
            if st.button("✅ 提交答案", use_container_width=True) and not st.session_state[sub_key]:
                st.session_state[sub_key] = True
            
            # --- 判分与反馈 ---
            if st.session_state[sub_key]:
                # 1. 判分
                if user_val == q_ans:
                    st.markdown(f"<div class='success-box'>🎉 回答正确！</div>", unsafe_allow_html=True)
                    is_correct_bool = True
                else:
                    st.error(f"❌ 遗憾答错。正确答案是：{q_ans}")
                    is_correct_bool = False
                
                # 2. 存入数据库 (Upsert 逻辑：防重复)
                if q.get('id'): # 确保题目已入库
                    try:
                        # 检查是否已有记录
                        exist = supabase.table("user_answers").select("id").eq("user_id", user_id).eq("question_id", q['id']).eq("is_correct", False).execute().data
                        
                        if exist:
                            # 存在旧错题 -> 更新时间
                            supabase.table("user_answers").update({
                                "user_response": user_val,
                                "is_correct": is_correct_bool,
                                "created_at": datetime.datetime.now().isoformat()
                            }).eq("id", exist[0]['id']).execute()
                        else:
                            # 无记录 -> 插入
                            supabase.table("user_answers").insert({
                                "user_id": user_id, 
                                "question_id": q['id'], 
                                "user_response": user_val, 
                                "is_correct": is_correct_bool
                            }).execute()
                    except Exception as e:
                        print(f"Save Error: {e}")
                
                # 3. 解析与 AI 扩展
                st.divider()
                st.info(f"💡 **解析：** {q_exp}")
                
                # --- AI 举例与追问 (复用错题本逻辑) ---
                chat_key = f"quiz_chat_hist_{idx}"
                if chat_key not in st.session_state: st.session_state[chat_key] = []
                
                # 第一次请求
                if st.button("🤔 我不理解？让 AI 举个栗子", key=f"btn_ex_{idx}"):
                    prompt = f"用户做这道会计题：'{q_text}'。答案是{q_ans}。解析：{q_exp}。请用通俗的生活案例（如买菜、开店）来解释。"
                    with st.spinner("AI 正在思考..."):
                        res = call_ai_universal(prompt)
                        if res: 
                            st.session_state[chat_key].append({"role":"model", "content":res})

                # 显示对话流
                for msg in st.session_state[chat_key]:
                    css = "chat-ai" if msg['role'] == "model" else "chat-user"
                    st.markdown(f"<div class='{css}'>{msg['content']}</div>", unsafe_allow_html=True)
                
                # 追问框
                if st.session_state[chat_key]:
                    ask_input = st.text_input("继续追问...", key=f"ask_in_{idx}")
                    if st.button("发送", key=f"ask_send_{idx}") and ask_input:
                        st.session_state[chat_key].append({"role":"user", "content":ask_input})
                        with st.spinner("..."):
                            reply = call_ai_universal(ask_input, history=st.session_state[chat_key][:-1])
                            st.session_state[chat_key].append({"role":"model", "content":reply})
                            st.rerun()

            st.markdown("---")
            
            # 4. 下一题
            if st.button("➡️ 下一题", use_container_width=True):
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
# ⚔️ 全真模考 (V3.9 终极版：跨章节组卷 + 智能阅卷 + AI点评)
# =========================================================
elif menu == "⚔️ 全真模考":
    st.title("⚔️ 全真模拟考试")
    
    # 初始化考试状态
    if 'exam_session' not in st.session_state:
        st.session_state.exam_session = None

    # ---------------------------------------------------------
    # 场景 A: 考试配置台 (未开始)
    # ---------------------------------------------------------
    if not st.session_state.exam_session:
        # 1. 历史成绩概览 (Bento Grid 风格)
        st.markdown("##### 📜 最近模考记录")
        try:
            history = supabase.table("mock_exams").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(4).execute().data
            if history:
                cols = st.columns(4)
                for i, h in enumerate(history):
                    with cols[i]:
                        score_color = "#00C090" if h['user_score'] >= 60 else "#FF7043"
                        st.markdown(f"""
                        <div class="css-card" style="padding:15px; border-left: 4px solid {score_color}">
                            <div style="font-size:12px; color:#888">{h['created_at'][:10]}</div>
                            <div style="font-weight:bold; font-size:14px; height:40px; overflow:hidden; text-overflow:ellipsis;">{h['title']}</div>
                            <div style="font-size:24px; color:{score_color}; font-weight:800">{h['user_score']} <span style="font-size:12px">分</span></div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("暂无考试记录，快来开启你的第一次模考吧！")
        except: pass
        
        st.divider()
        
        # 2. 组卷配置
        subjects = get_subjects()
        if not subjects:
            st.error("系统未初始化科目数据")
            st.stop()
            
        c1, c2 = st.columns([1, 1])
        with c1:
            # 获取科目
            sel_sub = st.selectbox("选择模考科目", [s['name'] for s in subjects])
            sub_id = next(s['id'] for s in subjects if s['name'] == sel_sub)
        with c2:
            # 模式选择
            exam_mode = st.radio("试卷类型", ["🐇 精简自测 (5题 / 10分钟)", "🐢 全真模拟 (20题 / 60分钟)"], horizontal=True)
        
        # 3. 组卷逻辑 (V3 核心：科目 -> 书 -> 章 -> 题)
        if st.button("🚀 生成试卷并开始", type="primary", use_container_width=True):
            with st.spinner("正在全库扫描，智能组卷中..."):
                # Step 1: 找该科目下所有的书
                books = supabase.table("books").select("id").eq("subject_id", sub_id).execute().data
                if not books:
                    st.error("该科目下没有书籍资料，无法组卷！")
                    st.stop()
                book_ids = [b['id'] for b in books]
                
                # Step 2: 找这些书下所有的章
                chaps = supabase.table("chapters").select("id").in_("book_id", book_ids).execute().data
                if not chaps:
                    st.error("书籍中没有章节信息！")
                    st.stop()
                chap_ids = [c['id'] for c in chaps]
                
                # Step 3: 从题库中随机抽取题目
                # 策略：拉取该科目下的题目 (限制 200 道混淆)
                all_qs = supabase.table("question_bank").select("*").in_("chapter_id", chap_ids).limit(200).execute().data
                
                target_count = 5 if "精简" in exam_mode else 20
                duration_mins = 10 if "精简" in exam_mode else 60
                
                if len(all_qs) < target_count:
                    st.warning(f"题库库存不足！该科目总共只有 {len(all_qs)} 道题，将全部用于考试。")
                    final_paper = all_qs
                else:
                    import random
                    random.shuffle(all_qs)
                    final_paper = all_qs[:target_count]
                
                if not final_paper:
                    st.error("题库为空，请先去【资料库】录入题目。")
                    st.stop()

                # 初始化考试 Session
                st.session_state.exam_session = {
                    "paper": final_paper,
                    "answers": {}, # 存储用户答案 {index: val}
                    "subject": sel_sub,
                    "mode": exam_mode,
                    "start_time_ms": int(time.time() * 1000), # 用于 JS 倒计时
                    "duration_mins": duration_mins,
                    "submitted": False,
                    "report": None
                }
                st.rerun()

    # ---------------------------------------------------------
    # 场景 B: 考试进行中 (沉浸式)
    # ---------------------------------------------------------
    elif not st.session_state.exam_session['submitted']:
        session = st.session_state.exam_session
        paper = session['paper']
        
        # --- 1. 顶部状态栏 & JS 倒计时 ---
        
        # 计算倒计时目标时间戳
        end_time_ms = session['start_time_ms'] + (session['duration_mins'] * 60 * 1000)
        
        # 注入倒计时 JS
        timer_html = f"""
        <div style="
            position: fixed; top: 60px; right: 20px; z-index: 9999;
            background: #dc3545; color: white; 
            padding: 8px 20px; border-radius: 30px;
            font-family: monospace; font-size: 18px; font-weight: bold;
            box-shadow: 0 4px 15px rgba(220,53,69, 0.3);
            display: flex; align-items: center; gap: 8px;
        ">
            <span>⏳ 剩余</span> <span id="exam_timer">--:--</span>
        </div>
        <script>
            var endTime = {end_time_ms};
            function updateExamTimer() {{
                var now = Date.now();
                var diff = Math.floor((endTime - now) / 1000);
                
                if (diff <= 0) {{
                    document.getElementById("exam_timer").innerText = "00:00";
                    return;
                }}
                
                var m = Math.floor(diff / 60).toString().padStart(2, '0');
                var s = (diff % 60).toString().padStart(2, '0');
                document.getElementById("exam_timer").innerText = m + ":" + s;
            }}
            setInterval(updateExamTimer, 1000);
            updateExamTimer();
        </script>
        """
        components.html(timer_html, height=0)
        
        st.markdown(f"### 📝 {session['subject']} - {session['mode']}")
        st.progress(len(session['answers']) / len(paper)) # 答题进度条
        
        # --- 2. 题目渲染 (单页显示所有题目，模拟试卷) ---
        with st.form("exam_paper_form"):
            for idx, q in enumerate(paper):
                st.markdown(f"**第 {idx+1} 题：**")
                
                # 题目内容
                q_text = q['content']
                st.markdown(f"<div style='font-size:16px; margin-bottom:10px; background:#fff; padding:15px; border-radius:8px; border:1px solid #eee'>{q_text}</div>", unsafe_allow_html=True)
                
                # 智能识别单/多选
                std_ans = str(q['correct_answer']).replace(" ","").replace(",","").upper()
                is_multi = len(std_ans) > 1 or q.get('type') == 'multi'
                
                opts = q.get('options') or []
                
                if is_multi:
                    st.caption("（多选题）")
                    col_opts = st.columns(2)
                    selected = []
                    for i, opt in enumerate(opts):
                        # 使用 form key，确保唯一性
                        if col_opts[i % 2].checkbox(opt, key=f"ex_mul_{idx}_{i}"):
                            selected.append(opt[0].upper()) # 假设选项格式 "A. xxx"
                    
                    # 存入临时答案 (排序后拼接 "AB")
                    session['answers'][idx] = "".join(sorted(selected))
                    
                else:
                    st.caption("（单选题）")
                    val = st.radio("选择", opts, key=f"ex_sin_{idx}", index=None, label_visibility="collapsed")
                    if val:
                        session['answers'][idx] = val[0].upper()
                
                st.divider()
            
            # --- 3. 交卷按钮 ---
            submitted = st.form_submit_button("🏁 交卷并查看成绩", type="primary", use_container_width=True)
            
            if submitted:
                # 标记状态
                session['submitted'] = True
                st.rerun()

    # ---------------------------------------------------------
    # 场景 C: 考后报告 (评分 + AI 点评)
    # ---------------------------------------------------------
    else:
        session = st.session_state.exam_session
        paper = session['paper']
        user_ans_map = session['answers']
        
        # 1. 自动判分逻辑
        total_score = 0
        score_per_q = 100 / len(paper) # 动态分值
        
        detail_report = []
        
        for idx, q in enumerate(paper):
            u_ans = user_ans_map.get(idx, "")
            std_ans = str(q['correct_answer']).replace(" ","").replace(",","").replace("，","").upper()
            
            is_correct = (u_ans == std_ans)
            if is_correct: total_score += score_per_q
            
            # 记录详情
            detail_report.append({
                "q_content": q['content'],
                "u_ans": u_ans if u_ans else "未作答",
                "std_ans": std_ans,
                "is_correct": is_correct,
                "explanation": q.get('explanation', '暂无解析')
            })
            
            # 同步存入 user_answers 表 (用于弱项分析)
            if not is_correct:
                try:
                    supabase.table("user_answers").insert({
                        "user_id": user_id,
                        "question_id": q['id'],
                        "user_response": u_ans,
                        "is_correct": is_correct,
                        "time_taken": 0 # 模考暂不统计单题耗时
                    }).execute()
                except: pass

        final_score = int(total_score)
        
        # 2. AI 考后点评 (自动触发)
        if 'ai_comment' not in session:
            with st.spinner("🤖 AI 阅卷官正在分析你的试卷..."):
                wrong_qs = [d['q_content'] for d in detail_report if not d['is_correct']]
                if not wrong_qs:
                    session['ai_comment'] = "全对！简直是会计界的明日之星！保持这个状态，过关稳了。"
                else:
                    prompt = f"""
                    学生刚刚完成了一套会计模考，得分 {final_score}/100。
                    以下是他做错的题目内容摘要：
                    {str(wrong_qs)[:2000]}
                    
                    请给出简短、犀利的考后点评，并指出他需要加强复习的方向。
                    语气：严厉负责的班主任。
                    """
                    session['ai_comment'] = call_ai_universal(prompt)
                    
            # 3. 存入 mock_exams 表 (只存一次)
            try:
                supabase.table("mock_exams").insert({
                    "user_id": user_id,
                    "title": f"{session['subject']} 模考",
                    "mode": session['mode'],
                    "user_score": final_score,
                    "exam_data": json.dumps(detail_report) # 存快照
                }).execute()
            except: pass

        # 4. 显示成绩单
        st.balloons()
        
        c_score, c_comment = st.columns([1, 2])
        with c_score:
            st.markdown(f"""
            <div class="css-card" style="text-align:center; border-top: 5px solid #00C090;">
                <div style="color:#888;">最终得分</div>
                <div style="font-size:60px; color:#00C090; font-weight:800">{final_score}</div>
                <div style="font-size:14px;">满分 100</div>
            </div>
            """, unsafe_allow_html=True)
        with c_comment:
            st.info(f"📋 **AI 阅卷点评：**\n\n{session.get('ai_comment', '暂无点评')}")

        st.divider()
        st.subheader("🔍 试卷解析")
        
        for i, item in enumerate(detail_report):
            status = "✅ 正确" if item['is_correct'] else "❌ 错误"
            
            with st.expander(f"第 {i+1} 题：{status}"):
                st.markdown(f"**题目：** {item['q_content']}")
                
                c1, c2 = st.columns(2)
                c1.markdown(f"你的答案：`{item['u_ans']}`")
                c2.markdown(f"正确答案：`{item['std_ans']}`")
                
                if not item['is_correct']:
                    st.error("回答错误")
                else:
                    st.success("回答正确")
                    
                st.info(f"**解析：** {item['explanation']}")

        if st.button("🚪 退出考场", use_container_width=True):
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











