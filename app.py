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
def call_ai_universal(prompt, history=[], model_override=None):
    """支持 Gemini / DeepSeek / OpenRouter 的通用接口，带超时控制"""
    
    # 1. 获取用户配置的超时时间
    profile = get_user_profile(st.session_state.get('user_id'))
    settings = profile.get('settings') or {}
    current_timeout = settings.get('ai_timeout', 60) # 默认60秒

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
            
            resp = requests.post(url, headers=headers, json={"contents": contents}, timeout=current_timeout)
            if resp.status_code == 200:
                return resp.json()['candidates'][0]['content']['parts'][0]['text']
            return f"Gemini Error {resp.status_code}: {resp.text}"

        # B. OpenAI 兼容 (DeepSeek / OpenRouter)
        else:
            client = None
            if model_override and "gemini" in model_override:
                 # 特殊拆书场景
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

            resp = client.chat.completions.create(model=target_model, messages=messages, temperature=0.7, timeout=current_timeout)
            return resp.choices[0].message.content

    except Exception as e:
        return f"AI 连接超时或异常 (当前限制 {current_timeout}秒): {e}"

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
# 4. 侧边栏与导航 (还原多模型选择)
# ==============================================================================
profile = get_user_profile(user_id)
settings = profile.get('settings') or {}

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=50)
    st.markdown("### 会计私教 Pro")
    
    # --- AI 设置 (记忆版) ---
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
        # 兼容旧配置可能存在的不同格式
        idx_m = 0
        if saved_m in opts: idx_m = opts.index(saved_m)
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
    
    # --- 导航 ---
    menu = st.radio("功能导航", [
        "🏠 仪表盘",
        "📂 智能拆书 & 资料",
        "🎓 AI 课堂 (讲义)",
        "📝 章节特训",
        "⚔️ 全真模考",
        "📊 弱项分析",
        "❌ 错题本",
        "⚙️ 设置中心"
    ], label_visibility="collapsed")
    
    # --- 倒计时 (跨年逻辑) ---
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
# 📂 智能拆书 & 资料 (V3.7 修复版：防重名 + 强壮入库)
# =========================================================
elif menu == "📂 智能拆书 & 资料":
    st.title("📂 资料库管理")
    
    # 辅助函数
    def clean_textbook_content(text):
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            if len(line.strip()) < 3 or line.strip().isdigit(): continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines)

    subjects = get_subjects()
    if not subjects: st.error("请先初始化科目数据"); st.stop()
    
    # --- 1. 顶层选择 (修复同名书籍冲突问题) ---
    c1, c2 = st.columns([1, 2])
    with c1:
        s_name = st.selectbox("1. 所属科目", [s['name'] for s in subjects])
        sid = next(s['id'] for s in subjects if s['name'] == s_name)
    with c2:
        books = get_books(sid)
        # 核心修复：在下拉选项中加入 ID 后缀，防止同名书混淆
        # 格式： "书籍名称 (ID:123)"
        book_map = {f"{b['title']} (ID:{b['id']})": b['id'] for b in books}
        b_opts = ["➕ 上传新资料..."] + list(book_map.keys())
        
        sel_book_label = st.selectbox("2. 选择书籍/文件", b_opts)
    
    st.divider()

    # =====================================================
    # 场景 A: 上传新资料
    # =====================================================
    if "上传新" in sel_book_label:
        st.markdown("#### 📤 第一步：上传与定性")
        doc_type = st.radio("这份文件是？", ["📖 纯教材 (用于学习/出新题)", "📑 习题库/真题集 (用于录入库存)"], horizontal=True)
        up_file = st.file_uploader("拖入 PDF 文件", type="pdf")
        
        if up_file:
            try:
                with pdfplumber.open(up_file) as pdf: total_pages = len(pdf.pages)
                st.success(f"文件已加载：{up_file.name} (共 {total_pages} 页)")
                
                # Session 初始化
                if 'toc_step' not in st.session_state: st.session_state.toc_step = 1
                
                # --- Step 1: AI 分析 ---
                if st.session_state.toc_step == 1:
                    if "纯教材" in doc_type:
                        if st.button("🚀 开始拆解教材"):
                            with st.spinner("AI 正在阅读目录..."):
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
                                    except: st.error("目录解析失败")
                    
                    else: # 习题库
                        ans_mode = st.radio("答案在哪里？", ["🅰️ 紧跟在题目后面", "🅱️ 集中在文件末尾"])
                        user_hint = st.text_input("特殊情况备注", placeholder="例：忽略水印...")
                        
                        if st.button("🚀 开始分析习题结构"):
                            with st.spinner("AI 正在分析试卷结构..."):
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
                                        st.rerun()
                                    except: st.error("结构分析失败")

                # --- Step 2: 确认与入库 ---
                if st.session_state.get('toc_step') == 2 and 'toc_result' in st.session_state:
                    st.markdown("#### 📝 确认分类结构")
                    
                    col_cfg = {
                        "title": "章节/分类名称",
                        "start_page": st.column_config.NumberColumn("题目起始页", min_value=1, format="%d"),
                        "end_page": st.column_config.NumberColumn("题目结束页", min_value=1, format="%d")
                    }
                    
                    is_ans_split = st.session_state.get('ans_mode_cache') and "文件末尾" in st.session_state.get('ans_mode_cache')
                    if is_ans_split:
                        st.warning("⚠️ 检测到答案后置：请补充对应的【答案页码】！")
                        col_cfg["ans_start_page"] = st.column_config.NumberColumn("答案起始页", min_value=1, format="%d")
                        col_cfg["ans_end_page"] = st.column_config.NumberColumn("答案结束页", min_value=1, format="%d")

                    edited_df = st.data_editor(st.session_state.toc_result, column_config=col_cfg, num_rows="dynamic", use_container_width=True)
                    
                    if st.button("💾 执行处理并入库", type="primary"):
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        try:
                            # 1. 建书
                            book_res = supabase.table("books").insert({
                                "user_id": user_id, "subject_id": sid, "title": up_file.name.replace(".pdf",""), "total_pages": total_pages
                            }).execute()
                            bid = book_res.data[0]['id']
                            
                            total_tasks = len(edited_df)
                            for i, row in enumerate(edited_df):
                                status_text.text(f"正在处理：{row['title']}...")
                                
                                # 强制转 int
                                c_start = int(float(row['start_page']))
                                c_end = int(float(row['end_page']))
                                
                                # A. 优先建立章节 (保证结构存在)
                                c_res = supabase.table("chapters").insert({
                                    "book_id": bid, 
                                    "title": row['title'], 
                                    "start_page": c_start, 
                                    "end_page": c_end, 
                                    "user_id": user_id
                                }).execute()
                                cid = c_res.data[0]['id']
                                
                                # B. 尝试提取内容 (即使失败也不影响章节创建)
                                up_file.seek(0)
                                q_text = extract_pdf(up_file, c_start, c_end)
                                
                                # 纯教材模式
                                if "纯教材" in doc_type:
                                    clean_txt = clean_textbook_content(q_text)
                                    if len(clean_txt) > 10:
                                        save_material_v3(cid, clean_txt, user_id)
                                
                                # 习题库模式
                                else:
                                    final_text = q_text
                                    # 拼接答案
                                    if is_ans_split and row.get('ans_start_page', 0) > 0:
                                        a_start = int(float(row['ans_start_page']))
                                        a_end = int(float(row['ans_end_page']))
                                        if a_start > 0:
                                            up_file.seek(0)
                                            a_text = extract_pdf(up_file, a_start, a_end)
                                            final_text += f"\n\n====== 答案参考区域 ======\n{a_text}"
                                    
                                    # AI 提取
                                    if len(final_text) > 50:
                                        p_extract = f"""
                                        任务：提取会计题目。自动对齐题目和答案。
                                        用户备注：{st.session_state.get('ans_mode_cache')}
                                        返回JSON: [{{ "question": "...", "options": ["A.","B."], "answer": "A", "explanation": "..." }}]
                                        文本：{final_text[:25000]}
                                        """
                                        # 增加错误重试
                                        try:
                                            r = call_ai_universal(p_extract)
                                            if r:
                                                cln = r.replace("```json","").replace("```","").strip()
                                                s = cln.find('['); e = cln.rfind(']')+1
                                                qs_data = json.loads(cln[s:e])
                                                fmt_qs = [{"question": q['question'], "options": q['options'], "answer": q['answer'], "explanation": q.get('explanation', ''), "type": "multi" if len(q['answer'])>1 else "single"} for q in qs_data]
                                                save_questions_v3(fmt_qs, cid, user_id, origin="extract")
                                        except: pass
                                
                                progress_bar.progress((i + 1) / total_tasks)
                            
                            st.balloons()
                            st.success(f"🎉 处理完成！")
                            # 清理状态
                            del st.session_state.toc_step
                            del st.session_state.toc_result
                            time.sleep(2)
                            st.rerun() # 强制刷新以显示新书
                            
                        except Exception as e:
                            st.error(f"处理中断: {e}")

            except Exception as e: st.error(f"文件读取错误: {e}")

    # =====================================================
    # 场景 B: 已有书籍管理
    # =====================================================
    elif books:
        # 获取 ID (从 book_map 中查找)
        bid = book_map[sel_book_label]
        
        # 顶部工具栏
        c_tit, c_act = st.columns([5, 1])
        with c_tit: st.markdown(f"### 📘 {sel_book_label.split(' (ID')[0]}")
        with c_act:
            if st.button("🗑️ 删除本书"):
                # 级联删除: Book -> Chapter -> Material/Questions
                # 需确保数据库开启了 ON DELETE CASCADE
                try:
                    supabase.table("books").delete().eq("id", bid).execute()
                    st.toast("书籍已删除")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"删除失败: {e}")

        chapters = get_chapters(bid)
        if not chapters: st.info("本书暂无章节 (请检查上传过程是否出错)")
        else:
            for chap in chapters:
                q_cnt = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", chap['id']).execute().count
                m_cnt = supabase.table("materials").select("id", count="exact").eq("chapter_id", chap['id']).execute().count
                
                with st.expander(f"📑 {chap['title']} (题:{q_cnt} | 教材:{'有' if m_cnt else '无'})"):
                    if m_cnt: st.caption("✅ 教材内容已入库")
                    if q_cnt: st.caption(f"✅ 已收录 {q_cnt} 道题目")
                    
                    if st.button("🗑️ 清空本章数据", key=f"c_{chap['id']}"):
                         supabase.table("materials").delete().eq("chapter_id", chap['id']).execute()
                         supabase.table("question_bank").delete().eq("chapter_id", chap['id']).execute()
                         st.toast("章节内容已清空")
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

# === 📝 章节特训 (刷题) ===
elif menu == "📝 章节特训 (刷题)":
    st.title("📝 章节突破")
    
    # 1. 计时器
    if st.session_state.get('quiz_active'):
        if 'js_start_time' not in st.session_state: st.session_state.js_start_time = int(time.time() * 1000)
        components.html(f"""<div style='position:fixed;top:60px;right:20px;z-index:9999;background:#00C090;color:white;padding:5px 15px;border-radius:20px;font-family:monospace;font-weight:bold'>⏱️ <span id='t'>00:00</span></div><script>setInterval(()=>{{var d=Math.floor((Date.now()-{st.session_state.js_start_time})/1000);document.getElementById('t').innerText=Math.floor(d/60).toString().padStart(2,'0')+':'+(d%60).toString().padStart(2,'0')}},1000)</script>""", height=0)

    # 2. 选区
    if not st.session_state.get('quiz_active'):
        subjects = get_subjects()
        if subjects:
            c1, c2, c3 = st.columns(3)
            with c1: 
                s = st.selectbox("科目", [x['name'] for x in subjects])
                sid = next(x['id'] for x in subjects if x['name']==s)
            with c2:
                books = get_books(sid)
                if not books: st.warning("该科目无书"); st.stop()
                b = st.selectbox("书籍", [x['title'] for x in books])
                bid = next(x['id'] for x in books if x['title']==b)
            with c3:
                chaps = get_chapters(bid)
                if not chaps: st.warning("本书无章节"); st.stop()
                c = st.selectbox("章节", [x['title'] for x in chaps])
                cid = next(x['id'] for x in chaps if x['title']==c)
                
            # 进度条
            try:
                q_res = supabase.table("question_bank").select("id").eq("chapter_id", cid).execute().data
                total_q = len(q_res)
                if total_q > 0:
                    done_res = supabase.table("user_answers").select("question_id").eq("user_id", user_id).eq("is_correct", True).execute().data
                    done_ids = set([d['question_id'] for d in done_res])
                    mastered = len(done_ids.intersection(set([q['id'] for q in q_res])))
                    st.caption(f"📈 进度：{mastered}/{total_q}")
                    st.progress(mastered/total_q)
            except: pass
            
            # 模式选择
            st.divider()
            mode = st.radio("练习策略", ["🎲 刷真题 (从库存抽)", "🧠 AI 基于教材出新题"], horizontal=True)

            if st.button("🚀 开始练习", type="primary", use_container_width=True):
                st.session_state.quiz_cid = cid
                st.session_state.js_start_time = int(time.time() * 1000)
                
                # A: 刷真题
                if "真题" in mode:
                    if total_q == 0: st.error("无题库")
                    else:
                        qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).limit(50).execute().data
                        random.shuffle(qs)
                        st.session_state.quiz_data = qs[:10]
                        st.session_state.q_idx = 0
                        st.session_state.quiz_active = True
                        st.rerun()
                # B: AI 出题
                else:
                    mats = supabase.table("materials").select("content").eq("chapter_id", cid).execute().data
                    if not mats: st.error("无教材")
                    else:
                        txt = "\n".join([m['content'] for m in mats])
                        with st.spinner("AI 出题中..."):
                            p = f"出3道单选。内容：{txt[:8000]}。格式JSON：[{{'content':'..','options':['A..'],'correct_answer':'A','explanation':'..'}}]。"
                            res = call_ai_universal(p)
                            if res:
                                try:
                                    clean = res.replace("```json","").replace("```","").strip()
                                    d = json.loads(clean)
                                    db_qs = [{'chapter_id': cid, 'user_id': user_id, 'type': 'single', 'content': x['content'], 'options': x['options'], 'correct_answer': x['correct_answer'], 'explanation': x['explanation'], 'origin': 'ai_gen'} for x in d]
                                    supabase.table("question_bank").insert(db_qs).execute()
                                    st.session_state.quiz_data = d
                                    st.session_state.q_idx = 0
                                    st.session_state.quiz_active = True
                                    st.rerun()
                                except: st.error("生成失败")

    # 3. 做题交互
    if st.session_state.get('quiz_active'):
        idx = st.session_state.q_idx
        total = len(st.session_state.quiz_data)
        
        if idx >= total:
            st.balloons(); st.success("完成！")
            if st.button("返回"): st.session_state.quiz_active = False; st.rerun()
        else:
            q = st.session_state.quiz_data[idx]
            q_text = q.get('content') or q.get('question')
            q_ans = (q.get('correct_answer') or q.get('answer') or "").upper().replace(" ","").replace(",","")
            q_opts = q.get('options', [])
            
            st.progress((idx+1)/total)
            st.markdown(f"<div class='css-card'><h4>Q{idx+1}: {q_text}</h4></div>", unsafe_allow_html=True)
            
            # 智能多选
            is_multi = len(q_ans) > 1 or q.get('type') == 'multi'
            user_val = ""
            
            if is_multi:
                st.caption("【多选题】")
                opts = []
                for o in q_opts:
                    if st.checkbox(o, key=f"m_{idx}_{o}"): opts.append(o[0])
                user_val = "".join(sorted(opts))
            else:
                sel = st.radio("单选", q_opts, key=f"s_{idx}", label_visibility="collapsed")
                user_val = sel[0] if sel else ""
            
            sub_key = f"sub_{idx}"
            if sub_key not in st.session_state: st.session_state[sub_key] = False
            
            if st.button("✅ 提交", use_container_width=True) and not st.session_state[sub_key]:
                st.session_state[sub_key] = True
            
            if st.session_state[sub_key]:
                if user_val == q_ans:
                    st.markdown("<div class='success-box'>🎉 正确</div>", unsafe_allow_html=True)
                    if q.get('id'): supabase.table("user_answers").insert({"user_id": user_id, "question_id": q['id'], "user_response": user_val, "is_correct": True}).execute()
                else:
                    st.error(f"❌ 错误。答案：{q_ans}")
                    if q.get('id'):
                        exist = supabase.table("user_answers").select("id").eq("user_id", user_id).eq("question_id", q['id']).eq("is_correct", False).execute().data
                        if exist: supabase.table("user_answers").update({"created_at": datetime.datetime.now().isoformat()}).eq("id", exist[0]['id']).execute()
                        else: supabase.table("user_answers").insert({"user_id": user_id, "question_id": q['id'], "user_response": user_val, "is_correct": False}).execute()
                
                st.info(f"解析：{q.get('explanation')}")
                
                # AI 举例
                ck = f"qc_{idx}"
                if ck not in st.session_state: st.session_state[ck] = []
                if st.button("🤔 AI 举例"):
                    r = call_ai_universal(f"解释：{q_text}。答案{q_ans}。解析{q.get('explanation')}")
                    if r: st.session_state[ck].append({"role":"model", "content":r})
                
                for m in st.session_state[ck]:
                    st.markdown(f"<div class='chat-{'ai' if m['role']=='model' else 'user'}'>{m['content']}</div>", unsafe_allow_html=True)
                
                if st.session_state[ck]:
                    ask = st.text_input("追问", key=f"ak_{idx}")
                    if st.button("发送", key=f"sk_{idx}") and ask:
                        st.session_state[ck].append({"role":"user", "content":ask})
                        r = call_ai_universal(ask, history=st.session_state[ck][:-1])
                        st.session_state[ck].append({"role":"model", "content":r})
                        st.rerun()

            st.markdown("---")
            if st.button("➡️ 下一题", use_container_width=True):
                st.session_state.q_idx += 1; st.rerun()

# === ⚔️ 全真模考 ===
elif menu == "⚔️ 全真模考":
    st.title("⚔️ 全真模拟")
    if 'exam_sess' not in st.session_state: st.session_state.exam_sess = None
    
    if not st.session_state.exam_sess:
        # 配置页
        subjects = get_subjects()
        if subjects:
            sn = st.selectbox("科目", [x['name'] for x in subjects])
            sid = next(x['id'] for x in subjects if x['name']==sn)
            if st.button("🚀 生成试卷"):
                books = get_books(sid)
                bids = [b['id'] for b in books]
                if bids:
                    cids = [c['id'] for c in supabase.table("chapters").select("id").in_("book_id", bids).execute().data]
                    qs = supabase.table("question_bank").select("*").in_("chapter_id", cids).limit(100).execute().data
                    if len(qs)>=5:
                        random.shuffle(qs)
                        st.session_state.exam_sess = {"paper":qs[:10], "ans":{}, "start":int(time.time()*1000), "sub":False}
                        st.rerun()
                    else: st.error("题目不足")
                else: st.error("无书")
    elif not st.session_state.exam_sess['sub']:
        # 考试中
        sess = st.session_state.exam_sess
        end_ms = sess['start'] + 60*60*1000
        components.html(f"<div style='position:fixed;top:60px;right:20px;z-index:9999;background:#dc3545;color:white;padding:5px 15px;border-radius:20px;font-family:monospace'>⏳ <span id='t'></span></div><script>setInterval(()=>{{var d=Math.floor(({end_ms}-Date.now())/1000);document.getElementById('t').innerText=d>0?Math.floor(d/60)+':'+(d%60):'00:00'}},1000)</script>", height=0)
        
        with st.form("ex"):
            for i, q in enumerate(sess['paper']):
                st.markdown(f"**{i+1}. {q['content']}**")
                qa = (q.get('correct_answer') or "").upper().replace(" ","")
                if len(qa)>1:
                    opts = []
                    for o in q['options']:
                        if st.checkbox(o, key=f"em_{i}_{o}"): opts.append(o[0])
                    sess['ans'][i] = "".join(sorted(opts))
                else:
                    v = st.radio("选", q['options'], key=f"es_{i}", label_visibility="collapsed")
                    if v: sess['ans'][i] = v[0]
                st.divider()
            if st.form_submit_button("交卷"):
                sess['sub'] = True
                st.rerun()
    else:
        # 结果
        sess = st.session_state.exam_sess
        sc = 0
        det = []
        for i, q in enumerate(sess['paper']):
            u = sess['ans'].get(i,"")
            std = (q.get('correct_answer') or "").upper().replace(" ","")
            ok = (u==std)
            if ok: sc += 10
            det.append({"q":q['content'], "u":u, "std":std, "ok":ok, "exp":q.get('explanation')})
            if not ok: 
                try: supabase.table("user_answers").insert({"user_id":user_id, "question_id":q['id'], "user_response":u, "is_correct":False}).execute()
                except: pass
        
        st.balloons()
        st.markdown(f"<h1 style='text-align:center; color:#00C090'>{sc} 分</h1>", unsafe_allow_html=True)
        for d in det:
            with st.expander(f"{'✅' if d['ok'] else '❌'} {d['q'][:20]}..."):
                st.write(d['q'])
                st.error(f"你: {d['u']}"); st.success(f"标: {d['std']}")
                st.info(d['exp'])
        if st.button("退出"):
            st.session_state.exam_sess = None
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

# === ⚙️ 设置中心 ===
elif menu == "⚙️ 设置中心":
    st.title("⚙️ 设置")
    # 连通测试
    if st.button("📡 测试 AI"):
        r = call_ai_universal("Hi")
        if "Error" in r: st.error(r)
        else: st.success(f"连接成功: {r}")
        
    # 超时
    to = st.slider("超时时间", 10, 300, 60)
    if st.button("保存设置"):
        update_settings(user_id, {"ai_timeout": to})
        st.success("已保存")
    
    st.divider()
    if st.button("🗑️ 清空所有数据"):
        supabase.table("user_answers").delete().eq("user_id", user_id).execute()
        st.success("已清空")



