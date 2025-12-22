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
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        font-family: 'Segoe UI', 'Roboto', sans-serif;
    }
    
    /* === 侧边栏：毛玻璃特效 === */
    [data-testid="stSidebar"] {
        background-color: rgba(255, 255, 255, 0.95);
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
        transform: translateY(-5px);
        box-shadow: 0 15px 30px rgba(0, 192, 144, 0.15);
        border-color: rgba(0, 192, 144, 0.3);
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
        color: white; border: none; border-radius: 50px; height: 45px; font-weight: 600;
        box-shadow: 0 4px 10px rgba(0, 192, 144, 0.3); transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px); box-shadow: 0 6px 15px rgba(0, 192, 144, 0.5); filter: brightness(1.1); color: white;
    }
    
    /* === 选项列表美化 === */
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
    
    /* === 成功提示框 === */
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

# 用户身份模拟 (生产环境需对接 st.login)
if 'user_id' not in st.session_state:
    st.session_state.user_id = "test_user_001"
user_id = st.session_state.user_id

# ==============================================================================
# 3. 核心功能函数
# ==============================================================================

# --- AI 调用 (通用版) ---
def call_ai_universal(prompt, history=[], model_override=None):
    """支持 Gemini / DeepSeek / OpenRouter 的通用接口"""
    # 1. 获取用户配置
    profile = get_user_profile(st.session_state.get('user_id'))
    settings = profile.get('settings') or {}
    
    # 获取用户设定的超时时间，默认 60 秒
    current_timeout = settings.get('ai_timeout', 60)
    
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
            
            # 使用动态超时时间
            resp = requests.post(url, headers=headers, json={"contents": contents}, timeout=current_timeout)
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

            messages = [{"role": "system", "content": "你是一位资深会计讲师。回答请使用 Markdown 格式。"}]
            for h in history:
                role = "assistant" if h['role'] == "model" else h['role']
                messages.append({"role": role, "content": h['content']})
            messages.append({"role": "user", "content": prompt})

            # 使用动态超时时间
            resp = client.chat.completions.create(
                model=target_model, 
                messages=messages, 
                temperature=0.7,
                timeout=current_timeout # 🔥 关键修改
            )
            return resp.choices[0].message.content

    except Exception as e:
        return f"AI 连接超时或异常 (当前限制 {current_timeout}秒): {e}"
        
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
    
    # --- 导航菜单 ---
    menu = st.radio("功能导航", [
        "🏠 仪表盘",
        "📂 智能拆书 & 资料",
        "🎓 AI 课堂 (讲义)",
        "📝 章节特训 (刷题)",
        "⚔️ 全真模考",
        "📊 弱项分析",
        "❌ 错题本",
        "⚙️ 设置中心"
    ], label_visibility="collapsed")
    
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
# 5. 主功能区
# ==============================================================================

# === 🏠 仪表盘 ===
if menu == "🏠 仪表盘":
    st.markdown("### 👋 欢迎回来，开始高效学习")
    
    # Bento Grid 核心指标
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
        st.markdown(f"""
        <div class="css-card">
            <i class="bi bi-bookmark-x-fill stat-icon" style="color:#dc3545"></i>
            <div class="stat-title">待复习错题</div>
            <div class="stat-value">--</div>
        </div>
        """, unsafe_allow_html=True)

# =========================================================
# 📂 智能拆书 & 资料 (V3.1：分类处理 + 智能拆分 + 管理)
# =========================================================
elif menu == "📂 智能拆书 & 资料":
    st.title("📂 资料库管理")
    
    subjects = get_subjects()
    if not subjects: st.error("请先在数据库初始化科目数据"); st.stop()
    
    # --- 1. 顶层选择器 ---
    c1, c2 = st.columns([1, 2])
    with c1:
        s_name = st.selectbox("1. 所属科目", [s['name'] for s in subjects])
        sid = next(s['id'] for s in subjects if s['name'] == s_name)
    
    with c2:
        books = get_books(sid)
        b_opts = ["➕ 上传新资料 (PDF)..."] + [b['title'] for b in books]
        sel_book = st.selectbox("2. 选择书籍/资料包", b_opts)
    
    st.divider()

    # =====================================================
    # 分支 A: 上传新书 (分类智能拆书)
    # =====================================================
    if "上传新" in sel_book:
        st.markdown("#### 📤 智能拆书台")
        
        # 1. 核心改进：前置分类选择
        doc_type = st.radio("请告诉 AI 这份资料的类型：", 
                           ["📖 教材/知识点汇总 (用于学习)", "📑 习题集/真题卷 (用于刷题)"], 
                           horizontal=True)
        
        up_file = st.file_uploader("上传 PDF 文件", type="pdf")
        
        if up_file:
            try:
                # 检查 PDF
                with pdfplumber.open(up_file) as pdf: total_pages = len(pdf.pages)
                st.success(f"文件已加载，共 {total_pages} 页")
                
                # Session 状态管理
                if 'toc_analysis' not in st.session_state:
                    
                    if st.button("🚀 Step 1: 开始 AI 目录分析", type="primary"):
                        
                        # A. 读取目录文字
                        with st.spinner("正在读取前 20 页目录..."):
                            toc_text = extract_pdf(up_file, 1, min(20, total_pages))
                        
                        if len(toc_text) < 50:
                            st.error("无法提取目录文字，请检查是否为扫描版 PDF。")
                        else:
                            # B. AI 分析 (根据类型调整 Prompt)
                            with st.spinner(f"AI 正在识别{'章节结构' if '教材' in doc_type else '试卷结构'}..."):
                                
                                # 差异化 Prompt
                                if "教材" in doc_type:
                                    role_desc = "你是一个图书编辑。"
                                    task_desc = "提取书中的【章节目录】（如第一章、第二章...）。"
                                else:
                                    role_desc = "你是一个考试院管理员。"
                                    task_desc = "提取书中的【试卷名称】或【章节练习题】（如 2024真题、第一章练习题...）。"
                                
                                p = f"""
                                {role_desc} 请分析以下目录文本。
                                任务：{task_desc}
                                总页数：{total_pages}。
                                
                                【必须】返回纯 JSON 列表，格式：
                                [
                                    {{"title": "名称...", "start_page": 5, "end_page": 10}}
                                ]
                                如果目录不清晰，请根据文本逻辑合理推断起止页码。
                                
                                待分析文本：
                                {toc_text[:8000]}
                                """
                                
                                # 强力清洗逻辑
                                res = call_ai_universal(p)
                                if res:
                                    try:
                                        clean = res.replace("```json","").replace("```","").strip()
                                        s_idx = clean.find('[')
                                        e_idx = clean.rfind(']') + 1
                                        if s_idx != -1 and e_idx != -1: clean = clean[s_idx:e_idx]
                                        
                                        st.session_state.toc_analysis = json.loads(clean)
                                        st.rerun()
                                    except Exception as e:
                                        st.error("AI 解析目录失败")
                                        with st.expander("查看原始返回"): st.text(res)
                                else:
                                    st.error("网络请求超时，请重试")

                # Step 2: 确认与切分
                if 'toc_analysis' in st.session_state:
                    st.write("##### 📝 Step 2: 确认拆分结构")
                    edited_df = st.data_editor(
                        st.session_state.toc_analysis, 
                        num_rows="dynamic",
                        column_config={
                            "title": "章节/试卷名称",
                            "start_page": st.column_config.NumberColumn("起始页", min_value=1),
                            "end_page": st.column_config.NumberColumn("结束页", min_value=1)
                        }, use_container_width=True
                    )
                    
                    if st.button("✂️ Step 3: 执行拆分并保存"):
                        progress_bar = st.progress(0)
                        status_box = st.empty()
                        
                        try:
                            # 1. 建书
                            book_res = supabase.table("books").insert({
                                "user_id": user_id, "subject_id": sid, "title": up_file.name.replace(".pdf",""), "total_pages": total_pages
                            }).execute()
                            bid = book_res.data[0]['id']
                            
                            # 2. 循环处理
                            total_items = len(edited_df)
                            for i, item in enumerate(edited_df):
                                status_box.info(f"正在处理 ({i+1}/{total_items}): {item['title']}")
                                
                                # 提取该段落文字
                                up_file.seek(0)
                                txt = extract_pdf(up_file, item['start_page'], item['end_page'])
                                
                                if len(txt) > 10:
                                    # 存章节
                                    c_res = supabase.table("chapters").insert({
                                        "book_id": bid, "title": item['title'], 
                                        "start_page": item['start_page'], "end_page": item['end_page'], 
                                        "user_id": user_id
                                    }).execute()
                                    cid = c_res.data[0]['id']
                                    
                                    # 存内容 (打上标签)
                                    src_type = "textbook" if "教材" in doc_type else "real_exam"
                                    save_material_v3(cid, txt, user_id) # 默认存入 materials 表
                                    
                                    # 🔥 如果是习题集，尝试自动标记 (可选高级功能)
                                    # 这里先只存文本，在后续“管理”界面提供一键提取按钮
                                
                                progress_bar.progress((i+1)/total_items)
                            
                            st.balloons()
                            st.success("✅ 资料已全部入库！")
                            del st.session_state.toc_analysis
                            time.sleep(2)
                            st.rerun()
                        except Exception as e:
                            st.error(f"入库失败: {e}")

            except Exception as e:
                st.error(f"文件读取错误: {e}")

    # =====================================================
    # 分支 B: 已有书籍管理 (管理 + 提取)
    # =====================================================
    elif books:
        # 获取当前书 ID
        bid = next(b['id'] for b in books if b['title'] == sel_book)
        chapters = get_chapters(bid)
        
        # --- 顶部管理区 ---
        c_title, c_del = st.columns([4, 1])
        with c_title:
            st.markdown(f"### 📘 {sel_book}")
        with c_del:
            # 🔥 之前的删除功能保留在这里
            with st.popover("⚙️ 管理", use_container_width=True):
                st.warning("危险操作")
                if st.button("🗑️ 删除此书", key="del_book_btn"):
                    supabase.table("books").delete().eq("id", bid).execute()
                    st.success("已删除")
                    time.sleep(1)
                    st.rerun()

        if not chapters:
            st.warning("本书无章节数据。")
        else:
            # 章节选择
            c_chap, c_stat = st.columns([2, 1])
            with c_chap:
                sel_chap = st.selectbox("选择章节/试卷", [c['title'] for c in chapters])
                cid = next(c['id'] for c in chapters if c['title'] == sel_chap)
            
            # 获取该章节已有的资料
            mats = supabase.table("materials").select("content").eq("chapter_id", cid).execute().data
            q_count = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", cid).execute().count
            
            with c_stat:
                st.markdown(f"""
                <div style='text-align:right; margin-top:20px; color:#666'>
                    📄 文本: {'✅ 有' if mats else '❌ 无'} <br> 
                    📝 题目: <b>{q_count}</b> 道
                </div>
                """, unsafe_allow_html=True)

            st.divider()

            # --- 功能 Tabs ---
            # 根据是否有文本资料，动态显示功能
            t1, t2 = st.tabs(["🧠 AI 提取/生成", "👀 查看原始内容"])
            
            with t1:
                if not mats:
                    st.warning("该章节没有文本内容，无法处理。")
                    st.caption("可能是拆书时提取失败，或者上传的是纯图片 PDF。")
                    # 补录入口
                    re_up = st.file_uploader("补录 PDF/Word", type=['pdf','docx'], key=f"re_{cid}")
                    if re_up and st.button("上传补录"):
                        txt = extract_pdf(re_up) if re_up.name.endswith('.pdf') else extract_text_from_docx(re_up)
                        save_material_v3(cid, txt, user_id)
                        st.experimental_rerun()
                else:
                    # 核心处理区
                    raw_text = mats[0]['content']
                    st.info(f"本章包含 {len(raw_text)} 字的文本资料。")
                    
                    c_gen_type = st.radio("你想做什么？", ["📝 从中提取题目 (它是习题集)", "🎓 生成学习讲义 (它是教材)"], horizontal=True)
                    
                    # 选项 A: 提取题目
                    if "提取题目" in c_gen_type:
                        hint = st.text_input("提示词 (例如：只提取选择题，忽略水印)", value="")
                        if st.button("🚀 开始 AI 识别题目", type="primary"):
                            with st.spinner("AI 正在扫描题目..."):
                                p = f"""
                                从以下文本中提取会计题目。
                                提示：{hint}
                                必须返回纯 JSON 列表：[{{ "question": "...", "options": ["A.","B."], "answer": "A", "explanation": "..." }}]
                                文本：{raw_text[:15000]}
                                """
                                res = call_ai_universal(p)
                                if res:
                                    try:
                                        clean = res.replace("```json","").replace("```","").strip()
                                        s = clean.find('['); e = clean.rfind(']')+1
                                        data = json.loads(clean[s:e])
                                        
                                        # 存入
                                        fmt = [{"question":x['content'], "options":x['options'], "answer":x['correct_answer'], "explanation":x['explanation']} for x in data]
                                        save_questions_v3(fmt, cid, user_id, origin="extraction")
                                        st.success(f"成功提取并存入 {len(data)} 道题！")
                                    except: st.error("AI 提取失败，格式错误")

                    # 选项 B: 生成讲义
                    else:
                        if st.button("✨ 生成生活化讲义"):
                            with st.spinner("AI 老师正在备课..."):
                                p = f"生成通俗易懂的讲义，包含生活案例。内容：{raw_text[:15000]}"
                                res = call_ai_universal(p)
                                if res:
                                    m_name = st.session_state.get('selected_provider', 'AI')
                                    supabase.table("ai_lessons").insert({
                                        "chapter_id": cid, "user_id": user_id, "title": f"{m_name} 讲义", "content": res, "ai_model": m_name
                                    }).execute()
                                    st.success("讲义已生成，请去【AI 课堂】查看！")

            with t2:
                if mats:
                    st.text_area("原始内容预览", mats[0]['content'], height=300)
                else:
                    st.caption("无内容")
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
            # 显示已有讲义
            lessons = supabase.table("ai_lessons").select("*").eq("chapter_id", cid).order("created_at", desc=True).execute().data
            if lessons:
                tabs = st.tabs([l['title'] or "未命名" for l in lessons])
                for i, tab in enumerate(tabs):
                    with tab:
                        st.markdown(lessons[i]['content'])
            else:
                st.info("暂无讲义")
                
            # 生成新讲义
            if st.button("✨ 生成新讲义"):
                mats = supabase.table("materials").select("content").eq("chapter_id", cid).execute().data
                if mats:
                    with st.spinner("AI 备课中..."):
                        p = f"根据内容生成通俗讲义。内容：{mats[0]['content'][:15000]}"
                        res = call_ai_universal(p)
                        if res:
                            model_name = st.session_state.get('openrouter_model_id') or "Gemini"
                            supabase.table("ai_lessons").insert({
                                "chapter_id": cid, "user_id": user_id, "title": f"{model_name}版", "content": res, "ai_model": model_name
                            }).execute()
                            st.rerun()

# === 📝 章节特训 (刷题) ===
elif menu == "📝 章节特训 (刷题)":
    st.title("📝 章节突破")
    
    # JS 计时器
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
                # 进度条
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
                
                if st.button("🚀 开始刷题", type="primary", use_container_width=True):
                    qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).limit(20).execute().data
                    if qs:
                        random.shuffle(qs)
                        st.session_state.quiz_data = qs[:10]
                        st.session_state.q_idx = 0
                        st.session_state.quiz_active = True
                        st.session_state.js_start_time = int(time.time() * 1000)
                        st.rerun()
                    else: st.error("本章无题")

    # 做题界面
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
                    supabase.table("user_answers").insert({"user_id": user_id, "question_id": q['id'], "user_response": user_val, "is_correct": True}).execute()
                else:
                    st.error(f"❌ 错误。答案：{q_ans}")
                    # 防重复插入逻辑
                    exist = supabase.table("user_answers").select("id").eq("user_id", user_id).eq("question_id", q['id']).eq("is_correct", False).execute().data
                    if exist:
                        supabase.table("user_answers").update({"created_at": datetime.datetime.now().isoformat()}).eq("id", exist[0]['id']).execute()
                    else:
                        supabase.table("user_answers").insert({"user_id": user_id, "question_id": q['id'], "user_response": user_val, "is_correct": False}).execute()
                
                st.info(f"解析：{q.get('explanation')}")
                
                # AI 举例
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
                # 跨章节组卷逻辑
                # 1. 找该科目下所有书 -> 所有章 -> 所有题
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
    
    # 考试中
    elif not st.session_state.exam_session['submitted']:
        session = st.session_state.exam_session
        
        # JS 倒计时
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
    
    # 考后报告
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
            
            # 存入错题 (非阻塞)
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
    st.title("📊 学习效果分析")
    
    # 1. 获取数据 (联表查询有点慢，这里只查记录表，用 Python 处理)
    try:
        # 获取最近 500 条做题记录
        rows = supabase.table("user_answers").select("*").order("created_at", desc=True).limit(500).execute().data
        
        if not rows:
            st.info("暂无做题数据，快去【章节特训】或【全真模考】刷几道题吧！")
        else:
            df = pd.DataFrame(rows)
            
            # --- 核心指标卡 ---
            total = len(df)
            correct_count = len(df[df['is_correct'] == True])
            rate = int((correct_count / total) * 100)
            
            # 计算平均耗时 (秒)
            avg_time = int(df['time_taken'].mean()) if 'time_taken' in df.columns else 0
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"<div class='css-card' style='text-align:center'><div style='color:#888'>综合正确率</div><div style='font-size:32px; color:#0d6efd; font-weight:bold'>{rate}%</div></div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div class='css-card' style='text-align:center'><div style='color:#888'>刷题总数</div><div style='font-size:32px; color:#198754; font-weight:bold'>{total}</div></div>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div class='css-card' style='text-align:center'><div style='color:#888'>平均每题耗时</div><div style='font-size:32px; color:#ffc107; font-weight:bold'>{avg_time}s</div></div>", unsafe_allow_html=True)

            st.divider()

            # --- 图表区 ---
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.subheader("📈 正确率分布")
                # 饼图
                fig_pie = px.pie(df, names='is_correct', title='正误比例', 
                                color_discrete_map={True: '#00C090', False: '#FF7043'},
                                labels={'is_correct': '是否正确', 'True': '正确', 'False': '错误'})
                st.plotly_chart(fig_pie, use_container_width=True)
                
            with col_chart2:
                st.subheader("🔥 每日刷题热度")
                # 柱状图
                df['date'] = pd.to_datetime(df['created_at']).dt.date
                daily_counts = df.groupby('date').size().reset_index(name='count')
                fig_bar = px.bar(daily_counts, x='date', y='count', title='每日刷题量')
                fig_bar.update_traces(marker_color='#0d6efd')
                st.plotly_chart(fig_bar, use_container_width=True)

            # --- AI 诊断区 ---
            st.divider()
            st.subheader("🩺 AI 学习诊断")
            
            if st.button("生成深度分析报告", type="primary"):
                with st.spinner("AI 正在分析你的做题习惯与薄弱点..."):
                    # 简化的分析 Prompt
                    prompt = f"""
                    用户最近做了 {total} 道会计题，正确率为 {rate}%。
                    平均每题耗时 {avg_time} 秒。
                    请根据这些数据，给出一份简短的学习建议。
                    指出他可能存在的问题（如：是否做得太快导致粗心？还是基础不牢？）。
                    语气：鼓励且专业。
                    """
                    advice = call_ai_universal(prompt)
                    if advice:
                        st.markdown(f"""
                        <div class="bs-card" style="border-left: 5px solid #6610f2; background-color: #f3f0ff;">
                            <h5>🤖 你的专属诊断书：</h5>
                            {advice}
                        </div>
                        """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"数据加载失败: {e}")

# === ❌ 错题本 (去重 + 记忆) ===
elif menu == "❌ 错题本":
    st.title("❌ 错题集")
    # 联表查询
    try:
        errs = supabase.table("user_answers").select("*, question_bank(*)").eq("user_id", user_id).eq("is_correct", False).order("created_at", desc=True).execute().data
    except: errs = []
    
    unique_q = {}
    for e in errs:
        if e['question_id'] not in unique_q: unique_q[e['question_id']] = e
        
    if not unique_q:
        st.success("🎉 无错题！")
    else:
        st.info(f"待复习：{len(unique_q)} 题")
        for qid, e in unique_q.items():
            q = e['question_bank']
            if not q: continue
            
            with st.expander(f"🔴 {q['content'][:30]}..."):
                # 题目 & 选项美化
                st.markdown(f"**题目：** {q['content']}")
                if q.get('options'):
                    for o in q['options']:
                        st.markdown(f"<div class='option-item'>{o}</div>", unsafe_allow_html=True)
                
                c1, c2 = st.columns(2)
                c1.error(f"错选：{e['user_response']}")
                c2.success(f"正解：{q['correct_answer']}")
                
                st.info(f"💡 **解析：** {q['explanation']}")
                
                # 功能区
                chat_hist = e.get('ai_chat_history') or []
                c_help, c_del = st.columns([3, 1])
                
                if c_help.button("🤔 AI 举例", key=f"err_ex_{qid}"):
                    if not chat_hist:
                        res = call_ai_universal(f"举例解释：{q['content']}。答案{q['correct_answer']}。")
                        if res:
                            nh = [{"role":"model", "content":res}]
                            supabase.table("user_answers").update({"ai_chat_history": nh}).eq("id", e['id']).execute()
                            st.rerun()
                
                if c_del.button("✅ 移除", key=f"err_rm_{qid}"):
                    # 批量移除
                    supabase.table("user_answers").update({"is_correct": True}).eq("question_id", qid).execute()
                    st.rerun()
                
                # 聊天记录
                if chat_hist:
                    st.markdown("---")
                    for m in chat_hist:
                        css = "chat-ai" if m['role']=="model" else "chat-user"
                        st.markdown(f"<div class='{css}'>{m['content']}</div>", unsafe_allow_html=True)
                    
                    ask = st.text_input("追问...", key=f"e_ask_{qid}")
                    if st.button("发送", key=f"e_snd_{qid}") and ask:
                        chat_hist.append({"role":"user", "content":ask})
                        r = call_ai_universal(ask, history=chat_hist[:-1])
                        chat_hist.append({"role":"model", "content":r})
                        supabase.table("user_answers").update({"ai_chat_history": chat_hist}).eq("id", e['id']).execute()
                        st.rerun()

# === ⚙️ 设置中心 ===
elif menu == "⚙️ 设置中心":
    st.title("⚙️ 系统偏好设置")
    
    # 读取当前配置
    current_settings = profile.get('settings') or {}
    
    # --- 1. AI 模型配置与测试 ---
    st.markdown("#### 🤖 AI 模型配置")
    with st.container():
        c_test, c_timeout = st.columns([1, 2])
        
        with c_test:
            st.info(f"当前大脑：**{st.session_state.get('selected_provider')}**")
            if st.button("📡 测试连通性", use_container_width=True):
                with st.spinner(f"正在呼叫 {st.session_state.get('selected_provider')}..."):
                    start_t = time.time()
                    # 发送简单指令测试
                    res = call_ai_universal("Say 'Hello' in one word.")
                    duration = time.time() - start_t
                    
                    if "Error" in res or "异常" in res:
                        st.error(f"❌ 连接失败: {res}")
                    else:
                        st.success(f"✅ 连接畅通! 耗时 {duration:.2f}s")
                        st.caption(f"AI回复: {res}")

        with c_timeout:
            # 获取当前超时设置，默认60
            saved_timeout = current_settings.get('ai_timeout', 60)
            new_timeout = st.slider(
                "⏳ AI 回答最大等待时间 (秒)", 
                min_value=10, 
                max_value=300, 
                value=saved_timeout,
                help="如果遇到 Read timed out 错误，请尝试调大此数值 (建议 60-120秒)"
            )
            
            # 自动保存设置
            if new_timeout != saved_timeout:
                update_settings(user_id, {"ai_timeout": new_timeout})
                st.toast(f"超时时间已更新为 {new_timeout} 秒")

    st.divider()

    # --- 2. 考试目标设定 (含联网功能) ---
    st.markdown("#### 📅 考试倒计时")
    
    # 联网自动配置按钮
    if st.button("🌐 联网搜索最新考试时间 (AI自动配置)"):
        with st.spinner("正在检索‘财政部会计资格评价中心’最新公告..."):
            # 这里模拟 AI 搜索过程，实际可接入 Google Search Tool
            # 为了演示，我们调用 AI 让它根据当前年份推测
            prompt = f"现在是{datetime.date.today().year}年。请根据中国中级会计职称考试通常在9月上旬的惯例，推测今年的考试日期。仅返回日期格式 YYYY-MM-DD，不要其他文字。"
            ai_date = call_ai_universal(prompt)
            
            try:
                # 简单的清洗逻辑
                clean_date_str = ai_date.strip().replace("\n", "")[:10]
                datetime.datetime.strptime(clean_date_str, '%Y-%m-%d') # 校验格式
                
                # 更新数据库
                supabase.table("study_profile").update({"exam_date": clean_date_str}).eq("user_id", user_id).execute()
                st.success(f"✅ AI 已自动同步考试日期：{clean_date_str}")
                time.sleep(1)
                st.rerun()
            except:
                st.warning("AI 返回的日期格式难以识别，请手动设置。")

    # 手动设置区
    curr_date = datetime.date(2025, 9, 6) # 默认兜底
    if profile.get('exam_date'):
        try: curr_date = datetime.datetime.strptime(profile['exam_date'], '%Y-%m-%d').date()
        except: pass
        
    new_d = st.date_input("设定目标日期", curr_date)
    if new_d != curr_date:
        supabase.table("study_profile").update({"exam_date": str(new_d)}).eq("user_id", user_id).execute()
        st.toast("日期已更新")
        time.sleep(1)
        st.rerun()
    
    st.divider()
    
    # --- 3. 数据与隐私 ---
    st.markdown("#### 🧹 数据管理")
    with st.expander("危险操作区"):
        st.warning("以下操作不可逆，请谨慎！")
        if st.button("🗑️ 清空所有错题与刷题记录"):
            supabase.table("user_answers").delete().eq("user_id", user_id).execute()
            supabase.table("mock_exams").delete().eq("user_id", user_id).execute()
            st.success("已清空所有学习记录，一切重新开始！")
            time.sleep(1)
            st.rerun()









