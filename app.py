import streamlit as st
import requests
import json
import random

# --- 核心配置 ---
# 依然从 Secrets 获取 Key
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    API_KEY = "你的API_KEY_本地测试用"

# 这是一个直接访问 Google Gemini API 的函数，不依赖安装包
def call_gemini_api(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-robotics-er-1.5-preview:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API 请求失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"网络错误: {e}")
        return None

# --- 页面配置 ---
st.set_page_config(
    page_title="中级会计智能备考助手",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stButton>button {width: 100%; border-radius: 10px; height: 3em;}
    .success-box {padding: 1rem; background-color: #d4edda; border-radius: 10px; color: #155724;}
    .error-box {padding: 1rem; background-color: #f8d7da; border-radius: 10px; color: #721c24;}
</style>
""", unsafe_allow_html=True)

# --- Session State ---
if 'questions' not in st.session_state: st.session_state.questions = []
if 'current_q_index' not in st.session_state: st.session_state.current_q_index = 0
if 'mistakes' not in st.session_state: st.session_state.mistakes = []

# --- 业务逻辑 ---

def generate_questions(text_content, num=3):
    prompt = f"""
    你是一位资深的中国会计中级职称考试出题专家。
    请根据以下资料生成 {num} 道单选题。
    
    资料：{text_content[:4000]}
    
    要求：
    严格直接返回纯 JSON 格式，不要用markdown代码块包裹(不要写```json)，格式如下：
    [
        {{
            "question": "题目",
            "options": ["A. x", "B. x", "C. x", "D. x"],
            "answer": "A",
            "explanation": "解析",
            "suggestion": "建议"
        }}
    ]
    """
    
    with st.spinner('AI 正在出题 (API 直连模式)...'):
        result = call_gemini_api(prompt)
        if result:
            try:
                # 解析 Google 返回的复杂 JSON 结构
                raw_text = result['candidates'][0]['content']['parts'][0]['text']
                # 清理一下可能的格式干扰
                clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                return json.loads(clean_text)
            except Exception as e:
                st.error(f"解析题目数据出错，请重试。错误: {e}")
                st.write("原始返回:", result) # 调试用
                return []
        return []

# --- 界面 ---
with st.sidebar:
    st.title("📊 学习仪表盘")
    mode = st.radio("模式", ["📖 资料上传", "✍️ 刷题", "❌ 错题本"])
    st.divider()
    st.metric("错题数", len(st.session_state.mistakes))

if mode == "📖 资料上传":
    st.header("Step 1: 建立题库")
    user_text = st.text_area("粘贴教材/法条内容", height=200)
    q_num = st.number_input("题目数量", 1, 10, 3)
    
    if st.button("🚀 生成题目"):
        if user_text:
            qs = generate_questions(user_text, q_num)
            if qs:
                st.session_state.questions = qs
                st.session_state.current_q_index = 0
                st.success(f"成功生成 {len(qs)} 道题！请去刷题页面。")

elif mode == "✍️ 刷题":
    st.header("Step 2: 实战")
    qs = st.session_state.questions
    idx = st.session_state.current_q_index
    
    if not qs:
        st.info("暂无题目，请先上传资料。")
    elif idx >= len(qs):
        st.balloons()
        st.success("本轮完成！")
        if st.button("重来"):
            st.session_state.questions = []
            st.session_state.current_q_index = 0
            st.rerun()
    else:
        q = qs[idx]
        st.subheader(f"Q{idx+1}: {q['question']}")
        choice = st.radio("选项", q['options'], key=f"q_{idx}", index=None)
        
        if st.button("提交"):
            if choice:
                if choice[0] == q['answer']:
                    st.markdown(f"<div class='success-box'>✅ 正确</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='error-box'>❌ 错误。答案：{q['answer']}</div>", unsafe_allow_html=True)
                    if q not in st.session_state.mistakes:
                        st.session_state.mistakes.append(q)
                
                with st.expander("解析", expanded=True):
                    st.write(q['explanation'])
                    st.caption("💡 " + q['suggestion'])
                
                if st.button("下一题"):
                    st.session_state.current_q_index += 1
                    st.rerun()

elif mode == "❌ 错题本":
    st.header("错题回顾")
    for i, q in enumerate(st.session_state.mistakes):
        with st.expander(f"错题 {i+1}: {q['question']}"):
            st.write(f"正确答案: {q['answer']}")
            st.write(f"解析: {q['explanation']}")
            if st.button("移除", key=f"del_{i}"):
                st.session_state.mistakes.pop(i)
                st.rerun()

