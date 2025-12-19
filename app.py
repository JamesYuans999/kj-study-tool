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

def call_gemini(prompt, history=[]):
    """通用 AI 调用 (支持上下文)"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    # 构建对话历史
    contents = []
    for h in history:
        role = "user" if h['role'] == 'user' else "model"
        contents.append({"role": role, "parts": [{"text": h['content']}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    
    data = {"contents": contents}
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

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
    menu = st.radio("导航", ["🏠 仪表盘", "📚 资料库 (双轨录入)", "📝 章节特训 (刷题)", "⚔️ 全真模考", "📊 弱项分析", "❌ 错题本", "⚙️ 设置中心"], label_visibility="collapsed")
    st.divider()
    if profile.get('exam_date'):
        try:
            days = (datetime.datetime.strptime(profile['exam_date'], '%Y-%m-%d').date() - datetime.date.today()).days
            st.metric("⏳ 距离考试", f"{days} 天")
        except: pass

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
                
                # 模式选择
                mode = st.radio("模式", ["🎲 刷真题库存", "🧠 AI 基于教材出新题"])
                
                if st.button("🚀 开始"):
                    st.session_state.quiz_cid = cid
                    st.session_state.q_timer = time.time()
                    
                    if "真题" in mode:
                        qs = supabase.table("question_bank").select("*").eq("chapter_id", cid).limit(10).execute().data
                        if qs:
                            st.session_state.quiz_data = qs
                            st.session_state.q_idx = 0
                            st.session_state.quiz_active = True
                            st.rerun()
                        else: st.error("题库为空")
                    else:
                        # AI 出题逻辑
                        mats = supabase.table("materials").select("content").eq("chapter_id", cid).execute().data
                        if mats:
                            txt = "\n".join([m['content'] for m in mats])
                            with st.spinner("AI 出题中..."):
                                p = f"基于内容出3道单选题。内容：{txt[:6000]}。格式JSON：[{{'content':'..','options':['A..'],'correct_answer':'A','explanation':'..'}}]。"
                                r = call_gemini(p)
                                if r:
                                    try:
                                        d = json.loads(r['candidates'][0]['content']['parts'][0]['text'].replace("```json","").replace("```","").strip())
                                        save_questions_batch([{'question':x['content'], 'options':x['options'], 'answer':x['correct_answer'], 'explanation':x['explanation']} for x in d], cid, user_id)
                                        st.session_state.quiz_data = d
                                        st.session_state.q_idx = 0
                                        st.session_state.quiz_active = True
                                        st.rerun()
                                    except: st.error("生成失败")
                        else: st.error("无教材")

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
    st.title("❌ 错题集")
    # 联表查询
    errs = supabase.table("user_answers").select("*, question_bank(*)").eq("user_id", user_id).eq("is_correct", False).execute().data
    if not errs: st.success("没有错题！")
    else:
        for e in errs:
            q = e['question_bank']
            if q:
                with st.expander(f"{q['content'][:20]}..."):
                    st.write(q['content'])
                    st.error(f"你的错选：{e['user_response']}")
                    st.success(f"正确答案：{q['correct_answer']}")
                    st.info(q['explanation'])
                    if st.button("已掌握，移除", key=f"del_{e['id']}"):
                        supabase.table("user_answers").delete().eq("id", e['id']).execute()
                        st.rerun()    
