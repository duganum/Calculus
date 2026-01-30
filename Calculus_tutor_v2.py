import streamlit as st
import json
import random
import re
from logic_v2_GitHub import get_gemini_model, load_problems, check_numeric_match, analyze_and_send_report

# 1. Page Configuration
st.set_page_config(page_title="TAMUCC Calculus Tutor", layout="wide")

# 2. CSS: UI consistency & Button Height
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
if "last_id" not in st.session_state: st.session_state.last_id = None
if "lecture_topic" not in st.session_state: st.session_state.lecture_topic = None

# 4. Load Problems (Using the logic file function)
PROBLEMS = load_problems()

# --- Page 0: Login ---
if st.session_state.user_name is None:
    st.title("🧮 Calculus AI Tutor Portal")
    st.subheader("Texas A&M University - Corpus Christi | Dr. Dugan Um")
    with st.form("login_form"):
        name_input = st.text_input("Full Name (Identification for academic monitoring)")
        if st.form_submit_button("Access Tutor"):
            if name_input.strip():
                st.session_state.user_name = name_input.strip()
                st.rerun()
            else:
                st.warning("Identification is required for academic reporting.")
    st.stop()

# --- Page 1: Main Menu ---
if st.session_state.page == "landing":
    st.title(f"Welcome, {st.session_state.user_name}!")
    st.info("Select a category to start practice. Your progress is monitored for academic support.")
    
    st.subheader("💡 Focus Areas")
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
                cat_probs = [p for p in PROBLEMS if p['id'].startswith(prefix)]
                if cat_probs:
                    st.session_state.current_prob = random.choice(cat_probs)
                    st.session_state.page = "chat"
                    st.rerun()
            
            if st.button(f"🎓 Lecture", key=f"lec_{prefix}", use_container_width=True):
                st.session_state.lecture_topic = name
                st.session_state.page = "lecture"
                st.rerun()

# --- Page 2: Socratic Chat Practice ---
elif st.session_state.page == "chat":
    prob = st.session_state.current_prob
    st.button("🏠 Home", on_click=lambda: setattr(st.session_state, 'page', 'landing'))
    
    st.title("📝 Problem Practice")
    cols = st.columns([2, 1])
    
    with cols[0]:
        st.subheader(prob['category'])
        st.info(prob['statement'])
        
        # Initialize Chat Session
        if "chat_session" not in st.session_state or st.session_state.last_id != prob['id']:
            sys_prompt = (
                f"You are the Calculus Tutor for {st.session_state.user_name} at TAMUCC. "
                f"Solve: {prob['statement']}. Socratic method only. Use LaTeX. "
                "Ask one targeted question at a time. Do not give the final answer immediately."
            )
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
                st.success("Correct! Excellent logic.")
                # 자동 리포트 전송 (정답 달성 시)
                history_text = "--- COMPLETED SUCCESSFULLY ---\n"
                for msg in st.session_state.chat_session.history:
                    role = "Tutor" if msg.role == "model" else "Student"
                    history_text += f"{role}: {msg.parts[0].text}\n"
                analyze_and_send_report(st.session_state.user_name, f"SUCCESS: {prob['id']}", history_text)
                
                if st.button("Next Random Problem ➡️"):
                    prefix = prob['id'].split('_')[0] + "_" + prob['id'].split('_')[1]
                    cat_probs = [p for p in PROBLEMS if p['id'].startswith(prefix)]
                    st.session_state.current_prob = random.choice(cat_probs)
                    st.rerun()
            else:
                st.session_state.chat_session.send_message(user_input)
                st.rerun()

    with cols[1]:
        st.write("### Tutor Tools")
        if st.button("Get a Hint", use_container_width=True):
            st.session_state.chat_session.send_message("I'm stuck. Can you guide me to the next step?")
            st.rerun()
            
        # 모니터링 기능이 포함된 Skip 버튼
        if st.button("New Problem (Skip)", use_container_width=True):
            history_text = "--- STUDENT SKIPPED PROBLEM ---\n"
            if "chat_session" in st.session_state:
                for msg in st.session_state.chat_session.history:
                    role = "Tutor" if msg.role == "model" else "Student"
                    history_text += f"{role}: {msg.parts[0].text}\n"
            
            # Skip 리포트 전송
            with st.spinner("Recording session traffic..."):
                analyze_and_send_report(st.session_state.user_name, f"SKIP REPORT: {prob['id']}", history_text)
            
            # 다음 문제로 이동
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
        st.write(f"### Fundamental Concepts of {topic}")
        st.info("Review the core theorems and formulas below before starting practice.")
        if st.button("Back to Menu", use_container_width=True):
            st.session_state.page = "landing"; st.rerun()

    with col_tutor:
        st.subheader("💬 Conceptual Discussion")
        if "lec_session" not in st.session_state:
            model = get_gemini_model(f"You are Prof. Um teaching {topic}. Start with a Socratic question.")
            st.session_state.lec_session = model.start_chat(history=[])
        
        for msg in st.session_state.lec_session.history:
            with st.chat_message("assistant" if msg.role == "model" else "user"):
                st.markdown(msg.parts[0].text)
        
        if lec_input := st.chat_input("Ask about the concept..."):
            st.session_state.lec_session.send_message(lec_input); st.rerun()
