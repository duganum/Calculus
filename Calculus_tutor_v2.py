import streamlit as st
import json
import random
import re
from logic_v2_GitHub import get_gemini_model, load_problems, check_numeric_match, analyze_and_send_report

# 1. Page Configuration
st.set_page_config(page_title="TAMUCC Calculus Tutor", layout="wide")

# 2. CSS: UI consistency
st.markdown("""
    <style>
    div.stButton > button {
        height: 60px;
        font-size: 16px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Initialize Session State
if "page" not in st.session_state: st.session_state.page = "landing"
if "user_name" not in st.session_state: st.session_state.user_name = None
if "current_prob" not in st.session_state: st.session_state.current_prob = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "lecture_topic" not in st.session_state: st.session_state.lecture_topic = None

# 4. Load Calculus Problems
@st.cache_data
def load_calculus_data():
    # 이전에 생성한 150문제 JSON 파일 로드
    with open('calculus_problems.json', 'r') as f:
        return json.load(f)

PROBLEMS = load_calculus_data()

# --- Page 0: Login ---
if st.session_state.user_name is None:
    st.title("🧮 Calculus AI Tutor Portal")
    st.subheader("Texas A&M University - Corpus Christi")
    with st.form("login_form"):
        name_input = st.text_input("Full Name")
        if st.form_submit_button("Start Learning"):
            if name_input.strip():
                st.session_state.user_name = name_input.strip()
                st.rerun()
    st.stop()

# --- Page 1: Landing (Category Selection) ---
if st.session_state.page == "landing":
    st.title(f"Welcome, {st.session_state.user_name}!")
    st.info("Select a category to start practice or view a lecture.")
    
    # 5 Categories Selection
    st.subheader("💡 Choose Your Focus Area")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    categories = [
        ("Derivatives", "CAL_1"),
        ("Integrals", "CAL_2"),
        ("Partial Derivatives", "CAL_3"),
        ("Vector Analysis", "CAL_4"),
        ("Multiple Integrals", "CAL_5")
    ]
    
    cols = [col1, col2, col3, col4, col5]
    for i, (name, prefix) in enumerate(categories):
        with cols[i]:
            if st.button(f"📘 {name}", key=f"cat_{prefix}", use_container_width=True):
                # 해당 카테고리 문제만 필터링 후 랜덤 선택
                cat_probs = [p for p in PROBLEMS if p['id'].startswith(prefix)]
                st.session_state.current_prob = random.choice(cat_probs)
                st.session_state.page = "chat"
                st.rerun()
            
            if st.button(f"🎓 Lecture", key=f"lec_{prefix}", use_container_width=True):
                st.session_state.lecture_topic = name
                st.session_state.page = "lecture"
                st.rerun()

# --- Page 2: Socratic Practice (Infinite Random Flow) ---
elif st.session_state.page == "chat":
    prob = st.session_state.current_prob
    st.button("🏠 Home", on_click=lambda: setattr(st.session_state, 'page', 'landing'))
    
    st.title("📝 Problem Practice")
    cols = st.columns([2, 1])
    
    with cols[0]:
        st.subheader(prob['category'])
        st.info(prob['statement'])
        
        # Chat interface
        if "chat_session" not in st.session_state or st.session_state.current_prob['id'] != st.session_state.last_id:
            sys_prompt = f"You are a Calculus Tutor at TAMUCC. Help {st.session_state.user_name} solve: {prob['statement']}. Socratic method only. Use LaTeX."
            st.session_state.chat_model = get_gemini_model(sys_prompt)
            st.session_state.chat_session = st.session_state.chat_model.start_chat(history=[])
            st.session_state.last_id = prob['id']

        for msg in st.session_state.chat_session.history:
            with st.chat_message("assistant" if msg.role == "model" else "user"):
                st.markdown(msg.parts[0].text)

        if user_input := st.chat_input("Enter your answer or step..."):
            # Check for numeric match
            is_correct = False
            for target, val in prob['targets'].items():
                if check_numeric_match(user_input, val):
                    is_correct = True
            
            if is_correct:
                st.success("Correct! Well done.")
                if st.button("Next Random Problem ➡️"):
                    # 같은 카테고리에서 다음 문제 랜덤 추출
                    prefix = prob['id'].split('_')[0] + "_" + prob['id'].split('_')[1]
                    cat_probs = [p for p in PROBLEMS if p['id'].startswith(prefix)]
                    st.session_state.current_prob = random.choice(cat_probs)
                    st.rerun()
            else:
                st.session_state.chat_session.send_message(user_input)
                st.rerun()

    with cols[1]:
        st.write("### Tutor Tools")
        if st.button("Get a Hint"):
            st.session_state.chat_session.send_message("Can you give me a small hint for the first step?")
            st.rerun()
        if st.button("New Problem (Skip)"):
            prefix = prob['id'].split('_')[0] + "_" + prob['id'].split('_')[1]
            cat_probs = [p for p in PROBLEMS if p['id'].startswith(prefix)]
            st.session_state.current_prob = random.choice(cat_probs)
            st.rerun()

# --- Page 3: Interactive Lecture ---
elif st.session_state.page == "lecture":
    topic = st.session_state.lecture_topic
    st.title(f"🎓 Lecture: {topic}")
    
    col_content, col_tutor = st.columns([1, 1])
    
    with col_content:
        # 개념 설명 렌더링 (Static 이미지 혹은 텍스트)
        st.write(f"### Understanding {topic}")
        st.markdown(f"In this module, we explore the fundamental principles of **{topic}** as required for the FE Exam.")
        # 정역학처럼 시뮬레이션 이미지가 있다면 여기에 추가 (render_lecture_visual 함수 활용)
        
        if st.button("Back to Menu"):
            st.session_state.page = "landing"
            st.rerun()

    with col_tutor:
        st.subheader("💬 Ask Professor Um")
        # 소크라테스식 대화 인터페이스 (Statics 코드와 동일 로직)
        if "lec_session" not in st.session_state:
            model = get_gemini_model(f"You are Prof. Um teaching {topic}. Start with a question about the concept.")
            st.session_state.lec_session = model.start_chat(history=[])
        
        for msg in st.session_state.lec_session.history:
            with st.chat_message("assistant" if msg.role == "model" else "user"):
                st.markdown(msg.parts[0].text)
        
        if lec_input := st.chat_input("Ask a question..."):
            st.session_state.lec_session.send_message(lec_input)
            st.rerun()