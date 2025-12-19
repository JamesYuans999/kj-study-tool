import streamlit as st
import requests
import json
import datetime
import pandas as pd
import pdfplumber
from supabase import create_client
import time
import docx

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

def extract_text_from_pdf(file, start_page=1, end_page=None):
    """【升级版】支持指定页码读取 PDF"""
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            total_pages = len(pdf.pages)
            # 处理页码越界
            if start_page < 1: start_page = 1
            if end_page is None or end_page > total_pages: end_page = total_pages
            
            # pdfplumber 索引从 0 开始，所以要 -1
            for i in range(start_page - 1, end_page):
                page = pdf.pages[i]
                text += page.extract_text() + "\n"
                
        return text
    except Exception as e:
        st.error(f"PDF 解析失败: {e}")
        return ""

def extract_text_from_docx(file):
    """读取 Word 文档全文"""
    try:
        doc = docx.Document(file)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return "\n".join(full_text)
    except Exception as e:
        st.error(f"Word 解析失败: {e}")
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

def rename_chapter(chap_id, new_name):
    """重命名章节"""
    try:
        supabase.table("chapters").update({"title": new_name}).eq("id", chap_id).execute()
        st.toast("✅ 更名成功！", icon="✨")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"更名失败: {e}")

def delete_chapter_cascade(chap_id):
    """删除章节 (触发级联删除)"""
    try:
        # 因为数据库设置了 on delete cascade，删了章节，下面的资料和题目会自动删除
        supabase.table("chapters").delete().eq("id", chap_id).execute()
        st.toast("🗑️ 章节及其数据已删除", icon="👋")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"删除失败: {e}")

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
    
    # 获取科目
    subjects = get_subjects()
    if not subjects:
        st.error("请先初始化数据库（执行SQL）以获取科目。")
        st.stop()
        
    col_s1, col_s2, col_s3 = st.columns([1, 1, 1])
    
    with col_s1:
        subject_names = [s['name'] for s in subjects]
        selected_sub_name = st.selectbox("选择科目", subject_names)
        selected_sub_id = next(s['id'] for s in subjects if s['name'] == selected_sub_name)
    
    with col_s2:
        # 获取该科目下的章节
        chapters = get_chapters(selected_sub_id, user_id)
        chapter_titles = [c['title'] for c in chapters]
        # 下拉菜单增加新建选项
        selected_chap_title = st.selectbox("选择章节", ["➕ 新建章节..."] + chapter_titles)
    
    # 获取当前选中的章节ID (如果有)
    current_chap_id = None
    if selected_chap_title != "➕ 新建章节..." and chapters:
        current_chap_id = next(c['id'] for c in chapters if c['title'] == selected_chap_title)

    with col_s3:
        #如果是新建模式
        if selected_chap_title == "➕ 新建章节...":
            new_chap_name = st.text_input("输入新章节名称", placeholder="例如：长期股权投资")
            if st.button("创建章节"):
                if new_chap_name:
                    create_chapter(selected_sub_id, new_chap_name, user_id)
                    st.toast("章节创建成功！", icon="✅")
                    time.sleep(1)
                    st.rerun()
    
    # --- 新增功能：章节管理区 (仅在选中已存在章节时显示) ---
    if current_chap_id:
        with st.expander(f"⚙️ 管理当前章节：{selected_chap_title}"):
            col_m1, col_m2 = st.columns(2)
            
            # 功能 A: 重命名
            with col_m1:
                st.write("**✏️ 重命名**")
                rename_text = st.text_input("修改名称为", value=selected_chap_title, key="rename_input")
                if st.button("确认修改"):
                    if rename_text and rename_text != selected_chap_title:
                        rename_chapter(current_chap_id, rename_text)
            
            # 功能 B: 删除
            with col_m2:
                st.write("**🗑️ 删除章节**")
                st.caption("⚠️ 警告：删除章节将同步删除该章节下所有的 资料 和 题库数据，且无法恢复！")
                if st.button("确认删除此章节", type="primary"):
                    delete_chapter_cascade(current_chap_id)

    st.divider()

    # 2. 双轨上传区 (只有选中了有效章节才显示)
    if current_chap_id:
        st.markdown(f"当前操作：**{selected_sub_name}** > **{selected_chap_title}**")
        
        type_tab1, type_tab2 = st.tabs(["📖 轨道A：教材/讲义 (AI生成)", "📑 轨道B：真题/练习卷 (AI提取)"])
        
        # --- 轨道 A ---
        with type_tab1:
            st.info("💡 适合：电子书、笔记。AI 将阅读内容，并在练习时为你生成新题目。")
            # 修改点：type 增加了 "docx"
            uploaded_a = st.file_uploader("上传教材 (PDF/Word)", type=["pdf", "docx"], key="file_a")
            
            if st.button("📥 保存教材资料"):
                if uploaded_a:
                    text = ""
                    with st.spinner("正在识别文字..."):
                        # 修改点：判断文件后缀
                        if uploaded_a.name.endswith(".pdf"):
                            text = extract_text_from_pdf(uploaded_a)
                        elif uploaded_a.name.endswith(".docx"):
                            text = extract_text_from_docx(uploaded_a)
                            
                        if len(text) > 50:
                            save_material_track_a(current_chap_id, text, uploaded_a.name, user_id)
                            st.markdown(f"<div class='success-box'>✅ 资料已入库！共 {len(text)} 字。</div>", unsafe_allow_html=True)
                        else:
                            st.error("文字太少或无法识别。")

        # --- 轨道 B (保持你之前要求的跨页码提取功能) ---
        with type_tab2:
            st.warning("⚡ 适合：已有题目和答案的文档。AI 将提取题目并存入题库。")
            
            uploaded_b = st.file_uploader("上传真题/母题 (PDF/Word)", type=["pdf", "docx"], key="file_b")
            
            # 只有 PDF 才能显示页码控制器，Word 显示全文提示
            is_pdf = uploaded_b is not None and uploaded_b.name.endswith(".pdf")
            is_word = uploaded_b is not None and uploaded_b.name.endswith(".docx")
            
            total_pages = 0
            if is_pdf:
                try:
                    with pdfplumber.open(uploaded_b) as pdf: total_pages = len(pdf.pages)
                    st.success(f"📄 PDF 检测到 {total_pages} 页")
                except: pass
            elif is_word:
                st.info("📄 Word 文档已就绪 (Word 模式下将读取全文)")

            # 控制器逻辑
            if is_pdf:
                # ... (保留你之前的 PDF 双区间选择器代码) ...
                # 这里为了节省篇幅，复用你上一次生成的“双区间读取”UI代码
                st.markdown("#### 1. 设定题目位置")
                c1, c2 = st.columns(2)
                with c1: q_start = st.number_input("题目开始页", 1, value=1)
                with c2: q_end = st.number_input("题目结束页", 1, value=min(10, total_pages) if total_pages else 10)
                
                separate_answer = st.checkbox("答案在文件后半部分", value=False)
                if separate_answer:
                    c3, c4 = st.columns(2)
                    with c3: a_start = st.number_input("答案开始页", 1, value=total_pages)
                    with c4: a_end = st.number_input("答案结束页", 1, value=total_pages)
            
            # 通用提示框
            c_hint, c_ans_pos = st.columns([2, 1])
            with c_hint: custom_hint = st.text_input("给 AI 的特别叮嘱", placeholder="例如：忽略水印...")
            with c_ans_pos: ans_pos = st.selectbox("答案位置描述", ["答案紧跟题目", "答案在文档末尾"])

            if st.button("🔍 开始提取"):
                if uploaded_b:
                    raw_text = ""
                    # 分流处理
                    if is_pdf:
                        with st.spinner("正在读取 PDF 指定范围..."):
                            uploaded_b.seek(0)
                            # 题目部分
                            raw_text = extract_text_from_pdf(uploaded_b, q_start, q_end)
                            # 答案部分 (如果有)
                            if separate_answer:
                                uploaded_b.seek(0) # 指针归位
                                a_text = extract_text_from_pdf(uploaded_b, a_start, a_end)
                                raw_text += "\n\n【答案区域】\n" + a_text
                    
                    elif is_word:
                        with st.spinner("正在读取 Word 全文..."):
                            raw_text = extract_text_from_docx(uploaded_b)

                    # 发送给 AI (通用逻辑)
                    if len(raw_text) < 10:
                        st.warning("提取内容过少")
                    else:
                        with st.spinner("AI 正在结构化提取..."):
                            prompt = f"""
                            你是一个数据录入员。请提取以下文本中的会计题目。
                            
                            答案位置提示：{ans_pos}。
                            额外要求：{custom_hint}。
                            
                            请严格返回纯 JSON 列表，不要 Markdown。格式：
                            [
                                {{
                                    "question": "题目...",
                                    "options": ["A.","B."],
                                    "answer": "A", 
                                    "explanation": "解析..."
                                }}
                            ]
                            
                            文本内容：
                            {raw_text[:15000]} 
                            """
                            # ... (后续 AI 调用和 session_state 存储代码保持不变) ...
                            # 复制之前的 res = call_gemini(prompt) ... 那部分代码即可
                            res = call_gemini(prompt)
                            if res and 'candidates' in res:
                                try:
                                    json_str = res['candidates'][0]['content']['parts'][0]['text']
                                    clean_json = json_str.replace("```json", "").replace("```", "").strip()
                                    st.session_state.extracted_data = json.loads(clean_json)
                                except Exception as e:
                                    st.error(f"AI 解析错误: {e}")

# === 页面：章节特训 (验证数据是否打通) ===
# ... (前面的代码保持不变) ...

# === 页面：章节特训 (刷题) - 完整交互版 ===
elif menu == "📝 章节特训 (刷题)":
    st.title("📝 章节突破")
    
    # 1. 章节选择器
    subjects = get_subjects()
    if not subjects:
        st.info("数据库还没有科目数据，请先去资料库初始化。")
        st.stop()
        
    c1, c2 = st.columns(2)
    with c1:
        sub_names = [s['name'] for s in subjects]
        sel_sub = st.selectbox("选择科目", sub_names)
        sel_sub_id = next(s['id'] for s in subjects if s['name'] == sel_sub)
    
    with c2:
        chapters = get_chapters(sel_sub_id, user_id)
        if not chapters:
            st.warning("该科目下无章节")
            st.stop()
        sel_chap = st.selectbox("选择章节", [c['title'] for c in chapters])
        sel_chap_id = next(c['id'] for c in chapters if c['title'] == sel_chap)

    # 2. 模式选择与数据概览
    st.markdown("---")
    # 统计库存
    q_bank_count = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", sel_chap_id).execute().count
    mat_count = supabase.table("materials").select("id", count="exact").eq("chapter_id", sel_chap_id).execute().count
    
    col_stat1, col_stat2, col_stat3 = st.columns(3)
    with col_stat1:
        st.metric("📚 教材资料", f"{mat_count} 份")
    with col_stat2:
        st.metric("💾 真题库存", f"{q_bank_count} 题")
    
    mode = st.radio("练习模式", ["🎲 刷真题 (从库存抽取)", "🧠 AI出新题 (基于教材生成)"], horizontal=True)

    # 初始化 Session State
    if 'quiz_data' not in st.session_state: st.session_state.quiz_data = []
    if 'current_idx' not in st.session_state: st.session_state.current_idx = 0
    if 'quiz_active' not in st.session_state: st.session_state.quiz_active = False

    # 3. 获取题目逻辑
    if not st.session_state.quiz_active:
        start_btn = st.button("🚀 开始练习", use_container_width=True)
        
        if start_btn:
            # --- 逻辑分支 A：刷真题 ---
            if "刷真题" in mode:
                if q_bank_count == 0:
                    st.error("库存没题！请先去‘资料库’录入真题。")
                else:
                    # 随机抽取 5 道
                    # 注意：Supabase 随机抽取需要 RPC 或客户端随机，这里用简单的 Limit 模拟
                    res = supabase.table("question_bank").select("*").eq("chapter_id", sel_chap_id).limit(10).execute()
                    # 简单洗牌
                    import random
                    final_qs = res.data
                    random.shuffle(final_qs)
                    st.session_state.quiz_data = final_qs[:5] # 取前5题
                    st.session_state.current_idx = 0
                    st.session_state.quiz_active = True
                    st.rerun()

            # --- 逻辑分支 B：AI 基于教材出题 ---
            elif "AI" in mode:
                if mat_count == 0:
                    st.error("没教材！请先去‘资料库’上传PDF或文本。")
                else:
                    # 获取该章节所有资料文本
                    mats = supabase.table("materials").select("content").eq("chapter_id", sel_chap_id).execute()
                    full_text = "\n".join([m['content'] for m in mats.data])
                    
                    with st.spinner("🤖 AI 正在阅读教材并出题 (约15秒)..."):
                        prompt = f"""
                        你是一位资深会计讲师。请根据以下教材内容，编制 3 道单项选择题。
                        教材内容：{full_text[:5000]}
                        
                        要求：
                        1. 难度中等偏上，考察细节。
                        2. 必须返回纯 JSON 列表：
                        [
                            {{
                                "content": "题目描述...",
                                "options": ["A.选项1", "B.选项2", "C.选项3", "D.选项4"],
                                "correct_answer": "A",
                                "explanation": "解析..."
                            }}
                        ]
                        """
                        res = call_gemini(prompt)
                        if res and 'candidates' in res:
                            try:
                                json_str = res['candidates'][0]['content']['parts'][0]['text']
                                clean = json_str.replace("```json", "").replace("```", "").strip()
                                new_qs = json.loads(clean)
                                # 存入数据库以便复用
                                save_questions_batch(new_qs, sel_chap_id, user_id) # 复用之前的存储函数
                                st.session_state.quiz_data = new_qs
                                st.session_state.current_idx = 0
                                st.session_state.quiz_active = True
                                st.rerun()
                            except:
                                st.error("AI 生成格式错误，请重试")

    # 4. 做题交互界面 (Quiz Engine)
    if st.session_state.quiz_active and st.session_state.quiz_data:
        idx = st.session_state.current_idx
        total = len(st.session_state.quiz_data)
        
        # 进度条
        st.progress((idx + 1) / total)
        st.caption(f"进度：{idx + 1} / {total}")
        
        q = st.session_state.quiz_data[idx]
        
        # --- 题目卡片 ---
        with st.container():
            st.markdown(f"""
            <div class="css-card">
                <h4 style="color:#2C3E50">Q{idx+1}: {q['content']}</h4>
            </div>
            """, unsafe_allow_html=True)
            
            # 选项展示
            user_choice = st.radio("请选择答案：", q['options'], key=f"q_radio_{idx}")
            
            # 提交区
            c_sub1, c_sub2 = st.columns([1, 1])
            
            # 状态标记：是否已提交当前题
            submit_key = f"submitted_{idx}"
            if submit_key not in st.session_state: st.session_state[submit_key] = False
            
            if c_sub1.button("✅ 提交答案", disabled=st.session_state[submit_key]):
                st.session_state[submit_key] = True
                
            # 判分逻辑
            if st.session_state[submit_key]:
                user_letter = user_choice[0] # 取 "A"
                correct_letter = q['correct_answer']
                
                is_correct = (user_letter == correct_letter)
                
                if is_correct:
                    st.markdown(f"<div class='success-box'>🎉 回答正确！</div>", unsafe_allow_html=True)
                else:
                    st.error(f"❌ 遗憾答错。正确答案是：{correct_letter}")
                    # 存入错题表 (Logic: User_Answers table)
                    try:
                        # 检查题目是否已有ID (AI新生成的可能还没ID，如果是从DB取的就有)
                        q_id = q.get('id') 
                        if not q_id: # 如果是AI刚生成的，需要查询刚插入的ID，或者简化处理暂存
                            pass # 这里为了简化代码，暂时略过无ID情况的记录，生产环境需要处理
                        else:
                            supabase.table("user_answers").insert({
                                "user_id": user_id,
                                "question_id": q_id,
                                "user_response": user_letter,
                                "is_correct": False,
                                "is_mastered": False
                            }).execute()
                    except:
                        pass # 忽略重复键错误

                # --- 核心：解析与举例 (PathA/B 通用) ---
                st.markdown("---")
                st.markdown("#### 💡 深度解析")
                st.info(q['explanation'])
                
                # ✨ 生活化举例按钮 (Contextual AI)
                if st.button("🤔 我不理解，给我举个生活中的例子"):
                    with st.spinner("AI 正在头脑风暴生活案例..."):
                        ex_prompt = f"""
                        用户没听懂这个会计知识点："{q['content']}"。
                        正确答案是 {q['correct_answer']}，原因是：{q['explanation']}。
                        请用通俗易懂的“生活案例”（比如买菜、通过借钱、做生意）来类比解释这个概念。
                        """
                        ex_res = call_gemini(ex_prompt)
                        if ex_res:
                            ex_text = ex_res['candidates'][0]['content']['parts'][0]['text']
                            st.markdown(f"""
                            <div class="css-card" style="background-color:#FFF3E0; border-color:#FFB74D">
                                <b>🍎 生活化类比：</b><br>
                                {ex_text}
                            </div>
                            """, unsafe_allow_html=True)

                # 🛠️ 题目纠错 (Human Loop)
                with st.expander("🛠️ 题目有问题？点此修改"):
                    new_q_text = st.text_input("修正题目", value=q['content'])
                    new_ans = st.text_input("修正答案", value=q['correct_answer'])
                    if st.button("更新题库"):
                        if q.get('id'):
                            supabase.table("question_bank").update({
                                "content": new_q_text, 
                                "correct_answer": new_ans
                            }).eq("id", q['id']).execute()
                            st.toast("已修正！感谢你的贡献。")

            # 下一题
            if st.session_state[submit_key]:
                if c_sub2.button("➡️ 下一题"):
                    if idx < total - 1:
                        st.session_state.current_idx += 1
                        st.rerun()
                    else:
                        st.balloons()
                        st.success("本章练习完成！")
                        if st.button("返回菜单"):
                            st.session_state.quiz_active = False
                            st.session_state.quiz_data = []
                            st.rerun()

# === 页面：全真模考 (核心引擎) ===
elif menu == "⚔️ 全真模考":
    # 状态管理：是否正在考试
    if 'exam_session' not in st.session_state:
        st.session_state.exam_session = None # 存试卷数据
    if 'exam_start_time' not in st.session_state:
        st.session_state.exam_start_time = None

    # --- 场景 A: 考试未开始 (配置台) ---
    if not st.session_state.exam_session:
        st.title("⚔️ 全真模拟考试")
        st.caption("系统将从题库中随机抽取题目，组成一套符合中级会计标准的试卷。")
        
        subjects = get_subjects()
        if not subjects: st.stop()
        
        col_set1, col_set2 = st.columns([2, 1])
        with col_set1:
            # 1. 考试配置
            sub_names = [s['name'] for s in subjects]
            sel_sub = st.selectbox("选择科目", sub_names)
            sel_sub_id = next(s['id'] for s in subjects if s['name'] == sel_sub)
            
            mode = st.radio("试卷类型", ["🐇 精简版 (5题/快速自测)", "🐢 完整版 (20题/压力测试)"], horizontal=True)
            
            # 检查库存
            total_q = supabase.table("question_bank").select("id", count="exact").eq("chapter_id", sel_sub_id).execute().count
            # 注意：这里简化逻辑，直接查该科目下所有章节的题。实际应先查chapter再查题，或修改DB结构让题库直接关联subject。
            # 为简化，假设你已录入足够的题。
            
            if st.button("🚀 生成试卷并开始", type="primary"):
                # 组卷逻辑
                limit = 5 if "精简" in mode else 20
                
                # 1. 获取该科目下所有章节ID
                chaps = get_chapters(sel_sub_id, user_id)
                chap_ids = [c['id'] for c in chaps]
                
                if not chap_ids:
                    st.error("该科目下没有章节数据！")
                else:
                    # 2. 从题库抽题 (使用 RPC 或 内存随机)
                    # 简单起见，拉取最近的 100 道题并在内存中随机
                    all_qs = supabase.table("question_bank").select("*").in_("chapter_id", chap_ids).limit(100).execute().data
                    
                    if len(all_qs) < limit:
                        st.warning(f"题库题目不足！当前只有 {len(all_qs)} 道，无法生成 {limit} 道的试卷。请先去资料库录题。")
                    else:
                        import random
                        random.shuffle(all_qs)
                        exam_paper = all_qs[:limit]
                        
                        # 初始化考试状态
                        st.session_state.exam_session = {
                            "paper": exam_paper,
                            "answers": {}, # 用户答案
                            "subject_name": sel_sub,
                            "mode": mode,
                            "submitted": False,
                            "score_report": None
                        }
                        st.session_state.exam_start_time = datetime.datetime.now()
                        st.rerun()

        with col_set2:
            # 历史记录
            st.markdown("#### 📜 历史模考")
            try:
                history = supabase.table("mock_exams").select("title, user_score, created_at").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute().data
                if history:
                    for h in history:
                        date_str = h['created_at'][:10]
                        st.markdown(f"<div style='font-size:13px; border-bottom:1px solid #eee; padding:5px;'>{date_str} - <b>{h['user_score']}分</b><br><span style='color:#888'>{h['title']}</span></div>", unsafe_allow_html=True)
                else:
                    st.write("暂无记录")
            except:
                st.write("加载失败")

    # --- 场景 B: 正在考试 (沉浸模式) ---
    else:
        paper = st.session_state.exam_session['paper']
        sub_name = st.session_state.exam_session['subject_name']
        
        # 顶部栏
        c_timer, c_title, c_quit = st.columns([1, 2, 1])
        with c_title:
            st.markdown(f"<h3 style='text-align:center'>{sub_name} - 模拟考场</h3>", unsafe_allow_html=True)
        with c_quit:
            if st.button("退出考试"):
                st.session_state.exam_session = None
                st.rerun()
        
        # 题目渲染区域
        with st.form("exam_form"):
            for idx, q in enumerate(paper):
                st.markdown(f"**第 {idx+1} 题：** {q['content']}")
                
                # 根据题型渲染不同输入组件
                # 目前默认是单选，如果你录入了主观题，这里可以扩展
                qid = str(q['id'])
                
                # 尝试判断是否为主观题 (简单逻辑：看有没有选项)
                is_subjective = q['options'] is None or len(q['options']) == 0
                
                if is_subjective:
                    st.text_area("请输入答案：", key=f"ans_{qid}")
                else:
                    # 选项处理
                    opts = q['options']
                    st.radio("选择：", opts, key=f"ans_{qid}", index=None)
                
                st.divider()
            
            submit_exam = st.form_submit_button("交卷", type="primary", use_container_width=True)
        
        # --- 交卷处理逻辑 ---
        if submit_exam:
            # 1. 收集答案
            user_answers_map = {}
            total_score = 0
            max_score = len(paper) * 10 # 假设每题10分
            
            # 进度条提示
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            full_report = [] # 详细报告
            
            for i, q in enumerate(paper):
                status_text.text(f"正在批改第 {i+1} 题...")
                progress_bar.progress((i + 1) / len(paper))
                
                qid = str(q['id'])
                u_ans_key = f"ans_{qid}"
                
                # 获取用户填写的答案
                # Streamlit Form 中，Radio 返回选中的字符串，Text Area 返回文本
                u_val = st.session_state.get(u_ans_key)
                
                # 判分逻辑
                is_subjective = q['options'] is None or len(q['options']) == 0
                
                score = 0
                ai_comment = ""
                
                if not u_val:
                    u_val = "未作答"
                
                if is_subjective:
                    # 🔥 AI 阅卷 (主观题)
                    grading_prompt = f"""
                    请你作为阅卷老师。
                    题目：{q['content']}
                    标准答案：{q['correct_answer']}
                    考生回答：{u_val}
                    
                    请打分（满分10分），并给出简短评语。
                    返回JSON: {{"score": 5, "comment": "回答不完整..."}}
                    """
                    try:
                        res = call_gemini(grading_prompt)
                        # 解析 AI 返回 (简化处理)
                        res_json = json.loads(res['candidates'][0]['content']['parts'][0]['text'].replace("```json", "").replace("```", ""))
                        score = res_json.get('score', 0)
                        ai_comment = res_json.get('comment', '')
                    except:
                        score = 0
                        ai_comment = "AI 阅卷失败，暂定0分"
                        
                else:
                    # 客观题 (提取选项字母 A/B/C/D)
                    # 假设选项格式是 "A. 选项内容"
                    user_letter = u_val[0] if u_val and len(u_val) > 0 else "X"
                    std_letter = q['correct_answer'][0] if q['correct_answer'] else "Y"
                    
                    if user_letter.upper() == std_letter.upper():
                        score = 10
                        ai_comment = "正确"
                    else:
                        score = 0
                        ai_comment = "错误"
                
                total_score += score
                
                # 记录这道题的详情
                full_report.append({
                    "q_content": q['content'],
                    "u_ans": u_val,
                    "std_ans": q['correct_answer'],
                    "score": score,
                    "comment": ai_comment,
                    "explanation": q['explanation']
                })
                
                # 存入 user_answers 表 (用于弱项分析)
                try:
                    supabase.table("user_answers").insert({
                        "user_id": user_id,
                        "question_id": q['id'],
                        "user_response": str(u_val),
                        "is_correct": score == 10,
                        "score": score
                    }).execute()
                except: pass

            # 存入 mock_exams 表
            try:
                supabase.table("mock_exams").insert({
                    "user_id": user_id,
                    "title": f"{sub_name} - {datetime.date.today()}",
                    "mode": "lite" if len(paper) < 10 else "full",
                    "user_score": total_score,
                    "exam_data": json.dumps(full_report) # 存下整套卷子详情
                }).execute()
            except Exception as e:
                st.error(f"保存试卷失败: {e}")

            # 显示结果
            st.session_state.exam_session['submitted'] = True
            st.session_state.exam_session['score_report'] = {
                "total": total_score,
                "max": max_score,
                "details": full_report
            }
            st.rerun()

        # --- 考后报告界面 ---
        if st.session_state.exam_session.get('submitted'):
            report = st.session_state.exam_session['score_report']
            
            st.balloons()
            st.markdown(f"""
            <div style="text-align:center; padding: 30px; background-color:white; border-radius:15px; box-shadow:0 4px 12px rgba(0,0,0,0.1);">
                <h1 style="color:#00C090; font-size: 60px; margin:0;">{report['total']} <span style="font-size:20px; color:#666">/ {report['max']} 分</span></h1>
                <p>考试结束！请查看下方详细解析</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.divider()
            
            for item in report['details']:
                with st.expander(f"[{item['score']}分] {item['q_content'][:30]}...", expanded=item['score'] == 0):
                    st.write(f"**题目：** {item['q_content']}")
                    c1, c2 = st.columns(2)
                    c1.error(f"你的回答：{item['u_ans']}")
                    c2.success(f"正确答案：{item['std_ans']}")
                    
                    st.info(f"**解析/点评：** {item['comment']} \n\n {item['explanation']}")
            
            if st.button("结束回顾，返回首页"):
                st.session_state.exam_session = None
                st.rerun()


# === 页面：弱项分析 (数据看板) ===
elif menu == "📊 弱项分析":
    st.title("📊 学习效果分析")
    
    # 获取所有做题记录
    try:
        # 联表查询有点复杂，我们先拉取 answer 表，再在 Python 里处理 (低成本方案)
        answers = supabase.table("user_answers").select("*").eq("user_id", user_id).execute().data
        
        if not answers:
            st.info("暂无做题数据，快去刷题吧！")
        else:
            df = pd.DataFrame(answers)
            
            # 1. 总体正确率仪表盘
            total_qs = len(df)
            correct_qs = len(df[df['is_correct'] == True])
            acc_rate = round((correct_qs / total_qs) * 100, 1)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                <div class="css-card">
                    <h3 style="color:#2C3E50">总正确率</h3>
                    <div style="font-size:40px; color:#00C090; font-weight:bold">{acc_rate}%</div>
                    <div style="color:#888">基于 {total_qs} 次答题记录</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                # 用 Plotly 画一个简单的每日刷题量柱状图
                df['date'] = pd.to_datetime(df['created_at']).dt.date
                daily_counts = df.groupby('date').size().reset_index(name='counts')
                
                import plotly.express as px
                fig = px.bar(daily_counts, x='date', y='counts', title="每日刷题趋势", color_discrete_sequence=['#00C090'])
                st.plotly_chart(fig, use_container_width=True)

            # 2. 错题重灾区 (AI 分析)
            st.subheader("🧠 弱项诊断报告")
            
            if st.button("生成 AI 诊断报告"):
                with st.spinner("AI 正在分析你的错题记录..."):
                    # 提取最近错题
                    wrong_df = df[df['is_correct'] == False].tail(10) # 取最近10道错题
                    if wrong_df.empty:
                        st.success("最近表现完美，没有错题！")
                    else:
                        # 理想情况下应该联表查询题目内容，这里简化处理，假设我们只统计错题ID
                        # 实际生产中，你应该 fetch question_bank 获取题目文本
                        # 这里演示 Prompt 逻辑
                        report_prompt = f"""
                        用户最近做错了 {len(wrong_df)} 道题。
                        请给出一段鼓励性但一针见血的学习建议。
                        告诉他应该重点复习哪些方面（假设他是中级会计考生）。
                        """
                        res = call_gemini(report_prompt)
                        if res:
                            advice = res['candidates'][0]['content']['parts'][0]['text']
                            st.markdown(f"""
                            <div class="css-card" style="border-left: 5px solid #FFB74D;">
                                <h4>🩺 AI 诊断意见：</h4>
                                {advice}
                            </div>
                            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"加载数据失败: {e}")






