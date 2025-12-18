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
            
            uploaded_b = st.file_uploader("上传真题/母题 PDF", type="pdf", key="pdf_b")
            
            # 读取总页数
            total_pages = 0
            if uploaded_b:
                try:
                    with pdfplumber.open(uploaded_b) as pdf:
                        total_pages = len(pdf.pages)
                    st.success(f"📄 检测到文件共 {total_pages} 页")
                except:
                    st.error("无法读取页数")

            # --- 核心修改：双区间选择器 ---
            st.markdown("#### 1. 设定题目位置")
            c1, c2 = st.columns(2)
            with c1: q_start = st.number_input("题目开始页", 1, value=1)
            with c2: q_end = st.number_input("题目结束页", 1, value=min(10, total_pages) if total_pages else 10)
            
            # 答案位置开关
            separate_answer = st.checkbox("答案在文件后半部分 (跨页码读取)", value=False)
            
            a_text = "" # 初始化
            
            if separate_answer:
                st.markdown("#### 2. 设定答案位置")
                st.caption("请去 PDF 末尾找一下这一章答案在哪几页")
                c3, c4 = st.columns(2)
                with c3: a_start = st.number_input("答案开始页", 1, value=total_pages if total_pages else 1)
                with c4: a_end = st.number_input("答案结束页", 1, value=total_pages if total_pages else 1)
            
            custom_hint = st.text_input("给 AI 的特别叮嘱", placeholder="例如：这是第一章存货的题，请把答案匹配对...")
            
            # Session State
            if 'extracted_data' not in st.session_state: st.session_state.extracted_data = None

            if st.button("🔍 组合读取并提取"):
                if uploaded_b:
                    if q_end < q_start:
                        st.error("题目页码范围错误")
                    else:
                        # 1. 提取题目部分
                        with st.spinner(f"正在读取题目 (P{q_start}-{q_end})..."):
                            uploaded_b.seek(0)
                            q_raw_text = extract_text_from_pdf(uploaded_b, q_start, q_end)
                        
                        # 2. 提取答案部分 (如果有)
                        a_raw_text = ""
                        if separate_answer:
                            if a_end < a_start:
                                st.error("答案页码范围错误")
                                st.stop()
                            with st.spinner(f"正在读取答案 (P{a_start}-{a_end})..."):
                                uploaded_b.seek(0)
                                a_raw_text = extract_text_from_pdf(uploaded_b, a_start, a_end)
                        
                        # 3. 拼接文本
                        full_context = f"""
                        【以下是题目部分】：
                        {q_raw_text}
                        
                        ----------------
                        【以下是答案部分】：
                        {a_raw_text}
                        """
                        
                        if len(full_context) < 20:
                            st.warning("提取内容过少，请检查页码。")
                        else:
                            # 4. 发送给 AI
                            with st.spinner("AI 正在左右互搏 (匹配题目与答案)..."):
                                prompt = f"""
                                任务：从以下文本中提取会计题目和对应的答案。
                                
                                情况说明：题目和答案在不同的区域。
                                1. 题目区域包含了题干和选项。
                                2. 答案区域包含了题号和正确选项（可能还有解析）。
                                请根据【题号】（如 1. 2. 3. 或 (1) (2)）将它们对应起来。
                                
                                额外要求：{custom_hint}
                                
                                返回格式：纯 JSON 列表
                                [
                                    {{
                                        "question": "题目...",
                                        "options": ["A.","B."],
                                        "answer": "A", 
                                        "explanation": "解析..."
                                    }}
                                ]
                                
                                待处理文本：
                                {full_context[:15000]} 
                                """
                                # 稍微放宽字符限制，因为包含了答案部分
                                
                                res = call_gemini(prompt)
                                if res and 'candidates' in res:
                                    try:
                                        json_str = res['candidates'][0]['content']['parts'][0]['text']
                                        clean_json = json_str.replace("```json", "").replace("```", "").strip()
                                        st.session_state.extracted_data = json.loads(clean_json)
                                    except Exception as e:
                                        st.error(f"AI 没能解析成功: {e}")
                                        st.write(res)

            # 预览与保存 (代码不变)
            if st.session_state.extracted_data:
                st.divider()
                st.subheader("🧐 匹配结果预览")
                df = pd.DataFrame(st.session_state.extracted_data)
                st.dataframe(df, use_container_width=True)
                
                if st.button("💾 确认存入"):
                    save_questions_batch(st.session_state.extracted_data, current_chap_id, user_id)
                    st.balloons()
                    st.success("入库成功！")
                    st.session_state.extracted_data = None


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


