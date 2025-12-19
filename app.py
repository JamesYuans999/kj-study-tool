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

def save_model_preference():
    """回调函数：当用户改变模型时，自动保存到 Supabase"""
    if st.session_state.get('user_id') and st.session_state.get('openrouter_model_select'):
        current_model = st.session_state.openrouter_model_select
        # 更新数据库
        update_settings(st.session_state.user_id, {"last_used_model": current_model})
        st.toast(f"已记住模型：{current_model}", icon="💾")


def call_ai_universal(prompt, history=[]):
    """
    通用 AI 调用接口 (支持 Gemini / DeepSeek / OpenRouter)
    自动读取 st.session_state 中的模型配置
    """
    # 1. 获取用户选择的厂商 (默认为 Gemini)
    provider = st.session_state.get('selected_provider', 'Gemini')
    
    # 2. 获取具体模型 ID (如果是 OpenRouter 或 DeepSeek)
    # 默认为 Gemini 2.0 Flash (OpenRouter上的免费神模)
    target_model = st.session_state.get('openrouter_model_id', 'google/gemini-2.0-flash-exp:free')
    
    try:
        # === 分支 A: Google Gemini 官方直连 ===
        if "Gemini" in provider:
            # 使用 secrets 中的 Google Key
            api_key = st.secrets["GOOGLE_API_KEY"]
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            
            # 转换历史格式为 Gemini 格式
            contents = []
            for h in history:
                role = "user" if h['role'] == 'user' else "model"
                contents.append({"role": role, "parts": [{"text": h['content']}]})
            contents.append({"role": "user", "parts": [{"text": prompt}]})
            
            data = {"contents": contents}
            
            # 发送请求
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                return f"Gemini 报错 ({response.status_code}): {response.text}"

        # === 分支 B: OpenAI 兼容接口 (DeepSeek / OpenRouter) ===
        else:
            client = None
            
            # 配置客户端
            if "DeepSeek" in provider:
                if "deepseek" not in st.secrets: return "请在 secrets.toml 配置 [deepseek]"
                client = OpenAI(
                    api_key=st.secrets["deepseek"]["api_key"], 
                    base_url=st.secrets["deepseek"]["base_url"]
                )
                # DeepSeek 官方 API 通常只支持 deepseek-chat 或 deepseek-reasoner
                # 如果 target_model 是 OpenRouter 的格式，这里强制修正为 deepseek-chat
                if "/" in target_model: target_model = "deepseek-chat"
                
            elif "OpenRouter" in provider:
                if "openrouter" not in st.secrets: return "请在 secrets.toml 配置 [openrouter]"
                client = OpenAI(
                    api_key=st.secrets["openrouter"]["api_key"], 
                    base_url=st.secrets["openrouter"]["base_url"]
                )
                # OpenRouter 必须使用完整的 model id (如 google/gemini...)

            if not client: return "AI 客户端初始化失败"

            # 转换历史格式为 OpenAI 格式
            messages = [{"role": "system", "content": "你是一位资深会计讲师，擅长用通俗的生活案例解释复杂的财务概念。"}]
            for h in history:
                # 兼容 Gemini 的 'model' 角色名转为 'assistant'
                role = "assistant" if h['role'] == "model" else h['role']
                messages.append({"role": role, "content": h['content']})
            messages.append({"role": "user", "content": prompt})

            # 发送请求
            response = client.chat.completions.create(
                model=target_model,
                messages=messages,
                temperature=0.7
            )
            return response.choices[0].message.content

    except Exception as e:
        return f"AI 调用发生异常: {str(e)}"


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
    
    # --- 1. AI 大脑设置 (修复报错版) ---
    ai_provider = st.selectbox(
        "🧠 AI 大脑", 
        ["Gemini (官方直连)", "DeepSeek (官方直连)", "OpenRouter (聚合平台)"]
    )
    st.session_state.selected_provider = ai_provider
    
    target_model_id = None
    
    # === OpenRouter 专属逻辑 ===
    if "OpenRouter" in ai_provider:
        # 1. 获取 Key
        or_key = st.secrets.get("openrouter", {}).get("api_key")
        
        # 2. 获取上次保存的模型 (记忆功能)
        user_settings = profile.get('settings') or {}
        last_used_model = user_settings.get('last_used_model')
        
        # 3. 联网获取列表 (调用新函数)
        all_models = fetch_openrouter_models(or_key)
        
        if not all_models:
            st.warning("⚠️ 无法连接 OpenRouter，使用默认列表")
            filtered_ids = ["google/gemini-2.0-flash-exp:free", "deepseek/deepseek-r1:free"]
        else:
            # 4. 筛选器 (解决你之前的需求)
            filter_type = st.radio("模型筛选", ["🤑 仅显示免费", "🌎 显示全部"], horizontal=True)
            
            if "免费" in filter_type:
                filtered_models = [m for m in all_models if m['is_free']]
            else:
                filtered_models = all_models
            
            filtered_ids = [m['id'] for m in filtered_models]
            if not filtered_ids: filtered_ids = [m['id'] for m in all_models]

        # 5. 智能定位默认值
        default_index = 0
        if last_used_model in filtered_ids:
            default_index = filtered_ids.index(last_used_model)
        
        # 6. 渲染选择框
        target_model_id = st.selectbox(
            "🔌 选择模型",
            filtered_ids,
            index=default_index,
            key="openrouter_model_select",
            on_change=save_model_preference,
            help="选择的模型会自动保存，下次打开默认选中"
        )
        
        # 显示是否免费
        is_free_tag = "🆓 免费" if ":free" in target_model_id or "free" in target_model_id.lower() else "💲 可能收费"
        st.caption(f"当前: `{target_model_id}` ({is_free_tag})")

    # === DeepSeek 专属逻辑 ===
    elif "DeepSeek" in ai_provider:
        # DeepSeek 官方只有两个主要模型
        target_model_id = st.selectbox("🔌 选择 DeepSeek 版本", ["deepseek-chat", "deepseek-reasoner"])

    # 存入全局状态
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

    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f"<div class='css-card'>📚 累计刷题<div class='big-number'>{profile.get('total_questions_done', 0)}</div></div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='css-card'>🎯 目标分数<div class='big-number'>90+</div></div>", unsafe_allow_html=True)
    with c3: st.markdown(f"<div class='css-card'>🔥 连续打卡<div class='big-number'>{profile.get('study_streak', 1)} 天</div></div>", unsafe_allow_html=True)

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
    
    # --- 1. 计时器逻辑 ---
    if 'q_timer' not in st.session_state: st.session_state.q_timer = time.time()
    
    # 只有在刷题激活状态下显示悬浮计时器
    if st.session_state.get('quiz_active'):
        el = int(time.time() - st.session_state.q_timer)
        st.markdown(f"<div class='timer-box'>⏱️ {el//60:02d}:{el%60:02d}</div>", unsafe_allow_html=True)

    # --- 2. 章节选择与启动区 ---
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
                    
                    # 显示库存数据
                    try:
                        q_count = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", cid).execute().count
                        st.caption(f"当前章节库存真题：{q_count} 道")
                    except: pass
                    
                    st.divider()
                    
                    # 模式选择
                    mode = st.radio("练习模式", ["🎲 刷真题库存", "🧠 AI 基于教材出新题"], horizontal=True)
                    
                    if st.button("🚀 开始练习", type="primary", use_container_width=True):
                        st.session_state.quiz_cid = cid
                        st.session_state.q_timer = time.time()
                        
                        # A. 刷真题模式
                        if "真题" in mode:
                            # 简单随机抽取 10 题
                            qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).limit(10).execute().data
                            if qs:
                                import random
                                random.shuffle(qs) # 内存洗牌
                                st.session_state.quiz_data = qs
                                st.session_state.q_idx = 0
                                st.session_state.quiz_active = True
                                st.rerun()
                            else: 
                                st.error("该章节题库为空，请先去资料库录入。")
                        
                        # B. AI 出题模式
                        else:
                            mats = supabase.table("materials").select("content").eq("chapter_id", cid).execute().data
                            if mats:
                                txt = "\n".join([m['content'] for m in mats])
                                with st.spinner("AI 正在阅读教材并出题..."):
                                    p = f"基于内容出3道单选题。内容：{txt[:6000]}。格式JSON：[{{'content':'..','options':['A..'],'correct_answer':'A','explanation':'..'}}]。"
                                    r = call_ai_universal(p) # 使用通用接口
                                    if r:
                                        try:
                                            # 清洗与解析
                                            clean_json = r.replace("```json","").replace("```","").strip()
                                            d = json.loads(clean_json)
                                            
                                            # 存入数据库 (变成真题)
                                            formatted_qs = [{'question':x['content'], 'options':x['options'], 'answer':x['correct_answer'], 'explanation':x['explanation']} for x in d]
                                            save_questions_batch(formatted_qs, cid, user_id)
                                            
                                            # 加载到当前练习
                                            st.session_state.quiz_data = d
                                            st.session_state.q_idx = 0
                                            st.session_state.quiz_active = True
                                            st.rerun()
                                        except: st.error("生成失败，请重试")
                            else: st.error("该章节没有教材资料")
                else:
                    st.warning("该科目下暂无章节，请去资料库新建。")

    # --- 3. 做题交互界面 ---
    if st.session_state.get('quiz_active'):
        idx = st.session_state.q_idx
        total = len(st.session_state.quiz_data)
        q = st.session_state.quiz_data[idx]
        
        # 兼容字段名 (数据库字段 vs AI生成字段)
        q_text = q.get('content') or q.get('question')
        q_ans = q.get('correct_answer') or q.get('answer')
        q_exp = q.get('explanation', '暂无解析')
        q_opts = q.get('options', [])
        
        # 进度条
        st.progress((idx+1)/total)
        
        # 题目卡片
        st.markdown(f"""
        <div class='css-card'>
            <span style='color:#888; font-size:12px'>Question {idx+1}/{total}</span>
            <h4>{q_text}</h4>
        </div>
        """, unsafe_allow_html=True)
        
        # 选项
        sel = st.radio("请选择答案：", q_opts, key=f"q_{idx}")
        
        # 提交状态控制
        sub_key = f"sub_{idx}"
        if sub_key not in st.session_state: st.session_state[sub_key] = False
        
        # 提交按钮
        if st.button("✅ 提交", use_container_width=True) and not st.session_state[sub_key]:
            st.session_state[sub_key] = True
            
        # --- 判分与保存逻辑 (核心修改点) ---
        if st.session_state[sub_key]:
            user_val = sel[0] if sel else ""
            
            if user_val == q_ans: 
                st.markdown(f"<div class='success-box'>🎉 回答正确！</div>", unsafe_allow_html=True)
                # (可选) 答对了可以将之前的错题记录标记为已掌握
                # if q.get('id'): supabase.table("user_answers").update({"is_correct": True}).eq("question_id", q['id']).execute()
            else: 
                st.error(f"❌ 遗憾答错。正确答案是：{q_ans}")
                
                # 🔥🔥🔥 防止重复保存逻辑 🔥🔥🔥
                if q.get('id'): # 只有当题目已入库有ID时才记录
                    try:
                        # 1. 检查是否已存在该题的"未掌握"记录
                        existing = supabase.table("user_answers").select("id").eq("user_id", user_id).eq("question_id", q['id']).eq("is_correct", False).execute().data
                        
                        if existing:
                            # 2. 如果已存在，仅更新时间戳和最新答案，避免产生双胞胎记录
                            rec_id = existing[0]['id']
                            supabase.table("user_answers").update({
                                "user_response": user_val,
                                "created_at": datetime.datetime.now().isoformat() # 顶上来
                            }).eq("id", rec_id).execute()
                        else:
                            # 3. 如果不存在，才插入新记录
                            supabase.table("user_answers").insert({
                                "user_id": user_id, 
                                "question_id": q['id'], 
                                "user_response": user_val, 
                                "is_correct": False
                            }).execute()
                    except Exception as e:
                        print(f"Save error: {e}")
            
            # --- 解析与 AI 举例 ---
            st.info(f"💡 **解析：** {q_exp}")
            
            # AI 举例交互区
            exp_chat_key = f"quiz_chat_{idx}"
            if exp_chat_key not in st.session_state: st.session_state[exp_chat_key] = []
            
            c_help, c_space = st.columns([1, 3])
            if c_help.button("🤔 不理解？举个生活例子"):
                with st.spinner("AI 正在思考..."):
                    p = f"用户对这个会计题不懂：'{q_text}'。答案是{q_ans}。原因：{q_exp}。请用买菜、做生意等通俗例子解释。"
                    res = call_ai_universal(p)
                    if res:
                        st.session_state[exp_chat_key].append({"role": "model", "content": res})
            
            # 显示对话
            for msg in st.session_state[exp_chat_key]:
                css = "chat-ai" if msg['role'] == "model" else "chat-user"
                st.markdown(f"<div class='{css}'>{msg['content']}</div>", unsafe_allow_html=True)
            
            # 追问框
            if st.session_state[exp_chat_key]:
                ask = st.text_input("继续追问...", key=f"ask_{idx}")
                if st.button("发送追问", key=f"btn_ask_{idx}") and ask:
                    st.session_state[exp_chat_key].append({"role": "user", "content": ask})
                    with st.spinner("回复中..."):
                        r = call_ai_universal(ask, history=st.session_state[exp_chat_key][:-1])
                        st.session_state[exp_chat_key].append({"role": "model", "content": r})
                        st.rerun()

            st.markdown("---")
            
            # 下一题按钮
            if st.button("➡️ 下一题", use_container_width=True):
                if idx < total-1:
                    st.session_state.q_idx += 1
                    st.rerun()
                else:
                    st.balloons()
                    st.success("本轮练习完成！")
                    if st.button("返回首页"):
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
                        <div style="
                            background-color: #F8F9FA; 
                            border: 1px solid #E9ECEF;
                            border-left: 4px solid #00C090; /* 呼应主色调 */
                            border-radius: 8px;
                            padding: 10px 15px;
                            margin-bottom: 8px;
                            font-size: 15px;
                            color: #495057;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                        ">
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



