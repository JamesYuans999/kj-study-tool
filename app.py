import streamlit as st
import google.generativeai as genai
import json
import random

# --- 配置 ---
# 请在实际运行时，在 Streamlit 的 secrets 或环境变量中设置 API key，
# 或者在本地测试时直接替换下方的 "YOUR_API_KEY" (注意保密)
# st.secrets["GOOGLE_API_KEY"] 是部署时的做法
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    # 如果你在本地运行且没有配置 secrets，临时填入你的 Key
    API_KEY = "在这里填入你的Google_Gemini_API_Key" 

genai.configure(api_key=API_KEY)

# --- 模型设置 ---
# 使用 flash 模型，速度快且免费额度高
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 页面配置 ---
st.set_page_config(
    page_title="中级会计智能备考助手",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS 美化 (简洁风格) ---
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border-radius: 10px;
        color: #155724;
    }
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;
        border-radius: 10px;
        color: #721c24;
    }
    .stProgress .st-bo {
        background-color: #4CAF50;
    }
</style>
""", unsafe_allow_html=True)

# --- Session State 初始化 (用于存储题库、进度、错题) ---
if 'questions' not in st.session_state:
    st.session_state.questions = []
if 'current_q_index' not in st.session_state:
    st.session_state.current_q_index = 0
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'mistakes' not in st.session_state:
    st.session_state.mistakes = [] # 错题集
if 'context_text' not in st.session_state:
    st.session_state.context_text = ""

# --- 核心函数 ---

def generate_questions(text_content, num=3):
    """调用 Gemini 生成题目"""
    prompt = f"""
    你是一位资深的中国会计中级职称考试出题专家。
    请根据以下提供的学习资料内容，生成 {num} 道单项选择题。
    
    资料内容：
    {text_content[:5000]} (内容截取以防过长)
    
    要求：
    1. 题目难度需符合中级会计考试标准。
    2. 必须以纯 JSON 格式返回，不要包含 Markdown 格式标记（如 ```json）。
    3. JSON 结构如下：
    [
        {{
            "question": "题目描述",
            "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
            "answer": "A",
            "explanation": "详细解析，包含考点引用和错误原因分析。",
            "suggestion": "针对此考点的简短复习建议"
        }}
    ]
    """
    try:
        with st.spinner('AI 正在研读资料并为你出题...'):
            response = model.generate_content(prompt)
            # 清理可能的 markdown 标记
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
    except Exception as e:
        st.error(f"生成题目失败，可能是网络或API限制: {e}")
        return []

# --- 侧边栏：导航与状态 ---
with st.sidebar:
    st.title("📊 学习仪表盘")
    
    mode = st.radio("选择模式", ["📖 资料上传 & 出题", "✍️ 开始刷题", "❌ 错题本复习"])
    
    st.divider()
    
    # 进度显示
    total_q = len(st.session_state.questions)
    done_q = st.session_state.current_q_index
    if total_q > 0:
        progress = done_q / total_q
        st.write(f"当前进度: {done_q}/{total_q}")
        st.progress(progress)
    
    st.metric("错题数量", len(st.session_state.mistakes))
    
    st.info("💡 建议：每天利用碎片时间刷5-10题，保持题感。")

# --- 主界面逻辑 ---

if mode == "📖 资料上传 & 出题":
    st.header("Step 1: 建立你的专属题库")
    st.write("你可以复制粘贴教材重点、法条或网上的笔记，AI 将基于此为你出题。")
    
    user_text = st.text_area("在此粘贴学习资料 (支持会计实务、财管、经济法)", height=200, placeholder="例如：长期股权投资的权益法核算规则...")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        q_num = st.number_input("生成题目数量", min_value=1, max_value=10, value=3)
    
    if st.button("🚀 生成题目"):
        if user_text:
            st.session_state.context_text = user_text
            new_qs = generate_questions(user_text, q_num)
            if new_qs:
                st.session_state.questions = new_qs
                st.session_state.current_q_index = 0
                st.session_state.score = 0
                st.success(f"成功生成 {len(new_qs)} 道题目！请切换到‘开始刷题’模式。")
        else:
            st.warning("请先输入学习资料内容。")

elif mode == "✍️ 开始刷题":
    st.header("Step 2: 实战演练")
    
    questions = st.session_state.questions
    idx = st.session_state.current_q_index
    
    if not questions:
        st.info("题库为空，请先去‘资料上传’页面生成题目。")
    elif idx >= len(questions):
        st.balloons()
        st.success("🎉 恭喜！你已完成本轮练习。")
        if st.button("清空并重新开始"):
            st.session_state.questions = []
            st.session_state.current_q_index = 0
    else:
        q = questions[idx]
        
        st.subheader(f"Question {idx + 1}")
        st.markdown(f"**{q['question']}**")
        
        # 选项处理
        user_choice = st.radio("请选择:", q['options'], key=f"q_{idx}", index=None)
        
        # 提交按钮
        if st.button("提交答案"):
            if user_choice:
                selected_letter = user_choice[0] # 获取 A/B/C/D
                
                if selected_letter == q['answer']:
                    st.markdown(f"<div class='success-box'>✅ 回答正确！</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='error-box'>❌ 回答错误。正确答案是 {q['answer']}</div>", unsafe_allow_html=True)
                    # 加入错题本 (去重)
                    if q not in st.session_state.mistakes:
                        st.session_state.mistakes.append(q)
                
                # 显示解析
                with st.expander("查看详细解析 & 举例", expanded=True):
                    st.markdown(f"**解析：** {q['explanation']}")
                    st.markdown(f"**学习建议：** {q['suggestion']}")
                    if st.button("让 AI 举一个类似的例子 (举一反三)"):
                        with st.spinner("生成例子中..."):
                            ex_prompt = f"针对会计知识点：'{q['question']}'，请举一个具体的数字案例或生活化例子来帮助理解。"
                            ex_res = model.generate_content(ex_prompt)
                            st.write(ex_res.text)

                # 下一题按钮
                if st.button("下一题 ➡️"):
                    st.session_state.current_q_index += 1
                    st.rerun()
            else:
                st.warning("请先选择一个选项。")

elif mode == "❌ 错题本复习":
    st.header("Step 3: 查漏补缺")
    
    if not st.session_state.mistakes:
        st.write("太棒了！目前没有错题。")
    else:
        st.write(f"你共有 {len(st.session_state.mistakes)} 道错题待复习。")
        
        for i, mq in enumerate(st.session_state.mistakes):
            with st.expander(f"错题 {i+1}: {mq['question'][:20]}..."):
                st.markdown(f"**题目：** {mq['question']}")
                st.markdown(f"**选项：** {mq['options']}")
                st.markdown(f"**正确答案：** {mq['answer']}")
                st.info(f"💡 **解析：** {mq['explanation']}")
                
                if st.button(f"我已掌握，移除此题", key=f"del_{i}"):
                    st.session_state.mistakes.pop(i)
                    st.rerun()