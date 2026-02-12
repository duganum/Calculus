import streamlit as st
import json
import random
import re
import time
import os
from logic_v2_GitHub import get_gemini_model, check_numeric_match, analyze_and_send_report

# 1. Page Configuration
st.set_page_config(page_title="TAMUCC Engineering Economy Tutor", layout="wide")

# 2. CSS: Professional UI & Fix for Top Clipping
st.markdown("""
    <style>
    div.stButton > button {
        height: 50px;
        font-size: 14px;
        font-weight: bold;
    }
    .block-container { 
        padding-top: 3.5rem !important; 
        max-width: 1000px; 
    }
    h1 {
        margin-top: 0px !important;
        padding-top: 0px !important;
        font-size: 2rem !important;
        line-height: 1.2 !important;
    }
    .stAlert {
        margin-top: 10px;
        margin-bottom: 10px;
    }
    .stChatInput {
        padding-bottom: 20px !important;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Initialize Session State
if "page" not in st.session_state: st.session_state.page = "landing"
if "user_name" not in st.session_state: st.session_state.user_name = None
if "current_prob" not in st.session_state: st.session_state.current_prob = None
if "last_id" not in st.session_state: st.session_state.last_id = None
if "api_busy" not in st.session_state: st.session_state.api_busy = False
if "lecture_topic" not in st.session_state: st.session_state.lecture_topic = None

# 4. Load Engineering Economics Problems
@st.cache_data
def load_engineering_economics_data():
    # Matching the filename from your GitHub filesystem exactly
    file_name = 'Eng_Economics_problems.json'
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        base_path = os.path.dirname(__file__)
        full_path = os.path.join(base_path, file_name)
        with open(full_path, 'r', encoding='utf-8') as f:
            return json.load(f)

PROBLEMS = load_engineering_economics_data()

# --- Helper Logic ---
def get_role(msg):
    role = msg.role if hasattr(msg, 'role') else msg.get('role')
    return "assistant" if role == "model" else "user"

def get_text(msg):
    if hasattr(msg, 'parts'):
        return msg.parts[0].text
    return msg.get('parts')[0].get('text')

# --- Page 0: Login ---
if st.session_state.user_name is None:
    st.title("💰 Engineering Economy AI Tutor")
    with st.form("login_form"):
        name_input = st.text_input("Enter Full Name")
        if st.form_submit_button("Access Tutor"):
            if name_input.strip():
                st.session_state.user_name = name_input.strip()
                st.rerun()
    st.stop()

# --- Page 1: Main Menu ---
if st.session_state.page == "landing":
    st.title(f"Welcome, {st.session_state.user_name}!")
    st.info("Select a focus area to begin your Socratic practice.")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    categories = [
        ("Time Value of Money", "EngEco_1"),
        ("Comparison of Alternatives", "EngEco_2"),
        ("Cost/Financial Analysis", "EngEco_3"),
        ("Risk & Uncertainty", "EngEco_4"),
        ("Specialized Apps", "EngEco_5")
    ]
    
    cols = [col1, col2, col3, col4, col5]
    for i, (name, prefix) in enumerate(categories):
        with cols[i]:
            # Practice Button
            if st.button(f"📘 {name}", key=f"cat_{prefix}", use_container_width=True):
                cat_probs = [p for p in PROBLEMS if p['id'].startswith(prefix)]
                if cat_probs:
                    st.session_state.current_prob = random.choice(cat_probs)
                    st.session_state.page = "chat"
                    st.rerun()
            
            # Lecture Button (Restored below each category)
            if st.button(f"🎓 Lecture", key=f"lec_{prefix}", use_container_width=True):
                st.session_state.lecture_topic = name
                st.session_state.page = "lecture"
                st.rerun()

# --- Page 2: Socratic Chat ---
elif st.session_state.page == "chat":
    prob = st.session_state.current_prob
    header_col1, header_col2 = st.columns([0.8, 0.2])
    with header_col1:
        st.title("📝 Problem Practice")
    with header_col2:
        if st.button("🏠 Home", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()
    
    st.markdown(f"**Category:** {prob['category']}")
    st.info(prob['statement'])
    
    if "chat_session" not in st.session_state or st.session_state.last_id != prob['id']:
        sys_prompt = (
            f"You are an Engineering Economy Professor. Help solve: {prob['statement']}. "
            "Ask ONE targeted question at a time. ALWAYS use LaTeX for math/factors. "
            "If the student provides the correct answer, congratulate them and provide a brief summary."
        )
        st.session_state.chat_model = get_gemini_model(sys_prompt)
        st.session_state.chat_session = st.session_state.chat_model.start_chat(history=[])
        start_msg = f"Hello {st.session_state.user_name}. Looking at this problem, what is the first parameter we need to identify?"
        st.session_state.chat_session.history.append({"role": "model", "parts": [{"text": start_msg}]})
        st.session_state.last_id = prob['id']

    chat_container = st.container()
    with chat_container:
        chat_box = st.container(height=400)
        with chat_box:
            for msg in st.session_state.chat_session.history:
                text = get_text(msg)
                if "HIDDEN_INSTRUCTION" not in text:
                    with st.chat_message(get_role(msg)):
                        st.markdown(text)

        if user_input := st.chat_input("Enter your step..."):
            st.session_state.api_busy = True
            is_correct = any(check_numeric_match(user_input, val) for val in prob['targets'].values())
            
            if is_correct:
                st.session_state.chat_session.history.append({"role": "user", "parts": [{"text": user_input}]})
                hidden_prompt = f"HIDDEN_INSTRUCTION: Correct was {user_input}. Congratulate and summarize steps."
                st.session_state.chat_session.send_message(hidden_prompt)
                history_text = "".join([f"{get_role(m)}: {get_text(m)}\n" for m in st.session_state.chat_session.history])
                analyze_and_send_report(st.session_state.user_name, f"SUCCESS: {prob['id']}", history_text)
            else:
                st.session_state.chat_session.send_message(user_input)
            
            st.session_state.api_busy = False
            st.rerun()

    st.markdown("---")
    if st.button("⏭️ Next Problem"):
        prefix = prob['id'].rsplit('_', 1)[0]
        cat_probs = [p for p in PROBLEMS if p['id'].startswith(prefix)]
        if cat_probs:
            remaining = [p for p in cat_probs if p['id'] != prob['id']]
            st.session_state.current_prob = random.choice(remaining if remaining else cat_probs)
        st.session_state.last_id = None
        st.rerun()

# --- Page 3: Interactive Lecture ---
elif st.session_state.page == "lecture":
    topic = st.session_state.lecture_topic
    st.title(f"🎓 Lecture: {topic}")
    col_content, col_tutor = st.columns([1, 1])
    
    with col_content:
        st.write(f"### Understanding {topic}")
        st.markdown(f"In this module, we explore the fundamental principles of **{topic}** required for the FE Exam.")
        if st.button("Back to Menu"):
            st.session_state.page = "landing"
            st.rerun()

    with col_tutor:
        st.subheader("💬 Ask Professor Um")
        if "lec_session" not in st.session_state:
            model = get_gemini_model(f"You are Prof. Um teaching {topic}. Lead the student with Socratic questions.")
            st.session_state.lec_session = model.start_chat(history=[])
        
        for msg in st.session_state.lec_session.history:
            with st.chat_message(get_role(msg)):
                st.markdown(get_text(msg))
        
        if lec_input := st.chat_input("Ask a question about the concept..."):
            st.session_state.lec_session.send_message(lec_input)
            st.rerun()
