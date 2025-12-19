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

@st.cache_data(ttl=3600)  # 缓存1小时，避免频繁请求卡顿
def fetch_available_models(provider, api_key, base_url):
    """
    动态获取 API 提供的模型列表
    """
    try:
        # 如果没有配置 Key，直接返回空，避免报错
        if not api_key: return []
        
        # 构造标准的 OpenAI 格式模型列表 URL
        # OpenRouter 和 DeepSeek 都遵循这个标准: GET /models
        url = f"{base_url.rstrip('/')}/models"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # OpenRouter 需要额外的 Referer 头，否则有时会拒收
        if "openrouter" in base_url:
            headers["HTTP-REFERER"] = "https://streamlit-app.com" 
            headers["X-TITLE"] = "My Study App"

        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            # OpenRouter 返回的数据在 'data' 字段里
            model_list = data.get('data', [])
            # 提取模型 ID 并排序
            ids = [m['id'] for m in model_list]
            return sorted(ids)
        else:
            return []
    except Exception:
        return []

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
    
    # --- 1. AI 大脑设置 (动态联网版) ---
    ai_provider = st.selectbox(
        "🧠 AI 大脑", 
        ["Gemini (官方直连)", "DeepSeek (官方直连)", "OpenRouter (聚合平台)"]
    )
    
    target_model_id = None # 初始化
    
    # === 分支 A: OpenRouter 动态列表 ===
    if "OpenRouter" in ai_provider:
        # 1. 尝试从 Secrets 获取配置
        or_key = st.secrets.get("openrouter", {}).get("api_key")
        or_url = st.secrets.get("openrouter", {}).get("base_url", "https://openrouter.ai/api/v1")
        
        # 2. 联网获取列表
        with st.spinner("正在同步 OpenRouter 模型库..."):
            dynamic_models = fetch_available_models("openrouter", or_key, or_url)
        
        # 3. 设定备选方案 (如果联网失败或Key没填，用这几个保底)
        backup_models = [
            "google/gemini-2.0-flash-exp:free",
            "deepseek/deepseek-r1",
            "meta-llama/llama-3.3-70b-instruct",
            "microsoft/phi-3-medium-128k-instruct:free"
        ]
        
        # 4. 决定显示哪些选项
        # 如果抓取到了，就把抓取到的放在前面；否则只显示备份的
        final_options = dynamic_models if dynamic_models else backup_models
        
        target_model_id = st.selectbox(
            "🔌 选择 OpenRouter 模型",
            final_options,
            index=0,
            help="列表实时从 OpenRouter 获取。如果没有显示完整列表，请检查 Secrets 配置。"
        )
        
        if not dynamic_models:
            st.caption("⚠️ 离线模式：未能连接 OpenRouter，仅显示推荐列表。")
        else:
            st.caption(f"✅ 已同步 {len(dynamic_models)} 个在线模型")

    # === 分支 B: DeepSeek 动态列表 ===
    elif "DeepSeek" in ai_provider:
        ds_key = st.secrets.get("deepseek", {}).get("api_key")
        ds_url = st.secrets.get("deepseek", {}).get("base_url", "https://api.deepseek.com")
        
        # DeepSeek 目前主要就是 deepseek-chat (V3) 和 deepseek-reasoner (R1)
        # 但我们也尝试动态获取，万一以后出了 V4 呢
        ds_models = fetch_available_models("deepseek", ds_key, ds_url)
        
        ds_backups = ["deepseek-chat", "deepseek-reasoner"]
        
        final_ds_opts = ds_models if ds_models else ds_backups
        
        target_model_id = st.selectbox("🔌 选择 DeepSeek 版本", final_ds_opts)

    # 存入全局状态
    st.session_state.selected_provider = ai_provider
    st.session_state.openrouter_model_id = target_model_id

    st.divider()

    # --- 2. 导航菜单 (保持不变) ---
    menu = st.radio(
        "导航", 
        ["🏠 仪表盘", "📚 资料库 (双轨录入)", "📝 章节特训 (刷题)", "⚔️ 全真模考", "📊 弱项分析", "❌ 错题本", "⚙️ 设置中心"], 
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # --- 3. 倒计时 (保持不变) ---
    if profile.get('exam_date'):
        try:
            days = (datetime.datetime.strptime(profile['exam_date'], '%Y-%m-%d').date() - datetime.date.today()).days
            if days <= 30:
                st.metric("⏳ 距离考试", f"{days} 天", delta="冲刺阶段", delta_color="inverse")
            else:
                st.metric("⏳ 距离考试", f"{days} 天")
        except: 
            pass

# === 🏠 仪表盘 ===
if menu == "🏠 仪表盘":
    days_left = 0
    if profile.get('exam_date'):
        days_left = (datetime.datetime.strptime(profile['exam_date'], '%Y-%m-%d').date() - datetime.date.today()).days
    
    st.markdown(f"### 🌞 距离上岸还有 <span style='color:#ff4b4b'>{days_left}</span> 天", unsafe_allow_html=True)
    msg = "别看手机了！看书！" if days_left < 30 else "乾坤未定，你我皆是黑马！"
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
    
    # 1. 计时器
    if 'q_timer' not in st.session_state: st.session_state.q_timer = time.time()
    if st.session_state.get('quiz_active'):
        el = int(time.time() - st.session_state.q_timer)
        st.markdown(f"<div class='timer-box'>⏱️ {el//60:02d}:{el%60:02d}</div>", unsafe_allow_html=True)

    # 2. 选择与启动
    if not st.session_state.get('quiz_active'):
        subjects = get_subjects()
        if subjects:
            s_name = st.selectbox("科目", [s['name'] for s in subjects])
            sid = next(s['id'] for s in subjects if s['name'] == s_name)
            chaps = get_chapters(sid, user_id)
            if chaps:
                c_title = st.selectbox("章节", [c['title'] for c in chaps])
                cid = next(c['id'] for c in chaps if c['title'] == c_title)
                
                st.markdown("---")
                
                # === 新增：进度统计 ===
                # 1. 总题数
                total_q = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", cid).execute().count
                # 2. 已做对过的题 (去重)
                # 注意：Supabase JS/Python client 在 filter 上稍有不同，这里用 Python 处理去重
                done_res = supabase.table("user_answers").select("question_id").eq("user_id", user_id).eq("is_correct", True).execute().data
                done_ids = list(set([d['question_id'] for d in done_res])) # 获取已掌握的 ID 列表
                done_count = len(done_ids)
                
                # 进度条
                progress = done_count / total_q if total_q > 0 else 0
                st.write(f"📊 **本章掌握进度**: {done_count} / {total_q}")
                st.progress(progress)
                
                # === 模式选择升级 ===
                mode = st.radio("练习策略", [
                    "🧹 消灭库存 (只做没掌握的题)", 
                    "🎲 随机巩固 (全库随机抽)", 
                    "🧠 AI 基于教材出新题"
                ])
                
                if st.button("🚀 开始"):
                    st.session_state.quiz_cid = cid
                    st.session_state.q_timer = time.time()
                    
                    # 策略 A: 消灭库存
                    if "消灭" in mode:
                        if total_q == 0:
                            st.error("题库为空，请先录题")
                        elif done_count == total_q:
                            st.balloons()
                            st.success("太棒了！本章题目已全部掌握！建议切换到随机模式复习。")
                        else:
                            # 核心逻辑：not_.in_ 排除已做对的 ID
                            qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).not_.in_("id", done_ids).limit(10).execute().data
                            if qs:
                                st.session_state.quiz_data = qs
                                st.session_state.q_idx = 0
                                st.session_state.quiz_active = True
                                st.rerun()
                            else:
                                st.info("剩余未掌握题目加载失败或已清空")

                    # 策略 B: 随机巩固
                    elif "随机" in mode:
                        # 简单随机：取20个再shuffle (生产环境可用 RPC random)
                        qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).limit(20).execute().data
                        if qs:
                            import random
                            random.shuffle(qs)
                            st.session_state.quiz_data = qs[:10]
                            st.session_state.q_idx = 0
                            st.session_state.quiz_active = True
                            st.rerun()
                    
                    # 策略 C: AI 出题 (保持原逻辑)
                    else:
                        # ... (原 AI 出题逻辑，只需把 call_gemini 换成 call_ai_universal) ...
                        pass

    # 3. 做题界面 (含追问功能)
    if st.session_state.get('quiz_active'):
        idx = st.session_state.q_idx
        q = st.session_state.quiz_data[idx]
        
        # 兼容两种数据格式 (DB读取 vs AI直接生成)
        q_text = q.get('content') or q.get('question')
        q_ans = q.get('correct_answer') or q.get('answer')
        
        st.progress((idx+1)/len(st.session_state.quiz_data))
        st.markdown(f"<div class='css-card'><h4>Q{idx+1}: {q_text}</h4></div>", unsafe_allow_html=True)
        
        sel = st.radio("选项", q['options'], key=f"q_{idx}")
        
        sub_key = f"sub_{idx}"
        if sub_key not in st.session_state: st.session_state[sub_key] = False
        
        if st.button("提交") and not st.session_state[sub_key]:
            st.session_state[sub_key] = True
            
        if st.session_state[sub_key]:
            if sel[0] == q_ans: st.success("✅ 正确")
            else: 
                st.error(f"❌ 错误。正确答案：{q_ans}")
                # 记录错题
                if q.get('id'):
                    supabase.table("user_answers").insert({"user_id": user_id, "question_id": q['id'], "user_response": sel[0], "is_correct": False}).execute()
            
            st.info(f"解析：{q['explanation']}")
            
            # --- 🔥 AI 举例与追问功能 (核心升级) ---
            st.markdown("---")
            exp_key = f"explain_chat_{idx}"
            if exp_key not in st.session_state: st.session_state[exp_key] = []
            
            c_exp1, c_exp2 = st.columns([1, 4])
            if c_exp1.button("🤔 举个生活例子"):
                with st.spinner("AI 思考中..."):
                    prompt = f"用户对这个会计题不懂：'{q_text}'。答案是{q_ans}。原因：{q['explanation']}。请用买菜、做生意等通俗例子解释。"
                    res = call_gemini(prompt)
                    if res:
                        ans = res['candidates'][0]['content']['parts'][0]['text']
                        st.session_state[exp_key].append({"role": "model", "content": ans})
            
            # 显示聊天记录
            for msg in st.session_state[exp_key]:
                css = "chat-ai" if msg['role'] == "model" else "chat-user"
                st.markdown(f"<div class='{css}'>{msg['content']}</div>", unsafe_allow_html=True)
            
            # 追问输入框
            if st.session_state[exp_key]:
                user_ask = st.text_input("还有疑问？继续追问 AI (回车发送)", key=f"ask_{idx}")
                if user_ask:
                    # 避免重复提交逻辑需配合 session state，这里简化处理
                    if st.button("发送追问"):
                        st.session_state[exp_key].append({"role": "user", "content": user_ask})
                        with st.spinner("AI 回复中..."):
                            # 带上下文调用
                            res = call_gemini(user_ask, history=st.session_state[exp_key][:-1])
                            if res:
                                ans = res['candidates'][0]['content']['parts'][0]['text']
                                st.session_state[exp_key].append({"role": "model", "content": ans})
                                st.rerun()

            st.markdown("---")
            if st.button("下一题"):
                if idx < len(st.session_state.quiz_data)-1:
                    st.session_state.q_idx += 1
                    st.rerun()
                else:
                    st.success("完成！")
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
    
    # 获取错题 (包含题目详情)
    # 注意：这里我们同时获取 question_bank 和 user_answers 里的 chat_history
    errs = supabase.table("user_answers").select("*, question_bank(*)").eq("user_id", user_id).eq("is_correct", False).order("created_at", desc=True).execute().data
    
    if not errs:
        st.markdown("""
        <div style="text-align:center; padding:40px; color:#888;">
            <h3>🎉 太棒了！目前没有错题</h3>
            <p>去刷几道新题挑战一下吧！</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info(f"当前共有 {len(errs)} 道错题待复习")
        
        for i, e in enumerate(errs):
            q = e['question_bank']
            if not q: continue
            
            # 获取数据库里已存的聊天记录 (如果没有则为 [])
            db_chat_history = e.get('ai_chat_history') or []
            
            # 卡片式展示
            with st.expander(f"🔴 {q['content'][:30]}... (点击展开)"):
                st.markdown(f"**题目：** {q['content']}")
                if q['options']:
                    st.markdown(f"**选项：** {q['options']}")
                
                c1, c2 = st.columns(2)
                c1.error(f"你的错选：{e['user_response']}")
                c2.success(f"正确答案：{q['correct_answer']}")
                
                st.info(f"💡 **标准解析：** {q['explanation']}")
                
                st.divider()
                
                # --- 🤖 AI 私教互动区 (带记忆功能) ---
                st.markdown("#### 🤖 AI 私教答疑")
                
                # 区域容器：用于显示历史记录
                chat_container = st.container()
                
                # 1. 渲染历史对话 (如果有)
                with chat_container:
                    if db_chat_history:
                        for msg in db_chat_history:
                            role_class = "chat-ai" if msg['role'] == "model" else "chat-user"
                            prefix = "🤖 AI：" if msg['role'] == "model" else "👤 你："
                            st.markdown(f"<div class='{role_class}'><b>{prefix}</b><br>{msg['content']}</div>", unsafe_allow_html=True)
                    else:
                        st.caption("暂无提问记录。点击下方按钮让 AI 举个栗子 👇")

                # 2. 交互按钮区
                col_ask, col_clear, col_del = st.columns([1, 1, 2])
                
                # 【按钮 A】: 第一次请求举例 (仅当没有历史记录时显示，或者用户想重新生成)
                if not db_chat_history:
                    if col_ask.button("🤔 我不理解，举个生活例子", key=f"init_ask_{e['id']}"):
                        prompt = f"用户做错了这道会计题：'{q['content']}'。答案是{q['correct_answer']}。解析是：{q['explanation']}。请用通俗的生活案例（如买菜、开店）来类比解释这个知识点。"
                        
                        with st.spinner("AI 正在头脑风暴..."):
                            res = call_ai_universal(prompt)
                            if res:
                                # 更新本地和数据库
                                new_history = [{"role": "model", "content": res}]
                                supabase.table("user_answers").update({"ai_chat_history": new_history}).eq("id", e['id']).execute()
                                st.rerun() # 刷新页面显示新内容

                # 【按钮 B】: 清空对话记录 (节省空间/重新提问)
                else:
                    if col_clear.button("🗑️ 清除对话记忆", key=f"clr_{e['id']}"):
                        supabase.table("user_answers").update({"ai_chat_history": []}).eq("id", e['id']).execute()
                        st.toast("记忆已清除")
                        st.rerun()

                # 【按钮 C】: 彻底移除错题 (已掌握)
                if col_del.button("✅ 我学会了，移出错题本", key=f"rm_{e['id']}"):
                    supabase.table("user_answers").update({"is_correct": True}).eq("id", e['id']).execute()
                    st.toast("恭喜！消灭一道错题！")
                    time.sleep(0.5)
                    st.rerun()

                # 3. 追问输入框 (仅当有历史记录或已开始对话时显示)
                if db_chat_history:
                    with st.form(key=f"chat_form_{e['id']}"):
                        user_input = st.text_input("继续追问 (例如：那如果是卖方呢？)", placeholder="在此输入你的疑问...")
                        submit_chat = st.form_submit_button("发送追问 ⬆️")
                        
                        if submit_chat and user_input:
                            # 1. 把用户问题加入历史
                            temp_history = db_chat_history + [{"role": "user", "content": user_input}]
                            
                            with st.spinner("AI 正在思考..."):
                                # 2. 调用 AI (带上下文)
                                ai_reply = call_ai_universal(user_input, history=db_chat_history)
                                
                                if ai_reply:
                                    # 3. 把 AI 回复也加入历史
                                    final_history = temp_history + [{"role": "model", "content": ai_reply}]
                                    
                                    # 4. 存入数据库
                                    supabase.table("user_answers").update({"ai_chat_history": final_history}).eq("id", e['id']).execute()
                                    st.rerun()

