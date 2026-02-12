import streamlit as st
import json
import random
import re
import time
from logic_v2_GitHub import get_gemini_model, load_problems, check_numeric_match, analyze_and_send_report

# 1. Page Configuration
st.set_page_config(page_title="TAMUCC Calculus Tutor", layout="wide")

# 2. CSS: Professional UI & Fix for Top Clipping
st.markdown("""
    <style>
    div.stButton > button {
        height: 50px;
        font-size: 14px;
        font-weight: bold;
    }
    /* Fixed clipping by increasing top padding and normalizing margins */
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
    /* Ensure info boxes don't crowd the header */
    .stAlert {
        margin-top: 10px;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Initialize Session State
if "page" not in st.session_state: st.session_state.page = "landing"
if "user_name" not in st.session_state: st.session_state.user_name = None
if "current_prob" not in st.session_state: st.session_state.current_prob = None
if "last_id" not in st.session_state: st.session_state.last_id = None
if "api_busy" not in st.session_state: st.session_state.api_busy = False

PROBLEMS = load_problems()

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
    st.title("🧮 Calculus AI Tutor Portal")
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
        ("Derivatives", "CAL_1"), 
        ("Integrals", "CAL_2"), 
        ("Partial Derivatives", "CAL_3"), 
        ("Vector Analysis", "CAL_4"), 
        ("Multiple Integrals", "CAL_5")
    ]
    
    for i, (name, prefix) in enumerate(categories):
        with [col1, col2, col3, col4, col5][i]:
            if st.button(f"📘 {name}", key=f"cat_{prefix}", use_container_width=True):
                cat_probs = [p for p in PROBLEMS if p['id'].startswith(prefix)]
                if cat_probs:
                    st.session_state.current_prob = random.choice(cat_probs)
                    st.session_state.page = "chat"
                    st.rerun()

# --- Page 2: Socratic Chat ---
elif st.session_state.page == "chat":
    prob = st.session_state.current_prob
    
    # Header layout with proper alignment
    header_col1, header_col2 = st.columns([0.8, 0.2])
    with header_col1:
        st.title("📝 Problem Practice")
    with header_col2:
        if st.button("🏠 Home", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()
    
    st.markdown("### Current Problem")
    st.info(prob['statement'])
    
    if "chat_session" not in st.session_state or st.session_state.last_id != prob['id']:
        sys_prompt = (
            f"You are a Socratic Calculus Tutor. Solve: {prob['statement']}. "
            "Ask ONLY one targeted question at a time to lead the student. "
            "ALWAYS use LaTeX for math (e.g., $x^2$). "
            "If the student provides the final correct answer, provide a warm congratulations "
            "and a concise summary of the steps, then STOP asking questions for this problem."
        )
        st.session_state.chat_model = get_gemini_model(sys_prompt)
        st.session_state.chat_session = st.session_state.chat_model.start_chat(history=[])
        start_msg = f"Hello {st.session_state.user_name}. Looking at this expression, what would be our first step?"
        st.session_state.chat_session.history.append({"role": "model", "parts": [{"text": start_msg}]})
        st.session_state.last_id = prob['id']

    # Chat history display - height 400 for compact visibility
    chat_box = st.container(height=400)
    with chat_box:
        for msg in st.session_state.chat_session.history:
            text = get_text(msg)
            if "HIDDEN_INSTRUCTION" not in text:
                with st.chat_message(get_role(msg)):
                    st.markdown(text)

    # User Input Logic
    if user_input := st.chat_input("Enter your step..."):
        st.session_state.api_busy = True
        
        is_correct = any(check_numeric_match(user_input, val) for val in prob['targets'].values())
        
        if is_correct:
            st.session_state.chat_session.history.append({"role": "user", "parts": [{"text": user_input}]})
            hidden_prompt = f"HIDDEN_INSTRUCTION: The user is correct. Their answer was {user_input}. Congratulate them and provide a brief step-by-step summary."
            st.session_state.chat_session.send_message(hidden_prompt)
            
            history_text = "".join([f"{get_role(m)}: {get_text(m)}\n" for m in st.session_state.chat_session.history])
            analyze_and_send_report(st.session_state.user_name, f"SUCCESS: {prob['id']}", history_text)
        else:
            st.session_state.chat_session.send_message(user_input)
            
        st.session_state.api_busy = False
        st.rerun()

    st.markdown("---")
    if st.button("⏭️ Next Problem", use_container_width=False):
        st.session_state.last_id = None
        st.rerun()
