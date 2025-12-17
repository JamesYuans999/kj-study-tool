import streamlit as st
import requests
import json
import datetime
import pandas as pd
import pdfplumber
from supabase import create_client
import time

# --- 1. 配置与风格 (保留之前的奶油绿风格) ---
st.set_page_config(page_title="中级会计冲刺班", page_icon="🥝", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F9F9F0; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #EEEEEE; }
    .css-card {
        background-color: #FFFFFF; border-radius: 15px; padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 20px; border: 1px solid #F0F0F0;
    }
    .big-number { font-size: 32px; font-weight: 800; color: #2C3E50; }
    .stButton>button {
        background-color: #00C090; color: white; border-radius: 10px; border: none;
        height: 45px; font-weight: bold; box-shadow: 0 4px 0 #009670; transition: all 0.2s;
    }
    .stButton>button:hover {
        background-color: #00A87E; box-shadow: 0 2px 0 #009670; transform: translateY(2px); color: white;
    }
    /* 成功提示框 */
    .success-box {
        padding: 15px; background-color: #E8F5E9; border-left: 5px solid #00C090; color: #1B5E20; border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. 数据库连接 ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
except:
    st.error("🔒 请配置 Secrets")
    st.stop()

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# --- 3. 核心功能函数 ---

def call_gemini(prompt):
    """调用 Gemini Robotics 模型"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-robotics-er-1.5-preview:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

def extract_text_from_pdf(file):
    """使用 pdfplumber 读取 PDF (增强版)"""
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            # 限制读取前 50 页，防止 Tokens 爆炸
            for page in pdf.pages[:50]: 
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"PDF 解析失败: {e}")
        return ""

# --- 数据库操作 Helper ---

def get_subjects():
    """获取所有科目"""
    res = supabase.table("subjects").select("*").execute()
    return res.data

def get_chapters(subject_id, user_id):
    """获取某科目下的章节"""
    res = supabase.table("chapters").select("*").eq("subject_id", subject_id).eq("user_id", user_id).execute()
    return res.data

def create_chapter(subject_id, title, user_id):
    """创建新章节"""
    supabase.table("chapters").insert({"subject_id": subject_id, "title": title, "user_id": user_id}).execute()

def save_material_track_a(chapter_id, content, title, user_id):
    """轨道A：保存教材文本"""
    data = {
        "chapter_id": chapter_id,
        "content": content,
        "source_type": "textbook",
        "title": title,
        "user_id": user_id
    }
    supabase.table("materials").insert(data).execute()

def save_questions_batch(questions_list, chapter_id, user_id):
    """轨道B：批量保存真题"""
    data_to_insert = []
    for q in questions_list:
        data_to_insert.append({
            "chapter_id": chapter_id,
            "user_id": user_id,
            "type": "single", # 暂时默认为单选，后续可让AI判断
            "content": q['question'],
            "options": q['options'],
            "correct_answer": q['answer'],
            "explanation": q.get('explanation', '暂无解析'),
            "origin": "extraction",
            "is_verified": True
        })
    supabase.table("question_bank").insert(data_to_insert).execute()

# --- 4. 主界面逻辑 ---

if 'user_id' not in st.session_state:
    st.session_state.user_id = "test_user_001" 

user_id = st.session_state.user_id

with st.sidebar:
    st.title("🥝 备考中心")
    menu = st.radio("导航", ["🏠 仪表盘", "📚 资料库 (双轨录入)", "📝 章节特训 (刷题)"], label_visibility="collapsed")

# === 页面：仪表盘 ===
if menu == "🏠 仪表盘":
    st.markdown("### 🌞 欢迎回到学习中心")
    # (此处省略仪表盘代码，保持你之前的代码即可，为了节省篇幅)
    st.info("请点击左侧 **📚 资料库** 开始上传你的第一份资料！")

# === 页面：资料库 (核心更新) ===
elif menu == "📚 资料库 (双轨录入)":
    st.title("📂 资料上传中心")
    
    # 1. 基础信息选择 (层级结构)
    st.markdown("##### 第一步：选择归属")
    col_s1, col_s2, col_s3 = st.columns([1, 1, 1])
    
    with col_s1:
        subjects = get_subjects()
        subject_names = [s['name'] for s in subjects]
        selected_sub_name = st.selectbox("选择科目", subject_names)
        # 获取 ID
        selected_sub_id = next(s['id'] for s in subjects if s['name'] == selected_sub_name)
    
    with col_s2:
        chapters = get_chapters(selected_sub_id, user_id)
        chapter_titles = [c['title'] for c in chapters]
        selected_chap_title = st.selectbox("选择章节", ["➕ 新建章节..."] + chapter_titles)
    
    with col_s3:
        if selected_chap_title == "➕ 新建章节...":
            new_chap_name = st.text_input("输入新章节名称", placeholder="例如：长期股权投资")
            if st.button("创建章节"):
                if new_chap_name:
                    create_chapter(selected_sub_id, new_chap_name, user_id)
                    st.toast("章节创建成功！", icon="✅")
                    time.sleep(1)
                    st.rerun()
    
    # 确定章节ID
    current_chap_id = None
    if selected_chap_title != "➕ 新建章节..." and chapters:
        current_chap_id = next(c['id'] for c in chapters if c['title'] == selected_chap_title)

    st.divider()

    # 2. 双轨上传区
    if current_chap_id:
        st.markdown(f"当前操作：**{selected_sub_name}** > **{selected_chap_title}**")
        
        type_tab1, type_tab2 = st.tabs(["📖 轨道A：教材/讲义 (AI生成)", "📑 轨道B：真题/练习卷 (AI提取)"])
        
        # --- 轨道 A ---
        with type_tab1:
            st.info("💡 适合：电子书、笔记。AI 将阅读内容，并在练习时为你生成新题目。")
            uploaded_a = st.file_uploader("上传教材 PDF", type="pdf", key="pdf_a")
            
            if st.button("📥 保存教材资料"):
                if uploaded_a:
                    with st.spinner("正在OCR识别文字..."):
                        text = extract_text_from_pdf(uploaded_a)
                        if len(text) > 50:
                            save_material_track_a(current_chap_id, text, uploaded_a.name, user_id)
                            st.markdown(f"<div class='success-box'>✅ 资料已入库！共 {len(text)} 字。请去‘章节特训’开始出题。</div>", unsafe_allow_html=True)
                        else:
                            st.error("文字太少或无法识别，请检查PDF。")

        # --- 轨道 B (AI 提取器) ---
        with type_tab2:
            st.warning("⚡ 适合：已有题目和答案的文档。AI 将提取题目并存入题库。")
            
            c1, c2 = st.columns(2)
            with c1:
                ans_pos = st.selectbox("答案位置", ["答案紧跟题目", "答案在文档末尾", "无答案(仅录入题目)"])
            with c2:
                custom_hint = st.text_input("给 AI 的特别叮嘱", placeholder="例如：忽略页眉水印...")
            
            uploaded_b = st.file_uploader("上传真题 PDF", type="pdf", key="pdf_b")
            
            # Session State 用于暂存提取结果以供预览
            if 'extracted_data' not in st.session_state:
                st.session_state.extracted_data = None

            if st.button("🔍 开始 AI 提取"):
                if uploaded_b:
                    with st.spinner("第一步：读取 PDF..."):
                        raw_text = extract_text_from_pdf(uploaded_b)
                    
                    with st.spinner("第二步：AI 正在结构化提取 (这可能需要 30 秒)..."):
                        prompt = f"""
                        你是一个数据录入员。请处理以下文本，提取其中的单项选择题。
                        文本内容：{raw_text[:8000]} ... (截取)
                        
                        用户提示：答案位置在【{ans_pos}】。额外注意：{custom_hint}。
                        
                        请严格返回纯 JSON 列表，不要 Markdown。格式：
                        [
                            {{
                                "question": "题目内容...",
                                "options": ["A.选项1", "B.选项2", "C.选项3", "D.选项4"],
                                "answer": "A", 
                                "explanation": "解析内容(如果有)"
                            }}
                        ]
                        如果找不到答案，answer字段填"无"。
                        """
                        res = call_gemini(prompt)
                        if res and 'candidates' in res:
                            try:
                                json_str = res['candidates'][0]['content']['parts'][0]['text']
                                clean_json = json_str.replace("```json", "").replace("```", "").strip()
                                st.session_state.extracted_data = json.loads(clean_json)
                            except Exception as e:
                                st.error(f"AI 返回格式有误: {e}")
                                st.write(res) # 调试用

            # 预览与确认保存
            if st.session_state.extracted_data:
                st.divider()
                st.subheader("🧐 提取结果预览 (人机协作校对)")
                st.caption("请检查提取是否正确，特别是答案。确认无误后点击下方保存。")
                
                # 用 DataFrame 展示更直观
                df = pd.DataFrame(st.session_state.extracted_data)
                st.dataframe(df, use_container_width=True)
                
                if st.button("💾 确认无误，批量存入题库"):
                    save_questions_batch(st.session_state.extracted_data, current_chap_id, user_id)
                    st.balloons()
                    st.success(f"成功导入 {len(st.session_state.extracted_data)} 道真题！")
                    # 清空暂存
                    st.session_state.extracted_data = None
                    
    else:
        st.info("👆 请先在上方选择或新建一个章节")

# === 页面：章节特训 (验证数据是否打通) ===
elif menu == "📝 章节特训 (刷题)":
    st.title("📝 章节突破")
    
    # 1. 选章节
    subjects = get_subjects()
    sub_names = [s['name'] for s in subjects]
    sel_sub = st.selectbox("科目", sub_names)
    sel_sub_id = next(s['id'] for s in subjects if s['name'] == sel_sub)
    
    chapters = get_chapters(sel_sub_id, user_id)
    if not chapters:
        st.warning("该科目下还没有章节，请去资料库创建。")
    else:
        sel_chap = st.selectbox("选择章节", [c['title'] for c in chapters])
        sel_chap_id = next(c['id'] for c in chapters if c['title'] == sel_chap)
        
        # 2. 统计数据
        # 查询该章节下有多少题 (真题) 和 多少资料 (教材)
        q_count = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", sel_chap_id).execute().count
        m_count = supabase.table("materials").select("id", count="exact").eq("chapter_id", sel_chap_id).execute().count
        
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.markdown(f"<div class='css-card'>📚 <b>教材资料</b><br>{m_count} 份<br><span style='color:#888;font-size:12px'>可用于AI出题</span></div>", unsafe_allow_html=True)
        with col_info2:
            st.markdown(f"<div class='css-card'>📑 <b>真题库存</b><br>{q_count} 道<br><span style='color:#888;font-size:12px'>直接抽取练习</span></div>", unsafe_allow_html=True)
            
        st.divider()
        
        # 3. 开始做题模式选择
        mode = st.radio("选择模式", ["🧠 AI基于教材出新题", "🎲 抽取已录入真题"])
        
        if st.button("开始练习"):
            if mode == "🎲 抽取已录入真题":
                if q_count == 0:
                    st.error("题库空空如也！请先去‘资料库 > 轨道B’上传真题。")
                else:
                    # 从数据库拉取题目的逻辑
                    res = supabase.table("question_bank").select("*").eq("chapter_id", sel_chap_id).limit(5).execute()
                    st.session_state.quiz_questions = res.data
                    st.success(f"抽取了 {len(res.data)} 道真题！(此处应跳转做题界面)")
                    # 实际做题界面将在下一次更新完善
                    st.json(res.data) # 暂时打印出来证明获取成功

            elif mode == "🧠 AI基于教材出新题":
                if m_count == 0:
                    st.error("没有教材资料！请先去‘资料库 > 轨道A’上传。")
                else:
                    st.info("正在调用 AI 读取教材并出题... (逻辑同之前，待集成)")
