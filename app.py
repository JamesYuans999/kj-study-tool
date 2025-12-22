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
# 1. 全局配置与 CSS 样式 (Bootstrap 风格)
# ==============================================================================
st.set_page_config(page_title="中级会计 AI 私教 Pro (V3.2)", page_icon="🥝", layout="wide")

st.markdown("""
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
<style>
    /* 全局背景 */
    .stApp {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        font-family: 'Segoe UI', 'Roboto', sans-serif;
    }
    
    /* 侧边栏 */
    [data-testid="stSidebar"] {
        background-color: rgba(255, 255, 255, 0.95);
        border-right: 1px solid rgba(0,0,0,0.05);
        box-shadow: 4px 0 15px rgba(0,0,0,0.03);
    }

    /* 卡片风格 */
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

    /* 统计数字 */
    .stat-title { font-size: 0.85rem; color: #6c757d; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
    .stat-value { font-size: 2.4rem; font-weight: 800; color: #2C3E50; letter-spacing: -1px; }
    .stat-icon { position: absolute; right: 20px; top: 20px; font-size: 2rem; color: rgba(0,192,144, 0.15); }

    /* 按钮美化 */
    .stButton>button {
        background: linear-gradient(135deg, #00C090 0%, #00a87e 100%);
        color: white; border: none; border-radius: 50px; height: 45px; font-weight: 600;
        box-shadow: 0 4px 10px rgba(0, 192, 144, 0.3); transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px); box-shadow: 0 6px 15px rgba(0, 192, 144, 0.5); filter: brightness(1.1); color: white;
    }

    /* 聊天气泡 */
    .chat-user {
        background-color: #E3F2FD; padding: 12px 18px; border-radius: 15px 15px 0 15px;
        margin: 10px 0 10px auto; max-width: 85%; color: #1565C0; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .chat-ai {
        background-color: #FFFFFF; padding: 12px 18px; border-radius: 15px 15px 15px 0;
        margin: 10px auto 10px 0; max-width: 85%; border-left: 4px solid #00C090; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* 选项列表 */
    .option-item {
        background: #fff; border: 1px solid #eee; padding: 12px 15px; border-radius: 8px; margin-bottom: 8px;
        border-left: 4px solid #e9ecef; transition: all 0.2s; color: #495057;
    }
    .option-item:hover { border-left-color: #00C090; background-color: #f8f9fa; }
    
    .success-box { padding: 15px; background: #E8F5E9; border-radius: 10px; color: #2E7D32; border: 1px solid #C8E6C9; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. 数据库连接与初始化
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

if 'user_id' not in st.session_state:
    st.session_state.user_id = "test_user_001"
user_id = st.session_state.user_id

# ==============================================================================
# 3. 核心功能函数库
# ==============================================================================

# --- AI 核心调用 (支持多模型 + 超时控制) ---
def call_ai_universal(prompt, history=[], model_override=None):
    """
    通用 AI 接口，支持 Gemini / DeepSeek / OpenRouter
    """
    profile = get_user_profile(st.session_state.get('user_id'))
    settings = profile.get('settings') or {}
    current_timeout = settings.get('ai_timeout', 60)
    
    provider = st.session_state.get('selected_provider', 'Gemini')
    target_model = model_override or st.session_state.get('openrouter_model_id') or st.session_state.get('google_model_id') or st.session_state.get('deepseek_model_id')
    
    if not target_model: target_model = "gemini-1.5-flash"
    
    try:
        # A. Google Gemini 官方直连
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

        # B. OpenAI 兼容接口 (DeepSeek / OpenRouter)
        else:
            client = None
            # 特殊逻辑：如果是 Override 且包含 gemini (例如拆书时)，尝试走 OpenRouter 渠道调用 Google 模型
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

            resp = client.chat.completions.create(model=target_model, messages=messages, temperature=0.7, timeout=current_timeout)
            return resp.choices[0].message.content

    except Exception as e:
        return f"AI 连接异常: {e}"

# --- API 列表获取 ---
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

# --- 数据库操作 Helper ---
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
    # 增加健壮性处理，防止字段缺失
    data = []
    for q in q_list:
        data.append({
            "chapter_id": chapter_id,
            "user_id": uid,
            "content": q.get('question') or q.get('content'),
            "options": q.get('options'),
            "correct_answer": q.get('answer') or q.get('correct_answer'),
            "explanation": q.get('explanation', ''),
            "type": "multi" if len(q.get('answer', '')) > 1 else "single",
            "origin": origin,
            "batch_source": f"Batch-{int(time.time())}"
        })
    if data:
        supabase.table("question_bank").insert(data).execute()

# --- 文件读取 ---
def extract_pdf(file, start=1, end=None):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            total = len(pdf.pages)
            if end is None or end > total: end = total
            # 修正页码逻辑：输入1表示第1页(index 0)
            for i in range(start-1, end):
                if i < total:
                    text += (pdf.pages[i].extract_text() or "") + "\n"
        return text
    except: return ""

def extract_docx(file):
    try:
        doc = docx.Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    except: return ""

def save_ai_pref():
    p = st.session_state.get('ai_provider_select')
    m = None
    if "OpenRouter" in str(p): m = st.session_state.get('or_model_select')
    elif "DeepSeek" in str(p): m = st.session_state.get('ds_model_select')
    elif "Gemini" in str(p): m = st.session_state.get('gl_model_select')
    if p: update_settings(user_id, {"last_provider": p, "last_used_model": m})

# ==============================================================================
# 4. 侧边栏 (导航与设置)
# ==============================================================================
profile = get_user_profile(user_id)
settings = profile.get('settings') or {}

with st.sidebar:
    st.title("🥝 备考中心")
    
    # --- 模型选择器 (带记忆) ---
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
            filtered_ids = ["google/gemini-2.0-flash-exp:free"]
        else:
            ft = st.radio("筛选", ["🤑 免费", "🌎 全部"], horizontal=True)
            subset = [m for m in all_ms if m['is_free']] if "免费" in ft else all_ms
            filtered_ids = [m['id'] for m in subset]
            if not filtered_ids: filtered_ids = [m['id'] for m in all_ms]
        idx_m = filtered_ids.index(saved_m) if saved_m in filtered_ids else 0
        st.session_state.openrouter_model_id = st.selectbox("🔌 模型", filtered_ids, index=idx_m, key="or_model_select", on_change=save_ai_pref)

    st.divider()
    menu = st.radio("功能导航", ["🏠 仪表盘", "📂 智能拆书 & 资料", "🎓 AI 课堂 (讲义)", "📝 章节特训 (刷题)", "⚔️ 全真模考", "📊 弱项分析", "❌ 错题本", "⚙️ 设置中心"], label_visibility="collapsed")
    
    # --- 智能跨年倒计时 ---
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
# 5. 主功能区逻辑 (所有模块完整展开)
# ==============================================================================

# === 🏠 仪表盘 ===
if menu == "🏠 仪表盘":
    st.markdown(f"### 🌞 欢迎回来，开始高效学习")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f"<div class='css-card'><div class='stat-title'>累计刷题</div><div class='stat-value'>{profile.get('total_questions_done', 0)}</div><i class='bi bi-pencil-fill stat-icon'></i></div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='css-card'><div class='stat-title'>连续打卡</div><div class='stat-value'>{profile.get('study_streak', 0)}</div><i class='bi bi-fire stat-icon'></i></div>", unsafe_allow_html=True)
    with c3: st.markdown(f"<div class='css-card'><div class='stat-title'>待复习错题</div><div class='stat-value'>--</div><i class='bi bi-bookmark-x-fill stat-icon'></i></div>", unsafe_allow_html=True)

# === 📂 智能拆书 & 资料 (V3.2 终极修复：双轨制+页码控制) ===
elif menu == "📂 智能拆书 & 资料":
    st.title("📂 资料库管理")
    
    subjects = get_subjects()
    if not subjects: st.error("请先在数据库初始化科目数据"); st.stop()
    
    # 1. 顶层选择 (科目->书籍)
    c1, c2 = st.columns([1, 2])
    with c1:
        s_name = st.selectbox("1. 所属科目", [s['name'] for s in subjects])
        sid = next(s['id'] for s in subjects if s['name'] == s_name)
    with c2:
        books = get_books(sid)
        b_opts = ["➕ 上传新书/新题库..."] + [b['title'] for b in books]
        sel_book = st.selectbox("2. 选择书籍", b_opts)
    
    st.divider()

    # --- 场景 A: 上传新书 (目录拆分) ---
    if "上传新" in sel_book:
        st.markdown("#### 📤 步骤一：建立书籍结构")
        st.info("AI 自动分析目录，将大文件拆分为章节。")
        
        book_type = st.radio("资料类型", ["📖 纯教材 (分章节学习)", "📑 习题集 (分套刷题)"], horizontal=True)
        up_file = st.file_uploader("上传完整 PDF", type="pdf")
        
        if up_file:
            try:
                with pdfplumber.open(up_file) as pdf: total_pages = len(pdf.pages)
                st.success(f"文件共 {total_pages} 页")
                
                # Step 1: 分析目录
                if 'toc_analysis' not in st.session_state:
                    if st.button("🚀 开始 AI 目录分析"):
                        with st.spinner("读取前 30 页目录..."):
                            toc_text = extract_pdf(up_file, 1, min(30, total_pages))
                        with st.spinner("AI 识别结构..."):
                            task = "提取书本章节" if "教材" in book_type else "提取试卷/练习题标题"
                            p = f"""
                            任务：{task}。总页数：{total_pages}。
                            【必须】返回纯 JSON 列表：[{{ "title": "名称", "start_page": 5, "end_page": 10 }}]
                            文本：{toc_text[:10000]}
                            """
                            res = call_ai_universal(p, model_override="google/gemini-1.5-flash")
                            if res:
                                try:
                                    clean = res.replace("```json","").replace("```","").strip()
                                    s = clean.find('['); e = clean.rfind(']')+1
                                    st.session_state.toc_analysis = json.loads(clean[s:e])
                                    st.rerun()
                                except: st.error("AI 解析失败")

                # Step 2: 确认与保存
                if 'toc_analysis' in st.session_state:
                    st.write("##### 📝 确认结构")
                    edited_df = st.data_editor(st.session_state.toc_analysis, num_rows="dynamic", use_container_width=True)
                    
                    if st.button("💾 确认创建"):
                        b_res = supabase.table("books").insert({
                            "user_id": user_id, "subject_id": sid, "title": up_file.name.replace(".pdf",""), "total_pages": total_pages
                        }).execute()
                        bid = b_res.data[0]['id']
                        
                        prog = st.progress(0)
                        for i, row in enumerate(edited_df):
                            c_res = supabase.table("chapters").insert({
                                "book_id": bid, "title": row['title'], "start_page": row['start_page'], "end_page": row['end_page'], "user_id": user_id
                            }).execute()
                            # 只有教材才自动存文本，习题集不存(因为要后续拼接答案)
                            if "教材" in book_type:
                                up_file.seek(0)
                                txt = extract_pdf(up_file, row['start_page'], row['end_page'])
                                if len(txt) > 10: save_material_v3(c_res.data[0]['id'], txt, user_id)
                            prog.progress((i+1)/len(edited_df))
                        
                        st.success("创建完成！")
                        del st.session_state.toc_analysis
                        time.sleep(2)
                        st.rerun()
            except: st.error("文件错误")

    # --- 场景 B: 已有书籍管理 (V2 功能复活：双轨录入) ---
    elif books:
        bid = next(b['id'] for b in books if b['title'] == sel_book)
        chapters = get_chapters(bid)
        
        # 删除书籍按钮
        c_del_b, _ = st.columns([1, 5])
        with c_del_b:
            with st.popover("⚙️ 管理"):
                if st.button("🗑️ 删除此书"):
                    supabase.table("books").delete().eq("id", bid).execute()
                    st.rerun()

        if not chapters:
            st.warning("无章节")
        else:
            # 3. 选择章节
            c3, c4 = st.columns([2, 1])
            with c3:
                sel_chap = st.selectbox("3. 选择具体章节", [c['title'] for c in chapters])
                cid = next(c['id'] for c in chapters if c['title'] == sel_chap)
                # 获取预设页码
                curr_chap = next(c for c in chapters if c['id'] == cid)
                def_s = curr_chap['start_page']
                def_e = curr_chap['end_page']
            
            with c4:
                # 统计
                q_cnt = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", cid).execute().count
                m_cnt = supabase.table("materials").select("id", count="exact").eq("chapter_id", cid).execute().count
                st.markdown(f"<div style='text-align:right; margin-top:28px; color:#666'>📚 教材: <b>{m_cnt}</b> | 📑 题库: <b>{q_cnt}</b></div>", unsafe_allow_html=True)

            st.markdown("---")
            
            # --- 🔥 核心 Tabs: 恢复 V2 的所有好功能 ---
            t1, t2, t3 = st.tabs(["📑 习题录入 (拼接答案)", "📖 教材文本管理", "🎓 AI 导学"])
            
            # [Tab 1] 习题录入 (V2 灵魂复刻：页码控制 + 提示词 + 答案拼接)
            with t1:
                st.info("💡 适合“题目在前、答案在后”的 PDF。AI 将读取两段内容，自动对齐并存入题库。")
                up_ex = st.file_uploader("请重新拖入 PDF", type="pdf", key="up_ex")
                
                if up_ex:
                    try:
                        with pdfplumber.open(up_ex) as pdf: tp = len(pdf.pages)
                        
                        # 1. 题目与答案区间选择器
                        st.write("##### 📐 设定读取范围")
                        col_q, col_a = st.columns(2)
                        with col_q:
                            st.markdown("**题目区域**")
                            q_s = st.number_input("题目开始页", 1, value=def_s, key="qs")
                            q_e = st.number_input("题目结束页", 1, value=def_e, key="qe")
                        with col_a:
                            st.markdown("**答案区域**")
                            need_ans = st.checkbox("启用答案拼接", value=True)
                            if need_ans:
                                a_s = st.number_input("答案开始页", 1, value=tp, key="as")
                                a_e = st.number_input("答案结束页", 1, value=tp, key="ae")
                        
                        hint = st.text_input("给 AI 的提示词", placeholder="例：这是单选题，忽略页眉，答案格式为 1.A...")
                        
                        # 3. 提取按钮
                        if st.button("🔍 开始提取并对齐", type="primary"):
                            with st.spinner("读取文件中..."):
                                up_ex.seek(0)
                                raw_text = extract_pdf(up_ex, q_s, q_e)
                                if need_ans:
                                    up_ex.seek(0)
                                    ans_text = extract_pdf(up_ex, a_s, a_e)
                                    raw_text += f"\n\n====== 以下是参考答案区域 ======\n{ans_text}"
                            
                            if len(raw_text) < 50:
                                st.error("提取文字过少")
                            else:
                                with st.spinner("AI 正在进行题目与答案的配对..."):
                                    p = f"""
                                    任务：提取题目并匹配答案。
                                    题目和答案在同一文本的不同位置（已标记）。
                                    请根据题号（如 1. 2. ...）自动将答案填入对应的题目中。
                                    用户提示：{hint}
                                    
                                    必须返回纯 JSON 列表，格式：
                                    [{{ "question": "...", "options": ["A.","B."], "answer": "A", "explanation": "解析..." }}]
                                    
                                    文本：{raw_text[:25000]}
                                    """
                                    res = call_ai_universal(p)
                                    if res:
                                        try:
                                            # 强力清洗
                                            clean = res.replace("```json","").replace("```","").strip()
                                            s = clean.find('['); e = clean.rfind(']')+1
                                            st.session_state.ex_data = json.loads(clean[s:e])
                                            st.success(f"识别到 {len(st.session_state.ex_data)} 道题！")
                                        except: 
                                            st.error("AI 格式错误")
                                            with st.expander("Debug"): st.text(res)
                        
                        # 4. 预览与保存
                        if 'ex_data' in st.session_state:
                            st.divider()
                            edited = st.data_editor(st.session_state.ex_data, num_rows="dynamic")
                            if st.button("💾 确认存入题库"):
                                save_questions_v3(edited, cid, user_id, origin="extraction")
                                st.balloons()
                                st.success("入库成功！")
                                del st.session_state.ex_data
                                time.sleep(1)
                                st.rerun()

                    except Exception as e: st.error(f"文件错误: {e}")

            # [Tab 2] 教材管理
            with t2:
                mats = supabase.table("materials").select("*").eq("chapter_id", cid).execute().data
                if mats:
                    with st.expander(f"👀 预览已存教材 ({len(mats[0]['content'])}字)", expanded=True):
                        st.text(mats[0]['content'][:1000] + "...")
                        if st.button("删除此教材内容"):
                            supabase.table("materials").delete().eq("id", mats[0]['id']).execute()
                            st.rerun()
                else:
                    st.warning("本章暂无教材文本。")
                    up_t = st.file_uploader("补录教材 PDF", type="pdf", key="up_t")
                    if up_t and st.button("上传"):
                        txt = extract_pdf(up_t)
                        save_material_v3(cid, txt, user_id)
                        st.rerun()

            # [Tab 3] AI 导学
            with t3:
                if st.button("✨ 生成讲义"):
                    if not mats: st.error("无教材内容")
                    else:
                        txt = "\n".join([m['content'] for m in mats])
                        with st.spinner("生成中..."):
                            res = call_ai_universal(f"生成通俗会计讲义。内容：{txt[:20000]}")
                            if res:
                                m_id = st.session_state.get('openrouter_model_id') or "AI"
                                supabase.table("ai_lessons").insert({"chapter_id":cid, "user_id":user_id, "title":f"{m_id}版", "content":res, "ai_model":m_id}).execute()
                                st.success("完成")

# === 🎓 AI 课堂 (讲义) ===
elif menu == "🎓 AI 课堂 (讲义)":
    st.title("🎓 智能讲义")
    books = supabase.table("books").select("*").eq("user_id", user_id).execute().data
    if books:
        c1, c2 = st.columns(2)
        with c1: 
            b_name = st.selectbox("书籍", [b['title'] for b in books])
            bid = next(b['id'] for b in books if b['title'] == b_name)
        with c2:
            chaps = get_chapters(bid)
            if chaps:
                c_name = st.selectbox("章节", [c['title'] for c in chaps])
                cid = next(c['id'] for c in chaps if c['title'] == c_name)
            else: cid = None
            
        if cid:
            lessons = supabase.table("ai_lessons").select("*").eq("chapter_id", cid).order("created_at", desc=True).execute().data
            if lessons:
                tabs = st.tabs([l['title'] or "未命名" for l in lessons])
                for i, tab in enumerate(tabs):
                    with tab:
                        st.markdown(lessons[i]['content'])
            else: st.info("暂无讲义")

# === 📝 章节特训 (刷题) ===
elif menu == "📝 章节特训 (刷题)":
    st.title("📝 章节突破")
    
    if st.session_state.get('quiz_active'):
        if 'js_start_time' not in st.session_state: st.session_state.js_start_time = int(time.time() * 1000)
        components.html(f"""<div style='position:fixed;top:60px;right:20px;z-index:9999;background:#00C090;color:white;padding:5px 15px;border-radius:20px;font-family:monospace;font-weight:bold'>⏱️ <span id='t'>00:00</span></div><script>setInterval(()=>{{var d=Math.floor((Date.now()-{st.session_state.js_start_time})/1000);document.getElementById('t').innerText=Math.floor(d/60).toString().padStart(2,'0')+':'+(d%60).toString().padStart(2,'0')}},1000)</script>""", height=0)

    if not st.session_state.get('quiz_active'):
        subjects = get_subjects()
        if subjects:
            c1, c2, c3 = st.columns(3)
            with c1: 
                s_name = st.selectbox("科目", [s['name'] for s in subjects])
                sid = next(s['id'] for s in subjects if s['name'] == s_name)
            with c2:
                books = get_books(sid)
                if books:
                    b_name = st.selectbox("书籍", [b['title'] for b in books])
                    bid = next(b['id'] for b in books if b['title'] == b_name)
                else: bid = None
            with c3:
                if bid:
                    chaps = get_chapters(bid)
                    if chaps:
                        c_name = st.selectbox("章节", [c['title'] for c in chaps])
                        cid = next(c['id'] for c in chaps if c['title'] == c_name)
                    else: cid = None
                else: cid = None
            
            if cid:
                st.markdown("---")
                try:
                    q_res = supabase.table("question_bank").select("id").eq("chapter_id", cid).execute().data
                    total = len(q_res)
                    if total > 0:
                        done_res = supabase.table("user_answers").select("question_id").eq("user_id", user_id).eq("is_correct", True).execute().data
                        done_ids = set([d['question_id'] for d in done_res])
                        mastered = len(done_ids.intersection(set([q['id'] for q in q_res])))
                        st.caption(f"📈 进度：{mastered}/{total}")
                        st.progress(mastered/total)
                except: pass
                
                mode = st.radio("模式", ["🎲 刷真题库存", "🧠 AI 基于教材出新题"])
                
                if st.button("🚀 开始刷题", type="primary", use_container_width=True):
                    st.session_state.quiz_cid = cid
                    st.session_state.js_start_time = int(time.time() * 1000)
                    
                    if "真题" in mode:
                        qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).limit(20).execute().data
                        if qs:
                            random.shuffle(qs)
                            st.session_state.quiz_data = qs[:10]
                            st.session_state.q_idx = 0
                            st.session_state.quiz_active = True
                            st.rerun()
                        else: st.error("本章无题")
                    else:
                        mats = supabase.table("materials").select("content").eq("chapter_id", cid).execute().data
                        if mats:
                            txt = "\n".join([m['content'] for m in mats])
                            with st.spinner("AI 出题中..."):
                                p = f"出3道单选题。JSON格式。内容：{txt[:6000]}"
                                r = call_ai_universal(p)
                                if r:
                                    try:
                                        clean = r.replace("```json","").replace("```","").strip()
                                        d = json.loads(clean)
                                        # 适配 V3
                                        save_questions_v3(d, cid, user_id, origin="ai_gen")
                                        st.session_state.quiz_data = d
                                        st.session_state.q_idx = 0
                                        st.session_state.quiz_active = True
                                        st.rerun()
                                    except: st.error("AI 格式错误")
                        else: st.error("无教材")

    # 做题
    if st.session_state.get('quiz_active'):
        idx = st.session_state.q_idx
        total = len(st.session_state.quiz_data)
        
        if idx >= total:
            st.balloons()
            st.success("完成！")
            if st.button("返回"):
                st.session_state.quiz_active = False
                st.rerun()
        else:
            q = st.session_state.quiz_data[idx]
            st.progress((idx+1)/total)
            
            # 显示题目
            q_text = q.get('content') or q.get('question')
            st.markdown(f"<div class='css-card'><h4>Q{idx+1}: {q_text}</h4></div>", unsafe_allow_html=True)
            
            # 多选判断
            q_ans = (q.get('correct_answer') or q.get('answer') or "").upper().replace(" ","").replace(",","")
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
                    # 存正确
                    supabase.table("user_answers").insert({"user_id": user_id, "question_id": q.get('id'), "user_response": user_val, "is_correct": True}).execute()
                else:
                    st.error(f"❌ 错误。答案：{q_ans}")
                    # 存错误 (防重)
                    if q.get('id'):
                        exist = supabase.table("user_answers").select("id").eq("user_id", user_id).eq("question_id", q['id']).eq("is_correct", False).execute().data
                        if exist:
                            supabase.table("user_answers").update({"created_at": datetime.datetime.now().isoformat()}).eq("id", exist[0]['id']).execute()
                        else:
                            supabase.table("user_answers").insert({"user_id": user_id, "question_id": q['id'], "user_response": user_val, "is_correct": False}).execute()
                
                st.info(f"解析：{q.get('explanation')}")
                
                chat_key = f"q_chat_{idx}"
                if chat_key not in st.session_state: st.session_state[chat_key] = []
                if st.button("🤔 AI 举个栗子"):
                    with st.spinner("..."):
                        r = call_ai_universal(f"解释：{q_text}。答案{q_ans}。解析{q.get('explanation')}")
                        if r: st.session_state[chat_key].append({"role":"model", "content":r})
                
                for m in st.session_state[chat_key]:
                    css = "chat-ai" if m['role']=="model" else "chat-user"
                    st.markdown(f"<div class='{css}'>{m['content']}</div>", unsafe_allow_html=True)
                
                if st.session_state[chat_key]:
                    ask = st.text_input("追问...", key=f"a_{idx}")
                    if st.button("发送", key=f"sa_{idx}") and ask:
                        st.session_state[chat_key].append({"role":"user", "content":ask})
                        r = call_ai_universal(ask, history=st.session_state[chat_key][:-1])
                        st.session_state[chat_key].append({"role":"model", "content":r})
                        st.rerun()

            st.markdown("---")
            c_next, c_end = st.columns([4, 1])
            with c_next:
                if st.button("➡️ 下一题", use_container_width=True):
                    st.session_state.q_idx += 1
                    st.rerun()
            with c_end:
                if st.button("🏁"): 
                    st.session_state.quiz_active = False; st.rerun()

# === ⚔️ 全真模考 ===
elif menu == "⚔️ 全真模考":
    st.title("⚔️ 全真模拟")
    if 'exam_session' not in st.session_state: st.session_state.exam_session = None
    
    if not st.session_state.exam_session:
        subjects = get_subjects()
        if subjects:
            s_name = st.selectbox("科目", [s['name'] for s in subjects])
            sid = next(s['id'] for s in subjects if s['name'] == s_name)
            if st.button("🚀 生成试卷", type="primary"):
                books = get_books(sid)
                bids = [b['id'] for b in books]
                if bids:
                    chaps = supabase.table("chapters").select("id").in_("book_id", bids).execute().data
                    cids = [c['id'] for c in chaps]
                    if cids:
                        qs = supabase.table("question_bank").select("*").in_("chapter_id", cids).limit(100).execute().data
                        if len(qs) >= 5:
                            random.shuffle(qs)
                            st.session_state.exam_session = {
                                "paper": qs[:10],
                                "answers": {},
                                "start_time": int(time.time()*1000),
                                "duration": 60,
                                "submitted": False
                            }
                            st.rerun()
                        else: st.error("题目不足")
                    else: st.error("无章节")
                else: st.error("无书籍")
    
    elif not st.session_state.exam_session['submitted']:
        session = st.session_state.exam_session
        end_ms = session['start_time'] + (session['duration'] * 60 * 1000)
        components.html(f"""<div style='position:fixed;top:60px;right:20px;z-index:9999;background:#dc3545;color:white;padding:5px 15px;border-radius:20px;font-family:monospace;font-weight:bold'>⏳ <span id='et'>--:--</span></div><script>setInterval(()=>{{var d=Math.floor(({end_ms}-Date.now())/1000);if(d<=0)document.getElementById('et').innerText='00:00';else document.getElementById('et').innerText=Math.floor(d/60).toString().padStart(2,'0')+':'+(d%60).toString().padStart(2,'0')}},1000)</script>""", height=0)
        
        with st.form("exam"):
            for i, q in enumerate(session['paper']):
                st.markdown(f"**{i+1}. {q['content']}**")
                q_ans = (q.get('correct_answer') or "").upper().replace(" ","")
                is_multi = len(q_ans) > 1 or q.get('type') == 'multi'
                if is_multi:
                    st.caption("多选")
                    opts = []
                    for o in q['options']:
                        if st.checkbox(o, key=f"e_m_{i}_{o}"): opts.append(o[0])
                    session['answers'][i] = "".join(sorted(opts))
                else:
                    val = st.radio("单选", q['options'], key=f"e_s_{i}", label_visibility="collapsed")
                    if val: session['answers'][i] = val[0]
                st.divider()
            
            if st.form_submit_button("交卷", type="primary"):
                session['submitted'] = True
                st.rerun()
    else:
        session = st.session_state.exam_session
        score = 0
        detail = []
        for i, q in enumerate(session['paper']):
            u = session['answers'].get(i, "")
            std = (q.get('correct_answer') or "").upper().replace(" ","")
            is_corr = (u == std)
            if is_corr: score += 10
            detail.append({"q": q['content'], "u": u, "std": std, "ok": is_corr, "exp": q.get('explanation')})
            if not is_corr:
                try: supabase.table("user_answers").insert({"user_id": user_id, "question_id": q['id'], "user_response": u, "is_correct": False}).execute()
                except: pass

        st.balloons()
        st.markdown(f"<h1 style='text-align:center; color:#00C090'>{score} 分</h1>", unsafe_allow_html=True)
        for d in detail:
            with st.expander(f"{'✅' if d['ok'] else '❌'} {d['q'][:20]}..."):
                st.write(d['q'])
                st.write(f"你: {d['u']} | 标: {d['std']}")
                st.info(d['exp'])
        if st.button("退出"):
            st.session_state.exam_session = None
            st.rerun()

# === 📊 弱项分析 ===
elif menu == "📊 弱项分析":
    st.title("📊 数据分析")
    try:
        rows = supabase.table("user_answers").select("*").order("created_at", desc=True).limit(500).execute().data
        if not rows: st.info("暂无数据")
        else:
            df = pd.DataFrame(rows)
            total = len(df)
            correct_count = len(df[df['is_correct'] == True])
            rate = int((correct_count / total) * 100)
            avg_time = int(df['time_taken'].mean()) if 'time_taken' in df.columns else 0
            
            c1, c2, c3 = st.columns(3)
            with c1: st.markdown(f"<div class='css-card' style='text-align:center'><div style='color:#888'>综合正确率</div><div style='font-size:32px; color:#0d6efd; font-weight:bold'>{rate}%</div></div>", unsafe_allow_html=True)
            with c2: st.markdown(f"<div class='css-card' style='text-align:center'><div style='color:#888'>刷题总数</div><div style='font-size:32px; color:#198754; font-weight:bold'>{total}</div></div>", unsafe_allow_html=True)
            with c3: st.markdown(f"<div class='css-card' style='text-align:center'><div style='color:#888'>平均耗时</div><div style='font-size:32px; color:#ffc107; font-weight:bold'>{avg_time}s</div></div>", unsafe_allow_html=True)

            st.divider()
            c_ch1, c_ch2 = st.columns(2)
            with c_ch1:
                st.subheader("📈 正确率")
                fig = px.pie(df, names='is_correct', color_discrete_map={True: '#00C090', False: '#FF7043'})
                st.plotly_chart(fig, use_container_width=True)
            with c_ch2:
                st.subheader("🔥 每日热度")
                df['date'] = pd.to_datetime(df['created_at']).dt.date
                fig2 = px.bar(df.groupby('date').size().reset_index(name='c'), x='date', y='c')
                fig2.update_traces(marker_color='#0d6efd')
                st.plotly_chart(fig2, use_container_width=True)

            st.divider()
            if st.button("生成深度诊断", type="primary"):
                with st.spinner("AI 分析中..."):
                    p = f"用户做了{total}题，正确率{rate}%，平均耗时{avg_time}s。给出学习建议。"
                    res = call_ai_universal(p)
                    if res: st.markdown(f"<div class='bs-card' style='border-left:5px solid #6610f2;background:#f3f0ff'>{res}</div>", unsafe_allow_html=True)
    except: st.error("数据加载失败")

# === ❌ 错题本 ===
elif menu == "❌ 错题本":
    st.title("❌ 错题集")
    try:
        errs = supabase.table("user_answers").select("*, question_bank(*)").eq("user_id", user_id).eq("is_correct", False).order("created_at", desc=True).execute().data
    except: errs = []
    
    unique_q = {}
    for e in errs:
        if e['question_id'] not in unique_q: unique_q[e['question_id']] = e
        
    if not unique_q: st.success("🎉 无错题")
    else:
        st.info(f"待复习：{len(unique_q)} 题")
        for qid, e in unique_q.items():
            q = e['question_bank']
            if not q: continue
            
            with st.expander(f"🔴 {q['content'][:30]}..."):
                st.markdown(f"### 📄 题目：\n{q['content']}")
                st.divider()
                if q.get('options') and isinstance(q['options'], list):
                    st.write("**选项：**")
                    for opt in q['options']:
                        st.markdown(f"<div class='option-item'>{opt}</div>", unsafe_allow_html=True)
                st.divider()
                
                c1, c2 = st.columns(2)
                c1.error(f"错选：{e['user_response']}")
                c2.success(f"正解：{q['correct_answer']}")
                
                st.info(f"💡 **解析：** {q['explanation']}")
                
                chat_hist = e.get('ai_chat_history') or []
                c_help, c_clr, c_del = st.columns([1.2, 1, 1])
                
                if not chat_hist:
                    if c_help.button("🤔 AI 举例", key=f"err_ex_{qid}"):
                        res = call_ai_universal(f"举例解释：{q['content']}。答案{q['correct_answer']}。")
                        if res:
                            nh = [{"role":"model", "content":res}]
                            supabase.table("user_answers").update({"ai_chat_history": nh}).eq("id", e['id']).execute()
                            st.rerun()
                else:
                    if c_clr.button("🗑️ 清除记忆", key=f"clr_{qid}"):
                        supabase.table("user_answers").update({"ai_chat_history": []}).eq("id", e['id']).execute()
                        st.rerun()
                
                if c_del.button("✅ 移除", key=f"rm_{qid}"):
                    supabase.table("user_answers").update({"is_correct": True}).eq("question_id", qid).execute()
                    st.rerun()
                
                if chat_hist:
                    st.markdown("---")
                    for m in chat_hist:
                        css = "chat-ai" if m['role']=="model" else "chat-user"
                        st.markdown(f"<div class='{css}'>{m['content']}</div>", unsafe_allow_html=True)
                    
                    with st.form(key=f"f_chat_{qid}"):
                        ask = st.text_input("追问...")
                        if st.form_submit_button("发送"):
                            chat_hist.append({"role":"user", "content":ask})
                            r = call_ai_universal(ask, history=chat_hist[:-1])
                            chat_hist.append({"role":"model", "content":r})
                            supabase.table("user_answers").update({"ai_chat_history": chat_hist}).eq("id", e['id']).execute()
                            st.rerun()

# === ⚙️ 设置中心 ===
elif menu == "⚙️ 设置中心":
    st.title("⚙️ 设置")
    
    curr = datetime.date(2025,9,6)
    if profile.get('exam_date'):
        try: curr = datetime.datetime.strptime(profile['exam_date'], '%Y-%m-%d').date()
        except: pass
    new_d = st.date_input("考试日期", curr)
    if new_d != curr:
        supabase.table("study_profile").update({"exam_date": str(new_d)}).eq("user_id", user_id).execute()
        st.rerun()
    
    st.divider()
    if st.button("📡 测试AI连通性"):
        res = call_ai_universal("Hi")
        if "Error" in res: st.error(res)
        else: st.success(f"通畅! 回复: {res}")
        
    st.markdown("#### 🧹 数据管理")
    if st.button("🗑️ 清空所有数据"):
        supabase.table("user_answers").delete().eq("user_id", user_id).execute()
        supabase.table("books").delete().eq("user_id", user_id).execute()
        st.success("已清空")
