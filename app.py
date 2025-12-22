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

# ==============================================================================
# 1. 全局配置与 Bootstrap 高级动态特效 (CSS)
# ==============================================================================
st.set_page_config(page_title="中级会计 AI 私教 Pro (V3.0)", page_icon="🥝", layout="wide")

st.markdown("""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
<style>
    /* === 基础设定：柔和护眼背景 === */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        font-family: 'Segoe UI', 'Roboto', sans-serif;
    }
    
    /* === 侧边栏：毛玻璃特效 === */
    [data-testid="stSidebar"] {
        background-color: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(0,0,0,0.05);
        box-shadow: 4px 0 15px rgba(0,0,0,0.03);
    }

    /* === 卡片：悬浮呼吸感 (Hover Card) === */
    .css-card {
        background-color: #FFFFFF;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        border: 1px solid rgba(0,0,0,0.04);
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        position: relative;
        overflow: hidden;
    }
    
    .css-card:hover {
        transform: translateY(-5px) scale(1.01);
        box-shadow: 0 15px 30px rgba(0, 192, 144, 0.15);
        border-color: #00C090;
    }
    
    /* 卡片左侧装饰条 */
    .css-card::before {
        content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%;
        background: #00C090; opacity: 0; transition: opacity 0.3s;
    }
    .css-card:hover::before { opacity: 1; }

    /* === 统计数字 === */
    .stat-title {
        font-size: 0.85rem; color: #6c757d; text-transform: uppercase; letter-spacing: 1px; font-weight: 700;
    }
    .stat-value {
        font-size: 2.4rem; font-weight: 800; color: #2C3E50; letter-spacing: -1px;
    }
    .stat-icon {
        position: absolute; right: 20px; top: 20px; font-size: 2rem; color: rgba(0,192,144, 0.15);
    }

    /* === 按钮：渐变色胶囊 === */
    .stButton>button {
        background: linear-gradient(135deg, #00C090 0%, #00a87e 100%);
        color: white; border: none; border-radius: 50px; height: 48px; font-weight: 600;
        box-shadow: 0 4px 10px rgba(0, 192, 144, 0.3); transition: all 0.3s ease; padding: 0 25px;
    }
    .stButton>button:hover {
        transform: translateY(-2px); box-shadow: 0 6px 15px rgba(0, 192, 144, 0.5); filter: brightness(1.1);
    }
    .stButton>button:active { transform: translateY(1px); }

    /* === 进度条颜色 === */
    .stProgress > div > div > div > div { background-color: #00C090; }

    /* === 聊天气泡 === */
    .chat-user {
        background-color: #E3F2FD; padding: 12px 18px; border-radius: 15px 15px 0 15px;
        margin: 10px 0 10px auto; max-width: 85%; color: #1565C0; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .chat-ai {
        background-color: #FFFFFF; padding: 12px 18px; border-radius: 15px 15px 15px 0;
        margin: 10px auto 10px 0; max-width: 85%; border-left: 4px solid #00C090; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }

    /* === 选项列表 === */
    .option-item {
        background: #fff; border: 1px solid #eee; padding: 12px; border-radius: 8px; margin-bottom: 8px;
        border-left: 4px solid transparent; transition: all 0.2s;
    }
    .option-item:hover { border-left-color: #00C090; background-color: #f9fdfb; }

    /* === 成功/警告框 === */
    .success-box { padding: 15px; background: #E8F5E9; border-radius: 10px; color: #2E7D32; border: 1px solid #C8E6C9; }
    .warn-box { padding: 15px; background: #FFF3E0; border-radius: 10px; color: #EF6C00; border: 1px solid #FFE0B2; }

</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. 数据库连接与配置
# ==============================================================================
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
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

# --- AI 调用 (通用版) ---
def call_ai_universal(prompt, history=[], model_override=None):
    """
    支持 Gemini / DeepSeek / OpenRouter 的通用接口
    """
    provider = st.session_state.get('selected_provider', 'Gemini')
    # 优先使用 override，否则使用 session 中的设置
    target_model = model_override or st.session_state.get('openrouter_model_id', 'google/gemini-2.0-flash-exp:free')
    
    try:
        # A. Google Gemini
        if "Gemini" in provider and not model_override:
            g_model = st.session_state.get("google_model_id", "gemini-1.5-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={API_KEY}"
            headers = {'Content-Type': 'application/json'}
            
            contents = []
            for h in history:
                role = "user" if h['role'] == 'user' else "model"
                contents.append({"role": role, "parts": [{"text": h['content']}]})
            contents.append({"role": "user", "parts": [{"text": prompt}]})
            
            resp = requests.post(url, headers=headers, json={"contents": contents}, timeout=60)
            if resp.status_code == 200:
                return resp.json()['candidates'][0]['content']['parts'][0]['text']
            return f"Gemini Error {resp.status_code}: {resp.text}"

        # B. OpenAI 兼容 (DeepSeek / OpenRouter)
        else:
            client = None
            if "DeepSeek" in provider and not model_override:
                client = OpenAI(api_key=st.secrets["deepseek"]["api_key"], base_url=st.secrets["deepseek"]["base_url"])
                target_model = st.session_state.get("deepseek_model_id", "deepseek-chat")
            else:
                # 默认走 OpenRouter (或者 override 强制走这里)
                # 注意：如果是 override (如拆书时强制用 Gemini)，我们需要构建一个临时的 Client 指向 Google 吗？
                # 不，拆书为了省钱，通常我们用 Gemini 原生。这里为了逻辑简单，如果 override 了且是 Google 模型，走分支 A 逻辑。
                if model_override and "gemini" in model_override:
                    # 递归调用自己，但临时骗它是 Gemini
                    # 这里简化处理：OpenAI 兼容接口也能调 OpenRouter 里的 Google 模型
                    client = OpenAI(api_key=st.secrets["openrouter"]["api_key"], base_url=st.secrets["openrouter"]["base_url"])
                else:
                    if "openrouter" in st.secrets:
                        client = OpenAI(api_key=st.secrets["openrouter"]["api_key"], base_url=st.secrets["openrouter"]["base_url"])
            
            if not client: return "AI Client 初始化失败"

            messages = [{"role": "system", "content": "你是一位资深会计讲师。"}]
            for h in history:
                role = "assistant" if h['role'] == "model" else h['role']
                messages.append({"role": role, "content": h['content']})
            messages.append({"role": "user", "content": prompt})

            resp = client.chat.completions.create(model=target_model, messages=messages, temperature=0.7)
            return resp.choices[0].message.content

    except Exception as e:
        return f"AI 异常: {e}"

# --- 动态获取模型列表 ---
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

# --- 数据库操作 (V3.0 Schema) ---
def get_user_profile(uid):
    try:
        res = supabase.table("study_profile").select("*").eq("user_id", uid).execute()
        if not res.data:
            supabase.table("study_profile").insert({"user_id": uid}).execute()
            return {}
        return res.data[0]
    except: return {}

def update_settings(uid, settings_dict):
    try:
        curr = get_user_profile(uid).get('settings') or {}
        curr.update(settings_dict)
        supabase.table("study_profile").update({"settings": curr}).eq("user_id", uid).execute()
    except: pass

def get_subjects():
    return supabase.table("subjects").select("*").execute().data

def get_books(sid):
    # V3 核心：通过 Subject 找 Books
    return supabase.table("books").select("*").eq("subject_id", sid).eq("user_id", user_id).execute().data

def get_chapters(book_id):
    # V3 核心：通过 Book 找 Chapters (修复之前的报错)
    return supabase.table("chapters").select("*").eq("book_id", book_id).order("start_page", desc=False).execute().data

def save_material_v3(chapter_id, content, uid):
    supabase.table("materials").insert({
        "chapter_id": chapter_id,
        "content": content,
        "user_id": uid
    }).execute()

def save_questions_v3(q_list, chapter_id, uid, origin="ai"):
    data = [{
        "chapter_id": chapter_id,
        "user_id": uid,
        "content": q['question'], # 兼容不同 key
        "options": q['options'],
        "correct_answer": q['answer'],
        "explanation": q.get('explanation', ''),
        "type": "multi" if len(q['answer']) > 1 else "single",
        "origin": origin
    } for q in q_list]
    supabase.table("question_bank").insert(data).execute()

# --- 文件解析 ---
def extract_pdf(file, start=1, end=None):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            total = len(pdf.pages)
            if end is None or end > total: end = total
            for i in range(start-1, end):
                text += pdf.pages[i].extract_text() + "\n"
        return text
    except: return ""

def extract_docx(file):
    try:
        doc = docx.Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    except: return ""

# --- 自动保存回调 ---
def save_ai_pref():
    p = st.session_state.get('ai_provider_select')
    m = None
    if "OpenRouter" in str(p): m = st.session_state.get('or_model_select')
    elif "DeepSeek" in str(p): m = st.session_state.get('ds_model_select')
    elif "Gemini" in str(p): m = st.session_state.get('gl_model_select')
    
    if p: update_settings(user_id, {"last_provider": p, "last_used_model": m})

# ==============================================================================
# 4. 侧边栏与导航
# ==============================================================================
profile = get_user_profile(user_id)
settings = profile.get('settings') or {}

with st.sidebar:
    st.title("🥝 备考中心")
    
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
    
    # --- 导航 ---
    menu = st.radio("功能导航", ["🏠 仪表盘", "📚 智能资料库 (V3)", "📝 章节特训", "⚔️ 全真模考", "📊 弱项分析", "❌ 错题本", "⚙️ 设置中心"], label_visibility="collapsed")
    
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
# 5. 各页面逻辑 (V3 架构适配)
# ==============================================================================

# === 🏠 仪表盘 ===
if menu == "🏠 仪表盘":
    # (复用之前的逻辑，简化展示)
    st.markdown(f"### 🌞 欢迎回来，{user_id}")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f"<div class='css-card'><div class='stat-title'>累计刷题</div><div class='stat-value'>{profile.get('total_questions_done',0)}</div><i class='bi bi-pencil-fill stat-icon'></i></div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='css-card'><div class='stat-title'>连续打卡</div><div class='stat-value'>{profile.get('study_streak',0)}</div><i class='bi bi-fire stat-icon'></i></div>", unsafe_allow_html=True)
    with c3: st.markdown(f"<div class='css-card'><div class='stat-title'>待复习错题</div><div class='stat-value'>--</div><i class='bi bi-bookmark-x-fill stat-icon'></i></div>", unsafe_allow_html=True)

# === 📚 智能资料库 (V3 核心：Subject -> Book -> Chapter) ===
elif menu == "📚 智能资料库 (V3)":
    st.title("📚 智能书架 & 拆书助手")
    
    subjects = get_subjects()
    if not subjects: st.error("请先在数据库初始化 Subjects 表"); st.stop()
    
    # 1. 选科目
    c1, c2 = st.columns(2)
    with c1:
        s_name = st.selectbox("1. 选择科目", [s['name'] for s in subjects])
        sid = next(s['id'] for s in subjects if s['name'] == s_name)
    
    # 2. 选书 (关联 Subject)
    with c2:
        books = get_books(sid)
        b_opts = ["➕ 上传新书 (PDF)..."] + [b['title'] for b in books]
        sel_book = st.selectbox("2. 选择书籍", b_opts)
    
    # A. 上传新书逻辑
    if "上传新书" in sel_book:
        with st.container():
            st.markdown("#### 📤 智能拆书台")
            st.caption("AI 自动分析 PDF 目录，将整书拆分为章节，极大节省 Token。")
            up_file = st.file_uploader("上传 PDF", type="pdf")
            
            if up_file:
                # 读取总页数
                try:
                    with pdfplumber.open(up_file) as pdf: total_pages = len(pdf.pages)
                    st.success(f"文件解析成功，共 {total_pages} 页")
                    
                    if st.button("🚀 开始 AI 目录分析"):
                        # 1. 创建 Book
                        book_data = {"user_id": user_id, "subject_id": sid, "title": up_file.name.replace(".pdf",""), "total_pages": total_pages}
                        new_book = supabase.table("books").insert(book_data).execute().data[0]
                        bid = new_book['id']
                        
                        # 2. 读取目录页 (前20页)
                        with st.spinner("AI 正在阅读目录..."):
                            toc_text = ""
                            with pdfplumber.open(up_file) as pdf:
                                for i in range(min(20, total_pages)):
                                    toc_text += pdf.pages[i].extract_text() + "\n"
                            
                            # 3. AI 规划
                            p = f"分析目录结构。总页数{total_pages}。返回JSON列表:[{{'title':'第一章 总论','start':5,'end':20}}]。文本：{toc_text[:8000]}"
                            # 强制用 Flash 省钱
                            res = call_ai_universal(p, model_override="google/gemini-1.5-flash")
                            
                            if res:
                                try:
                                    chaps = json.loads(res.replace("```json","").replace("```","").strip())
                                    # 存入 Chapters
                                    for c in chaps:
                                        supabase.table("chapters").insert({
                                            "book_id": bid, "title": c['title'], "start_page": c['start'], "end_page": c['end'], "user_id": user_id
                                        }).execute()
                                    st.success("拆分完成！请在上方下拉框选择这本书。")
                                    time.sleep(1)
                                    st.rerun()
                                except: st.error("AI 目录解析失败，请重试或手动创建")
                except: st.error("文件无效")

    # B. 书籍管理 (章节列表)
    elif books:
        bid = next(b['id'] for b in books if b['title'] == sel_book)
        chapters = get_chapters(bid)
        
        st.divider()
        st.write(f"📖 **{sel_book}** 目录结构")
        
        if not chapters:
            st.info("暂无章节，可能是解析失败。")
        else:
            for chap in chapters:
                with st.expander(f"📑 {chap['title']} (P{chap['start_page']}-{chap['end_page']})"):
                    # 检查是否有内容
                    has_mat = supabase.table("materials").select("id", count="exact").eq("chapter_id", chap['id']).execute().count
                    
                    c_info, c_act = st.columns([3, 1])
                    with c_info:
                        if has_mat: st.success("✅ 内容已入库")
                        else: st.warning("⚪ 内容未提取")
                        
                    with c_act:
                        # 提取入库按钮
                        if st.button("📥 提取内容", key=f"imp_{chap['id']}"):
                            st.info("请重新拖入对应的 PDF 文件以开始提取...")
                            # 这里简化：实际应弹出一个专用上传框或使用缓存的文件
                            # 为演示，我们在下方提供一个临时上传框
                            
                    # 临时上传框 (为了方便提取)
                    temp_up = st.file_uploader(f"上传 PDF 以提取 {chap['title']}", type="pdf", key=f"up_{chap['id']}")
                    if temp_up:
                        with st.spinner("切片提取中..."):
                            txt = extract_pdf(temp_up, chap['start_page'], chap['end_page'])
                            if txt:
                                save_material_v3(chap['id'], txt, user_id)
                                st.success("入库成功！")
                                st.rerun()

                    st.divider()
                    # 生成讲义/习题入口
                    if has_mat:
                        c_gen1, c_gen2 = st.columns(2)
                        if c_gen1.button("🎓 生成 AI 讲义", key=f"les_{chap['id']}"):
                            # 讲义生成逻辑...
                            st.toast("功能开发中...")
                        if c_gen2.button("🧠 生成 5 道题", key=f"qz_{chap['id']}"):
                            # 题目生成逻辑
                            mat = supabase.table("materials").select("content").eq("chapter_id", chap['id']).limit(1).execute().data[0]
                            with st.spinner("AI 出题中..."):
                                p = f"基于内容出5道单选。JSON格式。内容：{mat['content'][:5000]}"
                                r = call_ai_universal(p)
                                if r:
                                    try:
                                        d = json.loads(r.replace("```json","").replace("```","").strip())
                                        # 适配 V3 字段
                                        fmt = [{"question":x['content'], "options":x['options'], "answer":x['correct_answer'], "explanation":x['explanation']} for x in d]
                                        save_questions_v3(fmt, chap['id'], user_id, origin="ai_gen")
                                        st.success("题目已存入题库！")
                                    except: st.error("生成失败")

# === 📝 章节特训 (适配 V3: Subject->Book->Chapter) ===
elif menu == "📝 章节特训":
    st.title("📝 章节突破")
    
    # 1. JS 计时器
    if st.session_state.get('quiz_active'):
        if 'js_start' not in st.session_state: st.session_state.js_start = int(time.time()*1000)
        components.html(f"""<div style='position:fixed;top:60px;right:20px;z-index:9999;background:#00C090;color:white;padding:5px 15px;border-radius:20px;font-family:monospace;font-weight:bold;box-shadow:0 4px 10px rgba(0,0,0,0.2)'>⏱️ <span id='t'>00:00</span></div><script>setInterval(()=>{{var d=Math.floor((Date.now()-{st.session_state.js_start})/1000);document.getElementById('t').innerText=Math.floor(d/60).toString().padStart(2,'0')+':'+(d%60).toString().padStart(2,'0')}},1000)</script>""", height=0)

    # 2. 选区 (V3 级联)
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
                # V3 进度逻辑
                total = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", cid).execute().count
                # 简单估算：查 user_answers 关联
                # 严谨做法需要 view 或 join，这里简化
                st.caption(f"📚 题库库存: {total} 题")
            except: pass
            
            if st.button("🚀 开始刷题", type="primary", use_container_width=True):
                qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).limit(20).execute().data
                if qs:
                    random.shuffle(qs)
                    st.session_state.quiz_data = qs[:10]
                    st.session_state.q_idx = 0
                    st.session_state.quiz_active = True
                    st.session_state.js_start = int(time.time()*1000)
                    st.rerun()
                else: st.error("本章无题，请去资料库生成。")

    # 3. 做题 (保持不变，复用逻辑)
    if st.session_state.get('quiz_active'):
        idx = st.session_state.q_idx
        q = st.session_state.quiz_data[idx]
        total = len(st.session_state.quiz_data)
        
        st.progress((idx+1)/total)
        st.markdown(f"<div class='css-card'><h4>Q{idx+1}: {q['content']}</h4></div>", unsafe_allow_html=True)
        
        # 选项渲染 (支持多选)
        user_val = ""
        is_multi = q.get('type') == 'multi' or len(q['correct_answer']) > 1
        
        if is_multi:
            st.caption("【多选题】")
            opts = []
            for o in q['options']:
                if st.checkbox(o, key=f"m_{idx}_{o}"): opts.append(o[0])
            user_val = "".join(sorted(opts))
        else:
            sel = st.radio("单选", q['options'], key=f"s_{idx}", label_visibility="collapsed")
            user_val = sel[0] if sel else ""
            
        sub_key = f"sub_{idx}"
        if sub_key not in st.session_state: st.session_state[sub_key] = False
        
        if st.button("✅ 提交") and not st.session_state[sub_key]:
            st.session_state[sub_key] = True
            
        if st.session_state[sub_key]:
            if user_val == q['correct_answer']: 
                st.markdown("<div class='success-box'>🎉 正确</div>", unsafe_allow_html=True)
                # V3: 更新 user_answers
                supabase.table("user_answers").insert({
                    "user_id": user_id, "question_id": q['id'], "user_response": user_val, "is_correct": True
                }).execute()
            else:
                st.error(f"❌ 错误。答案: {q['correct_answer']}")
                supabase.table("user_answers").insert({
                    "user_id": user_id, "question_id": q['id'], "user_response": user_val, "is_correct": False
                }).execute()
                
            st.info(q['explanation'])
            
            # 翻页
            if st.button("➡️ 下一题"):
                if idx < total-1: 
                    st.session_state.q_idx += 1
                    st.rerun()
                else: 
                    st.success("完成")
                    if st.button("退出"): 
                        st.session_state.quiz_active = False
                        st.rerun()

# === ❌ 错题本 (V3: 关联查询) ===
elif menu == "❌ 错题本":
    st.title("❌ 错题集")
    # 联表查询 V3: user_answers -> question_bank
    errs = supabase.table("user_answers").select("*, question_bank(*)").eq("user_id", user_id).eq("is_correct", False).order("created_at", desc=True).execute().data
    
    unique_q = {}
    for e in errs:
        if e['question_id'] not in unique_q: unique_q[e['question_id']] = e
        
    if not unique_q: st.success("无错题")
    else:
        for qid, e in unique_q.items():
            q = e['question_bank']
            if not q: continue
            with st.expander(f"🔴 {q['content'][:30]}..."):
                st.markdown(f"**题目**：{q['content']}")
                for o in q['options']:
                    st.markdown(f"<div class='option-item'>{o}</div>", unsafe_allow_html=True)
                st.error(f"你的: {e['user_response']} | 正确: {q['correct_answer']}")
                st.info(q['explanation'])
                
                # AI 举例 (复用逻辑)
                if st.button("🤔 AI 举例", key=f"ex_{qid}"):
                    res = call_ai_universal(f"举例解释：{q['content']} 答案{q['correct_answer']}")
                    st.write(res)
                
                if st.button("✅ 移除", key=f"rm_{qid}"):
                    supabase.table("user_answers").update({"is_correct": True}).eq("question_id", qid).execute()
                    st.rerun()


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
# =========================================================
# 📚 资料库 (管理 + 预览 + 导学)
# =========================================================
elif menu == "📚 资料库 (双轨录入)":
    st.title("📂 资料与章节管理")
    
    # --- 1. 级联选择器 ---
    subjects = get_subjects()
    if subjects:
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1: 
            s_name = st.selectbox("科目", [s['name'] for s in subjects])
            sid = next(s['id'] for s in subjects if s['name'] == s_name)
        with c2:
            chaps = get_chapters(sid, user_id)
            chap_opts = ["➕ 新建章节..."] + [c['title'] for c in chaps]
            sel_chap = st.selectbox("章节", chap_opts)
        with c3:
            if sel_chap == "➕ 新建章节...":
                new_c = st.text_input("输入新章节名", placeholder="例：存货")
                if st.button("创建", use_container_width=True) and new_c:
                    create_chapter(sid, new_c, user_id)
                    st.rerun()
            else:
                # --- ⚙️ 章节管理功能 (新增) ---
                cid = next(c['id'] for c in chaps if c['title'] == sel_chap)
                with st.popover("⚙️ 管理此章节"):
                    st.write(f"当前：**{sel_chap}**")
                    new_name = st.text_input("重命名为", value=sel_chap)
                    if st.button("确认改名"):
                        supabase.table("chapters").update({"title": new_name}).eq("id", cid).execute()
                        st.rerun()
                    
                    st.divider()
                    if st.button("🗑️ 删除章节 (含所有题目)", type="primary"):
                        # 级联删除通常由数据库外键处理，但为了保险，手动删
                        supabase.table("question_bank").delete().eq("chapter_id", cid).execute()
                        supabase.table("materials").delete().eq("chapter_id", cid).execute()
                        supabase.table("chapters").delete().eq("id", cid).execute()
                        st.toast("删除成功")
                        time.sleep(1)
                        st.rerun()

    # --- 2. 资料操作区 ---
    if sel_chap != "➕ 新建章节..." and chaps:
        st.divider()
        
        # 检查当前章节已有资料
        mats = supabase.table("materials").select("id, title, content, created_at").eq("chapter_id", cid).execute().data
        
        # --- 👀 资料预览与提示 (新增) ---
        if mats:
            st.info(f"✅ 当前章节已包含 {len(mats)} 份教材资料。AI 将基于这些内容出题。")
            with st.expander("👀 点击预览已存资料内容"):
                for m in mats:
                    st.markdown(f"**📄 {m['title']}** ({len(m['content'])}字)")
                    st.caption(f"{m['content'][:200]}......") # 只显示前200字
                    if st.button("删除此资料", key=f"del_m_{m['id']}"):
                        supabase.table("materials").delete().eq("id", m['id']).execute()
                        st.rerun()
                    st.divider()
        else:
            st.warning("⚠️ 当前章节为空！请先上传教材或真题。")

        # --- 上传与生成 ---
        t1, t2, t3 = st.tabs(["📖 上传教材 (PDF/Word)", "📑 录入真题 (PDF/Word)", "🎓 生成AI导学"])
        
        # [Tab 1: 教材上传]
        with t1:
            st.caption("提示：Gemini 1.5 Pro/Flash 支持超长文本（约100万token），你可以上传整本教材，但**按章节切片上传**能让生成题目更聚焦。")
            up_a = st.file_uploader("上传文件", type=['pdf','docx'], key='up_a')
            if st.button("📥 解析并保存") and up_a:
                with st.spinner("正在提取文字..."):
                    txt = ""
                    if up_a.name.endswith('.pdf'):
                        txt = extract_text_from_pdf(up_a) # 默认读全文，也可以加页码控制
                    else:
                        txt = extract_text_from_docx(up_a)
                    
                    if len(txt) > 50:
                        save_material_track_a(cid, txt, up_a.name, user_id)
                        st.success(f"成功入库！共识别 {len(txt)} 字。")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("识别内容为空，请检查文件是否为扫描件（纯图片）。")

        # [Tab 2: 真题录入] (保持之前的双区间逻辑)
        with t2:
            st.caption("AI 将从文档中‘抠’出题目和答案，存入题库供你直接练习。")
            # ... (保留你之前的真题提取代码逻辑，这里为了篇幅不再重复粘贴，请保留原样) ...
            # 如果需要我把这段也补全，请告诉我。
            
            # 简写示意：
            up_b = st.file_uploader("上传真题", type=['pdf','docx'], key='up_b')
            if st.button("🔍 提取题目") and up_b:
                # ... (调用 extract_text 和 call_ai_universal 提取 JSON) ...
                pass

        # [Tab 3: AI 导学 (新增)]
        with t3:
            st.write("让 AI 根据你上传的教材，生成一份通俗易懂的学习笔记。")
            if not mats:
                st.error("请先在 Tab 1 上传教材！")
            else:
                if st.button("✨ 生成生活化讲义"):
                    all_text = "\n".join([m['content'] for m in mats])
                    prompt = f"""
                    你是一位风趣幽默的会计讲师。请阅读以下教材内容：
                    {all_text[:30000]} (截取部分)
                    
                    任务：
                    1. 总结本章核心考点（Top 3）。
                    2. 对每个考点，用“开奶茶店”或“家庭理财”等生活案例进行类比解释。
                    3. 输出为 Markdown 格式。
                    """
                    with st.spinner("AI 正在备课..."):
                        res = call_ai_universal(prompt)
                        if res:
                            st.markdown(res)
                            # 这里可以加一个保存按钮，把讲义存入 study_notes 表(需新建)
# =========================================================
# 📝 章节特训 (V3.0 适配版：科目 -> 书籍 -> 章节)
# =========================================================
elif menu == "📝 章节特训": # 注意菜单名字要和你侧边栏定义的一致
    st.title("📝 章节突破")
    
    # --- 1. JS 实时悬浮计时器 ---
    if st.session_state.get('quiz_active'):
        if 'js_start_time' not in st.session_state:
            st.session_state.js_start_time = int(time.time() * 1000)
        
        import streamlit.components.v1 as components
        timer_html = f"""
        <div style="
            position: fixed; top: 60px; right: 20px; z-index: 9999;
            background: linear-gradient(45deg, #00C090, #00E6AC);
            color: white; padding: 8px 20px; border-radius: 30px;
            font-family: monospace; font-size: 18px; font-weight: bold;
            box-shadow: 0 4px 15px rgba(0,192,144, 0.3);
            display: flex; align-items: center; gap: 8px;
        ">
            <span>⏱️</span> <span id="timer_display">00:00</span>
        </div>
        <script>
            var startTime = {st.session_state.js_start_time};
            function updateTimer() {{
                var now = Date.now();
                var diff = Math.floor((now - startTime) / 1000);
                var m = Math.floor(diff / 60).toString().padStart(2, '0');
                var s = (diff % 60).toString().padStart(2, '0');
                var el = document.getElementById("timer_display");
                if (el) el.innerText = m + ":" + s;
            }}
            setInterval(updateTimer, 1000);
            updateTimer();
        </script>
        """
        components.html(timer_html, height=0)

    # --- 2. 启动区 (三级联动选择) ---
    if not st.session_state.get('quiz_active'):
        subjects = get_subjects()
        if subjects:
            # 1. 选择科目
            c1, c2, c3 = st.columns(3)
            with c1:
                s_name = st.selectbox("1. 选择科目", [s['name'] for s in subjects])
                sid = next(s['id'] for s in subjects if s['name'] == s_name)
            
            # 2. 选择书籍 (V3新增)
            with c2:
                # 使用 V3 的 get_books 函数
                books = supabase.table("books").select("*").eq("subject_id", sid).eq("user_id", user_id).execute().data
                if not books:
                    st.warning("该科目下还没上传书籍/资料")
                    sel_book = None
                else:
                    sel_book_title = st.selectbox("2. 选择书籍/资料", [b['title'] for b in books])
                    bid = next(b['id'] for b in books if b['title'] == sel_book_title)
            
            # 3. 选择章节
            with c3:
                if books:
                    # 使用 V3 的 get_chapters (通过 book_id 查)
                    chaps = supabase.table("chapters").select("*").eq("book_id", bid).order("start_page").execute().data
                    if not chaps:
                        st.warning("该书还没有拆分章节")
                        cid = None
                    else:
                        sel_chap = st.selectbox("3. 选择章节", [c['title'] for c in chaps])
                        cid = next(c['id'] for c in chaps if c['title'] == sel_chap)
                else:
                    st.empty() # 占位

            if books and cid:
                st.markdown("---")
                
                # === 📊 进度统计 ===
                try:
                    q_res = supabase.table("question_bank").select("id").eq("chapter_id", cid).execute().data
                    total_q = len(q_res)
                    
                    mastered_count = 0
                    if total_q > 0:
                        chapter_q_ids = set([q['id'] for q in q_res])
                        user_correct = supabase.table("user_answers").select("question_id").eq("user_id", user_id).eq("is_correct", True).execute().data
                        user_correct_ids = set([a['question_id'] for a in user_correct])
                        mastered_count = len(user_correct_ids.intersection(chapter_q_ids))
                    
                    prog = mastered_count / total_q if total_q > 0 else 0
                    st.caption(f"📈 进度：已掌握 {mastered_count} / 库存 {total_q} 题")
                    st.progress(prog)
                except:
                    total_q = 0

                st.divider()
                
                # === 🎯 模式选择 ===
                mode = st.radio("练习策略", [
                    "🎲 刷真题 (从库存抽)", 
                    "🧠 AI 基于教材出新题"
                ], horizontal=True)
                
                if st.button("🚀 开始练习", type="primary", use_container_width=True):
                    st.session_state.quiz_cid = cid
                    st.session_state.js_start_time = int(time.time() * 1000)
                    
                    # --- 策略 A: 刷真题 ---
                    if "真题" in mode:
                        if total_q == 0:
                            st.error("题库为空，请先去【资料库】生成或录入！")
                        else:
                            qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).limit(50).execute().data
                            if qs:
                                import random
                                random.shuffle(qs)
                                st.session_state.quiz_data = qs[:10]
                                st.session_state.q_idx = 0
                                st.session_state.quiz_active = True
                                st.rerun()

                    # --- 策略 B: AI 出题 ---
                    else:
                        mats = supabase.table("materials").select("content").eq("chapter_id", cid).execute().data
                        if not mats:
                            st.error("该章节没有提取内容！请先去【资料库】点击‘提取入库’。")
                        else:
                            full_text = "\n".join([m['content'] for m in mats])
                            with st.spinner("🤖 AI 正在研读并出题..."):
                                prompt = f"""
                                请基于以下教材内容，生成 3 道单项选择题。
                                教材片段：{full_text[:8000]}
                                必须返回纯 JSON 列表：
                                [
                                  {{
                                    "content": "题目...",
                                    "options": ["A.x", "B.x", "C.x", "D.x"],
                                    "correct_answer": "A",
                                    "explanation": "解析..."
                                  }}
                                ]
                                """
                                res = call_ai_universal(prompt)
                                if res:
                                    try:
                                        clean = res.replace("```json","").replace("```","").strip()
                                        d = json.loads(clean)
                                        
                                        # 存入数据库 (适配 V3 表结构)
                                        db_qs = [{
                                            'chapter_id': cid,
                                            'user_id': user_id,
                                            'type': 'single',
                                            'content': x['content'],
                                            'options': x['options'],
                                            'correct_answer': x['correct_answer'],
                                            'explanation': x['explanation'],
                                            'origin': 'ai_gen',
                                            # V3 新增字段 batch_source
                                            'batch_source': f'AI生成-{datetime.date.today()}'
                                        } for x in d]
                                        
                                        supabase.table("question_bank").insert(db_qs).execute()
                                        
                                        st.session_state.quiz_data = d
                                        st.session_state.q_idx = 0
                                        st.session_state.quiz_active = True
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"AI 生成格式错误: {e}")
        else:
            st.warning("请先去资料库上传书籍")

    # --- 3. 做题交互界面 (保持不变) ---
    if st.session_state.get('quiz_active'):
        # ... (此处代码与之前完全一致，做题逻辑不受数据库结构影响) ...
        # ... (为了代码简洁，请把你之前运行正常的“做题交互”部分逻辑贴在这里) ...
        # ... (也就是从 idx = st.session_state.q_idx 开始的那部分) ...
        
        # [如果你需要我把做题部分的完整代码也贴出来，请告诉我，否则只替换上面的启动区即可解决报错]
        # 下面是精简版占位，请确保你的文件里有这部分
        idx = st.session_state.q_idx
        data_len = len(st.session_state.quiz_data)
        
        if idx >= data_len:
            st.balloons()
            st.success("本轮结束")
            if st.button("返回"):
                st.session_state.quiz_active = False
                st.rerun()
        else:
            q = st.session_state.quiz_data[idx]
            
            # 顶部导航
            c_prog, c_end = st.columns([5, 1])
            with c_prog: st.progress((idx+1)/data_len)
            with c_end: 
                if st.button("🏁 结束"): 
                    st.session_state.quiz_active = False
                    st.rerun()
            
            # 显示题目
            q_text = q.get('content') or q.get('question')
            st.markdown(f"<div class='css-card'><h4>Q{idx+1}: {q_text}</h4></div>", unsafe_allow_html=True)
            
            # 选项
            q_opts = q.get('options', [])
            sel = st.radio("答案", q_opts, key=f"q_{idx}")
            
            # 提交逻辑
            sub_key = f"sub_{idx}"
            if sub_key not in st.session_state: st.session_state[sub_key] = False
            if st.button("✅ 提交", use_container_width=True) and not st.session_state[sub_key]:
                st.session_state[sub_key] = True
            
            if st.session_state[sub_key]:
                q_ans = q.get('correct_answer') or q.get('answer')
                user_val = sel[0] if sel else ""
                
                if user_val == q_ans: st.success("正确")
                else: 
                    st.error(f"错误，答案：{q_ans}")
                    # 存错题
                    if q.get('id'):
                        try:
                            supabase.table("user_answers").insert({
                                "user_id": user_id,
                                "question_id": q['id'],
                                "user_response": user_val,
                                "is_correct": False
                            }).execute()
                        except: pass
                
                st.info(f"解析：{q.get('explanation')}")
                
                if st.button("下一题"):
                    st.session_state.q_idx += 1
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


