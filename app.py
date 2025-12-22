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
st.set_page_config(page_title="中级会计 AI 私教 Pro (V3.1)", page_icon="🥝", layout="wide")

st.markdown("""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
<style>
    /* === 基础设定 === */
    .stApp {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        font-family: 'Segoe UI', 'Roboto', sans-serif;
    }
    [data-testid="stSidebar"] {
        background-color: rgba(255, 255, 255, 0.95);
        border-right: 1px solid rgba(0,0,0,0.05);
        box-shadow: 4px 0 15px rgba(0,0,0,0.03);
    }

    /* === 卡片 === */
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
        transform: translateY(-5px);
        box-shadow: 0 15px 30px rgba(0, 192, 144, 0.15);
        border-color: rgba(0, 192, 144, 0.3);
    }
    .css-card::before {
        content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%;
        background: #00C090; opacity: 0; transition: opacity 0.3s;
    }
    .css-card:hover::before { opacity: 1; }

    /* === 数字与按钮 === */
    .stat-title { font-size: 0.85rem; color: #6c757d; font-weight: 700; text-transform: uppercase; }
    .stat-value { font-size: 2.4rem; font-weight: 800; color: #2C3E50; }
    .stat-icon { position: absolute; right: 20px; top: 20px; font-size: 2rem; color: rgba(0,192,144, 0.15); }

    .stButton>button {
        background: linear-gradient(135deg, #00C090 0%, #00a87e 100%);
        color: white; border: none; border-radius: 50px; height: 45px; font-weight: 600;
        box-shadow: 0 4px 10px rgba(0, 192, 144, 0.3); transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px); box-shadow: 0 6px 15px rgba(0, 192, 144, 0.5); filter: brightness(1.1); color: white;
    }
    
    /* === 选项列表 === */
    .option-item {
        background: #fff; border: 1px solid #eee; padding: 12px 15px; border-radius: 8px; margin-bottom: 8px;
        border-left: 4px solid #e9ecef; transition: all 0.2s; color: #495057;
    }
    .option-item:hover { border-left-color: #00C090; background-color: #f8f9fa; }

    /* === 聊天气泡 === */
    .chat-user {
        background-color: #E3F2FD; padding: 12px 18px; border-radius: 15px 15px 0 15px;
        margin: 10px 0 10px auto; max-width: 85%; color: #1565C0; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .chat-ai {
        background-color: #FFFFFF; padding: 12px 18px; border-radius: 15px 15px 15px 0;
        margin: 10px auto 10px 0; max-width: 85%; border-left: 4px solid #00C090; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .success-box { padding: 15px; background: #E8F5E9; border-radius: 10px; color: #2E7D32; border: 1px solid #C8E6C9; margin-bottom: 10px;}
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

# 用户身份模拟
if 'user_id' not in st.session_state:
    st.session_state.user_id = "test_user_001"
user_id = st.session_state.user_id

# ==============================================================================
# 3. 核心功能函数
# ==============================================================================

# --- 数据库 Helper ---
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
    return supabase.table("books").select("*").eq("subject_id", sid).eq("user_id", user_id).execute().data

def get_chapters(book_id):
    return supabase.table("chapters").select("*").eq("book_id", book_id).order("start_page", desc=False).execute().data

def save_material_v3(chapter_id, content, uid):
    supabase.table("materials").insert({"chapter_id": chapter_id, "content": content, "user_id": uid}).execute()

def save_questions_v3(q_list, chapter_id, uid, origin="ai"):
    data = [{
        "chapter_id": chapter_id, "user_id": uid,
        "content": q['question'], "options": q['options'], "correct_answer": q['answer'], "explanation": q.get('explanation', ''),
        "type": "multi" if len(q['answer']) > 1 else "single", "origin": origin,
        "batch_source": f"Batch-{int(time.time())}"
    } for q in q_list]
    supabase.table("question_bank").insert(data).execute()

# --- AI 调用 (含超时控制) ---
def call_ai_universal(prompt, history=[], model_override=None):
    """支持 Gemini / DeepSeek / OpenRouter 的通用接口，含超时控制"""
    provider = st.session_state.get('selected_provider', 'Gemini')
    target_model = model_override or st.session_state.get('openrouter_model_id') or st.session_state.get('google_model_id') or st.session_state.get('deepseek_model_id')
    if not target_model: target_model = "gemini-1.5-flash"
    
    # 🔥 获取用户设定的超时时间 (默认 60s)
    user_settings = st.session_state.get('current_settings', {})
    timeout_sec = user_settings.get('ai_timeout', 60)

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
            
            resp = requests.post(url, headers=headers, json={"contents": contents}, timeout=timeout_sec)
            if resp.status_code == 200:
                return resp.json()['candidates'][0]['content']['parts'][0]['text']
            return f"Gemini Error {resp.status_code}: {resp.text}"

        # B. OpenAI 兼容
        else:
            client = None
            if model_override and "gemini" in model_override:
                 if "openrouter" in st.secrets:
                     client = OpenAI(api_key=st.secrets["openrouter"]["api_key"], base_url=st.secrets["openrouter"]["base_url"])
            elif "DeepSeek" in provider:
                client = OpenAI(api_key=st.secrets["deepseek"]["api_key"], base_url=st.secrets["deepseek"]["base_url"])
            elif "OpenRouter" in provider:
                client = OpenAI(api_key=st.secrets["openrouter"]["api_key"], base_url=st.secrets["openrouter"]["base_url"])
            
            if not client: return "AI Client 初始化失败"

            messages = [{"role": "system", "content": "你是资深会计讲师。回答请使用 Markdown 格式。"}]
            for h in history:
                role = "assistant" if h['role'] == "model" else h['role']
                messages.append({"role": role, "content": h['content']})
            messages.append({"role": "user", "content": prompt})

            resp = client.chat.completions.create(model=target_model, messages=messages, temperature=0.7, timeout=timeout_sec)
            return resp.choices[0].message.content

    except Exception as e:
        return f"AI 连接中断 (超时 {timeout_sec}s): {e}"

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
# 将设置存入 session 供全局调用
st.session_state.current_settings = settings

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
    
    menu = st.radio("功能导航", ["🏠 仪表盘", "📚 智能资料库 (V3)", "📝 章节特训", "⚔️ 全真模考", "📊 弱项分析", "❌ 错题本", "⚙️ 设置中心"], label_visibility="collapsed")
    
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
# 5. 各页面逻辑
# ==============================================================================

# === 🏠 仪表盘 ===
if menu == "🏠 仪表盘":
    st.markdown(f"### 🌞 欢迎回来，{user_id}")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f"<div class='css-card'><div class='stat-title'>累计刷题</div><div class='stat-value'>{profile.get('total_questions_done',0)}</div><i class='bi bi-pencil-fill stat-icon'></i></div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='css-card'><div class='stat-title'>连续打卡</div><div class='stat-value'>{profile.get('study_streak',0)}</div><i class='bi bi-fire stat-icon'></i></div>", unsafe_allow_html=True)
    with c3: st.markdown(f"<div class='css-card'><div class='stat-title'>待复习错题</div><div class='stat-value'>--</div><i class='bi bi-bookmark-x-fill stat-icon'></i></div>", unsafe_allow_html=True)

# === 📂 智能拆书 & 资料 (V3) ===
elif menu == "📂 智能拆书 & 资料":
    st.title("📂 资料库管理")
    
    subjects = get_subjects()
    if not subjects: st.error("请初始化科目数据"); st.stop()
    
    c1, c2 = st.columns([1, 2])
    with c1:
        s_name = st.selectbox("1. 所属科目", [s['name'] for s in subjects])
        sid = next(s['id'] for s in subjects if s['name'] == s_name)
    with c2:
        books = get_books(sid)
        b_opts = ["➕ 上传新教材/资料 (PDF)..."] + [b['title'] for b in books]
        sel_book = st.selectbox("2. 选择书籍/资料包", b_opts)
    
    # A. 上传新书
    if "上传新" in sel_book:
        with st.container():
            st.markdown("#### 📤 智能拆书台")
            up_file = st.file_uploader("上传 PDF", type="pdf")
            if up_file:
                try:
                    with pdfplumber.open(up_file) as pdf: total_pages = len(pdf.pages)
                    st.success(f"文件页数: {total_pages} 页")
                    if 'toc_analysis' not in st.session_state:
                        if st.button("🚀 开始 AI 目录分析"):
                            with st.spinner("正在读取前 20 页目录..."):
                                toc_text = extract_pdf(up_file, 1, 20)
                            with st.spinner("AI 正在规划章节结构..."):
                                p = f"分析目录结构。总页数{total_pages}。返回JSON列表:[{{'title':'第一章 总论','start':5,'end':20}}]。文本：{toc_text[:10000]}"
                                res = call_ai_universal(p, model_override="google/gemini-1.5-flash")
                                if res:
                                    try:
                                        clean = res.replace("```json","").replace("```","").strip()
                                        st.session_state.toc_analysis = json.loads(clean)
                                    except: st.error("AI 解析失败，请重试")
                    
                    if 'toc_analysis' in st.session_state:
                        st.write("##### 📝 确认拆分方案")
                        edited_df = st.data_editor(st.session_state.toc_analysis, num_rows="dynamic", column_config={"title": "章节名称", "start_page": st.column_config.NumberColumn("起始页", min_value=1), "end_page": st.column_config.NumberColumn("结束页", min_value=1)})
                        if st.button("✂️ 开始拆分入库"):
                            progress_bar = st.progress(0)
                            try:
                                book_res = supabase.table("books").insert({"user_id": user_id, "subject_id": sid, "title": up_file.name.replace(".pdf",""), "total_pages": total_pages}).execute()
                                bid = book_res.data[0]['id']
                                for i, chap in enumerate(edited_df):
                                    up_file.seek(0)
                                    txt = extract_pdf(up_file, chap['start_page'], chap['end_page'])
                                    if len(txt) > 10:
                                        c_res = supabase.table("chapters").insert({"book_id": bid, "title": chap['title'], "start_page": chap['start_page'], "end_page": chap['end_page'], "user_id": user_id}).execute()
                                        cid = c_res.data[0]['id']
                                        save_material_v3(cid, txt, user_id)
                                    progress_bar.progress((i+1)/len(edited_df))
                                st.success("拆分完成！")
                                del st.session_state.toc_analysis
                                st.rerun()
                            except Exception as e: st.error(f"出错: {e}")
                except: st.error("文件无效")

    # B. 已有书籍章节管理 (含选项卡)
    elif books:
        bid = next(b['id'] for b in books if b['title'] == sel_book)
        chapters = get_chapters(bid)
        st.divider()
        if not chapters: st.warning("本书暂无章节。")
        else:
            for chap in chapters:
                with st.expander(f"📑 {chap['title']}"):
                    has_mat = supabase.table("materials").select("id", count="exact").eq("chapter_id", chap['id']).execute().count
                    if not has_mat: st.warning("内容缺失，请补录")
                    
                    t1, t2, t3 = st.tabs(["📖 教材/补录", "📑 真题提取", "🎓 AI 导学"])
                    
                    # Tab 1: 教材
                    with t1:
                        if has_mat: st.success("✅ 教材内容已就绪")
                        t_up = st.file_uploader(f"上传教材PDF", type=['pdf','docx'], key=f"up_m_{chap['id']}")
                        if t_up and st.button("📥 存入教材", key=f"btn_m_{chap['id']}"):
                            txt = extract_pdf(t_up) if t_up.name.endswith('.pdf') else extract_docx(t_up)
                            save_material_v3(chap['id'], txt, user_id)
                            st.success("已保存")
                            st.rerun()

                    # Tab 2: 真题
                    with t2:
                        st.caption("上传含答案的PDF，AI自动提取入库。")
                        q_up = st.file_uploader(f"上传真题PDF", type=['pdf','docx'], key=f"up_q_{chap['id']}")
                        c_p1, c_p2 = st.columns(2)
                        with c_p1: q_start = st.number_input("题目开始页", 1, key=f"qs_{chap['id']}")
                        with c_p2: q_end = st.number_input("题目结束页", 10, key=f"qe_{chap['id']}")
                        
                        sep = st.checkbox("答案在文档末尾", key=f"sep_{chap['id']}")
                        if sep:
                            c_a1, c_a2 = st.columns(2)
                            with c_a1: a_start = st.number_input("答案开始页", 1, key=f"as_{chap['id']}")
                            with c_a2: a_end = st.number_input("答案结束页", 10, key=f"ae_{chap['id']}")
                        
                        if q_up and st.button("🔍 提取真题", key=f"btn_q_{chap['id']}"):
                            with st.spinner("AI 提取中..."):
                                raw = ""
                                if q_up.name.endswith('.pdf'):
                                    q_up.seek(0)
                                    raw = extract_pdf(q_up, q_start, q_end)
                                    if sep: 
                                        q_up.seek(0)
                                        raw += "\n【答案区】\n" + extract_pdf(q_up, a_start, a_end)
                                else: raw = extract_docx(q_up)
                                
                                p = f"提取会计题目。内容：{raw[:15000]}。JSON列表：[{{'question':'..','options':['A..'],'answer':'A','explanation':'..'}}]。"
                                r = call_ai_universal(p)
                                if r:
                                    try:
                                        d = json.loads(r.replace("```json","").replace("```","").strip())
                                        save_questions_v3(d, chap['id'], user_id, origin="extract")
                                        st.success(f"成功存入 {len(d)} 题")
                                    except: st.error("AI 格式错误")

                    # Tab 3: 导学
                    with t3:
                        if st.button("✨ 生成本章导学", key=f"gen_l_{chap['id']}"):
                            mat = supabase.table("materials").select("content").eq("chapter_id", chap['id']).limit(1).execute().data
                            if mat:
                                with st.spinner("备课中..."):
                                    res = call_ai_universal(f"生成通俗讲义。内容：{mat[0]['content'][:20000]}")
                                    if res:
                                        model = st.session_state.get('selected_provider', 'AI')
                                        supabase.table("ai_lessons").insert({"chapter_id": chap['id'], "user_id": user_id, "title": f"{model}讲义", "content": res, "ai_model": model}).execute()
                                        st.rerun()
                            else: st.error("缺教材")
                        
                        # 显示讲义
                        lessons = supabase.table("ai_lessons").select("*").eq("chapter_id", chap['id']).execute().data
                        if lessons:
                            for l in lessons:
                                with st.expander(f"📘 {l['title']}"): st.markdown(l['content'])

# === 📝 章节特训 ===
elif menu == "📝 章节特训":
    st.title("📝 章节突破")
    
    if st.session_state.get('quiz_active'):
        if 'js_start_time' not in st.session_state: st.session_state.js_start_time = int(time.time() * 1000)
        components.html(f"""<div style='position:fixed;top:60px;right:20px;z-index:9999;background:#00C090;color:white;padding:5px 15px;border-radius:20px;font-family:monospace;font-weight:bold'>⏱️ <span id='t'>00:00</span></div><script>setInterval(()=>{{var d=Math.floor((Date.now()-{st.session_state.js_start_time})/1000);document.getElementById('t').innerText=Math.floor(d/60).toString().padStart(2,'0')+':'+(d%60).toString().padStart(2,'0')}},1000)</script>""", height=0)

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
                
            try:
                total = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", cid).execute().count
                st.caption(f"📚 题库库存: {total} 题")
            except: pass
            
            if st.button("🚀 开始刷题", type="primary", use_container_width=True):
                qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).limit(20).execute().data
                if qs:
                    random.shuffle(qs)
                    st.session_state.quiz_data = qs[:10]
                    st.session_state.q_idx = 0
                    st.session_state.quiz_active = True
                    st.session_state.js_start_time = int(time.time()*1000)
                    st.rerun()
                else: st.error("本章无题")

    if st.session_state.get('quiz_active'):
        idx = st.session_state.q_idx
        total = len(st.session_state.quiz_data)
        if idx >= total:
            st.balloons()
            st.success("完成！")
            if st.button("返回"): 
                st.session_state.quiz_active = False; st.rerun()
        else:
            q = st.session_state.quiz_data[idx]
            st.progress((idx+1)/total)
            st.markdown(f"<div class='css-card'><h4>Q{idx+1}: {q.get('content')}</h4></div>", unsafe_allow_html=True)
            
            q_ans = (q.get('correct_answer') or "").upper().replace(" ","").replace(",","")
            is_multi = len(q_ans) > 1 or q.get('type') == 'multi'
            
            user_val = ""
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
            if st.button("✅ 提交", use_container_width=True) and not st.session_state[sub_key]:
                st.session_state[sub_key] = True
            
            if st.session_state[sub_key]:
                if user_val == q_ans: 
                    st.markdown("<div class='success-box'>🎉 正确</div>", unsafe_allow_html=True)
                    supabase.table("user_answers").insert({"user_id": user_id, "question_id": q['id'], "user_response": user_val, "is_correct": True}).execute()
                else:
                    st.error(f"❌ 错误。答案: {q_ans}")
                    exist = supabase.table("user_answers").select("id").eq("user_id", user_id).eq("question_id", q['id']).eq("is_correct", False).execute().data
                    if not exist:
                        supabase.table("user_answers").insert({"user_id": user_id, "question_id": q['id'], "user_response": user_val, "is_correct": False}).execute()
                st.info(f"解析：{q.get('explanation')}")
                
                # AI 举例
                c_k = f"chat_{idx}"
                if c_k not in st.session_state: st.session_state[c_k] = []
                if st.button("🤔 AI 举例"):
                    r = call_ai_universal(f"举例解释：{q.get('content')} 答案{q_ans}")
                    if r: st.session_state[c_k].append({"role":"model","content":r})
                
                for m in st.session_state[c_k]:
                    st.markdown(f"<div class='chat-ai'>{m['content']}</div>", unsafe_allow_html=True)

            st.markdown("---")
            if st.button("➡️ 下一题", use_container_width=True):
                st.session_state.q_idx += 1; st.rerun()

# === ⚔️ 全真模考 ===
elif menu == "⚔️ 全真模考":
    st.title("⚔️ 全真模拟")
    if 'exam_session' not in st.session_state: st.session_state.exam_session = None
    
    if not st.session_state.exam_session:
        # (简化展示历史)
        st.write("点击开始生成试卷...")
        if st.button("🚀 生成试卷", type="primary"):
            # 简单拉取题库
            qs = supabase.table("question_bank").select("*").limit(20).execute().data
            if qs:
                st.session_state.exam_session = {"paper": qs, "answers": {}, "start": int(time.time()*1000), "submitted": False}
                st.rerun()
            else: st.error("题库不足")
            
    elif not st.session_state.exam_session['submitted']:
        session = st.session_state.exam_session
        end_ms = session['start'] + 3600000 # 1小时
        components.html(f"""<div style='position:fixed;top:60px;right:20px;z-index:9999;background:#dc3545;color:white;padding:5px 15px;border-radius:20px'>⏳ <span id='et'>--:--</span></div><script>setInterval(()=>{{var d=Math.floor(({end_ms}-Date.now())/1000);document.getElementById('et').innerText=Math.floor(d/60)+':'+(d%60)}},1000)</script>""", height=0)
        
        with st.form("exam"):
            for i, q in enumerate(session['paper']):
                st.markdown(f"**{i+1}. {q['content']}**")
                # 简单单选
                session['answers'][i] = st.radio("选", q['options'], key=f"e_{i}")
                st.divider()
            if st.form_submit_button("交卷"):
                session['submitted'] = True
                st.rerun()
    else:
        st.balloons()
        st.success("考试结束！")
        if st.button("退出"): st.session_state.exam_session = None; st.rerun()

# === 📊 弱项分析 ===
elif menu == "📊 弱项分析":
    st.title("📊 分析")
    rows = supabase.table("user_answers").select("*").order("created_at", desc=True).limit(500).execute().data
    if rows:
        df = pd.DataFrame(rows)
        c1, c2 = st.columns(2)
        with c1: st.metric("刷题总数", len(df))
        with c2: st.metric("正确率", f"{int(len(df[df['is_correct']==True])/len(df)*100)}%")
        fig = px.pie(df, names='is_correct', color_discrete_map={True:'#00C090', False:'#FF7043'})
        st.plotly_chart(fig)
    else: st.info("无数据")

# === ❌ 错题本 ===
elif menu == "❌ 错题本":
    st.title("❌ 错题集")
    errs = supabase.table("user_answers").select("*, question_bank(*)").eq("user_id", user_id).eq("is_correct", False).execute().data
    
    unique_q = {}
    for e in errs:
        if e['question_id'] not in unique_q: unique_q[e['question_id']] = e
        
    if not unique_q: st.success("🎉 无错题")
    else:
        for qid, e in unique_q.items():
            q = e['question_bank']
            if not q: continue
            with st.expander(f"🔴 {q['content'][:30]}..."):
                st.markdown(f"**题目**：{q['content']}")
                for o in q['options']: st.markdown(f"<div class='option-item'>{o}</div>", unsafe_allow_html=True)
                st.error(f"你的: {e['user_response']}")
                st.success(f"正确: {q['correct_answer']}")
                st.info(f"解析: {q['explanation']}")
                
                if st.button("✅ 移除", key=f"rm_{qid}"):
                    supabase.table("user_answers").update({"is_correct": True}).eq("question_id", qid).execute()
                    st.rerun()

# === ⚙️ 设置中心 ===
elif menu == "⚙️ 设置中心":
    st.title("⚙️ 设置")
    
    # AI 连通性测试
    st.markdown("#### 🤖 AI 模型配置")
    curr_timeout = settings.get('ai_timeout', 60)
    new_timeout = st.slider("AI 响应超时时间 (秒)", 10, 300, curr_timeout)
    if new_timeout != curr_timeout:
        update_settings(user_id, {"ai_timeout": new_timeout})
        st.toast("已保存")
        
    if st.button("📡 测试当前模型连通性"):
        with st.spinner("测试中..."):
            res = call_ai_universal("Hello, response 'OK'.")
            if "OK" in res or len(res) > 0: st.success(f"✅ 连接成功！回复: {res}")
            else: st.error(f"❌ 连接失败: {res}")

    st.divider()
    
    # 倒计时
    curr = datetime.date(2025,9,6)
    if profile.get('exam_date'):
        try: curr = datetime.datetime.strptime(profile['exam_date'], '%Y-%m-%d').date()
        except: pass
    new_d = st.date_input("考试日期", curr)
    if new_d != curr:
        supabase.table("study_profile").update({"exam_date": str(new_d)}).eq("user_id", user_id).execute()
        st.rerun()
