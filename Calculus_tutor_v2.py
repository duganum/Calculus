import streamlit as st
import json
import random
import re
import time
from logic_v2_GitHub import get_gemini_model, load_problems, check_numeric_match, analyze_and_send_report

# 1. Page Configuration
st.set_page_config(page_title="TAMUCC Calculus Tutor", layout="wide")

# 2. CSS: Professional UI & Fix for the "Sliced" Badge
st.markdown("""
    <style>
    div.stButton > button {
        height: 50px;
        font-size: 14px;
        font-weight: bold;
    }
    .status-badge {
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 14px;
        font-weight: bold;
        display: inline-flex;
        align-items: center;
        border: 1px solid rgba(0,0,0,0.1);
        margin-bottom: 20px;
        margin-top: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .block-container { padding-top: 2rem; }
    h1 {
        margin-top: 10px !important;
        padding-top: 0px !important;
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

def draw_status():
    status_container = st.container()
    if st.session_state.api_busy:
        status_container.markdown('<div class="status-badge" style="background-color: #ff4b4b; color: white;">🔴 Professor is reflecting...</div>', unsafe_allow_html=True)
    else:
        status_container.markdown('<div class="status-badge" style="background-color: #28a745; color: white;">🟢 Professor is Ready</div>', unsafe_allow_html=True)

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
    draw_status()
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
    draw_status()
    prob = st.session_state.current_prob
    
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
        # Updated system prompt to strictly guide the model
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

    # Chat history display
    chat_box = st.container(height=500)
    with chat_box:
        for msg in st.session_state.chat_session.history:
            # We skip internal hidden instructions to prevent "AI talking to itself"
            text = get_text(msg)
            if "HIDDEN_INSTRUCTION" not in text:
                with st.chat_message(get_role(msg)):
                    st.markdown(text)

    # User Input Logic
    if user_input := st.chat_input("Enter your step..."):
        st.session_state.api_busy = True
        
        # Check if user input matches target numerical answers
        is_correct = any(check_numeric_match(user_input, val) for val in prob['targets'].values())
        
        if is_correct:
            # 1. Add the user's actual text to history
            st.session_state.chat_session.history.append({"role": "user", "parts": [{"text": user_input}]})
            
            # 2. Send a hidden instruction for the summary without displaying it in the UI
            hidden_prompt = f"HIDDEN_INSTRUCTION: The user is correct. Their answer was {user_input}. Congratulate them and provide a brief step-by-step summary."
            st.session_state.chat_session.send_message(hidden_prompt)
            
            # 3. Finalize reporting
            history_text = "".join([f"{get_role(m)}: {get_text(m)}\n" for m in st.session_state.chat_session.history])
            analyze_and_send_report(st.session_state.user_name, f"SUCCESS: {prob['id']}", history_text)
        else:
            # Normal Socratic interaction
            st.session_state.chat_session.send_message(user_input)
            
        st.session_state.api_busy = False
        st.rerun()

    st.markdown("---")
    if st.button("⏭️ Next Problem"):
        st.session_state.last_id = None
        st.rerun()
