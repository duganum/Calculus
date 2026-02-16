import streamlit as st
import json
import random
import re
import time
import os
from google.api_core import exceptions  # Added for rate limit handling
from logic_v2_GitHub import get_gemini_model, check_numeric_match, analyze_and_send_report

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
        padding-top: 1.5rem !important; 
        max-width: 1100px; 
    }
    .status-badge {
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 14px;
        font-weight: bold;
        display: inline-block;
        border: 1px solid rgba(0,0,0,0.1);
        margin-top: 5px;
    }
    h1 {
        margin-top: 0px !important;
        padding-top: 0px !important;
        font-size: 2rem !important;
        line-height: 1.2 !important;
    }
    .stChatInput {
        padding-bottom: 10px !important;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Load Calculus Problems
@st.cache_data
def load_calculus_data():
    file_name = 'calculus_problems.json'
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        base_path = os.path.dirname(__file__)
        full_path = os.path.join(base_path, file_name)
        with open(full_path, 'r', encoding='utf-8') as f:
            return json.load(f)

PROBLEMS = load_calculus_data()

# 4. Initialize Session State
if "page" not in st.session_state: st.session_state.page = "landing"
if "user_name" not in st.session_state: st.session_state.user_name = None
if "current_prob" not in st.session_state: st.session_state.current_prob = None
if "last_id" not in st.session_state: st.session_state.last_id = None
if "api_busy" not in st.session_state: st.session_state.api_busy = False
if "lecture_topic" not in st.session_state: st.session_state.lecture_topic = None

# --- Helper Logic ---
def get_role(msg):
    role = msg.role if hasattr(msg, 'role') else msg.get('role')
    return "assistant" if role == "model" else "user"

def get_text(msg):
    if hasattr(msg, 'parts'):
        return msg.parts[0].text
    return msg.get('parts')[0].get('text')

def draw_header_with_status(title_text):
    head_col1, head_col2 = st.columns([4, 1])
    with head_col1:
        st.title(title_text)
    with head_col2:
        if st.session_state.api_busy:
            st.markdown('<div class="status-badge" style="background-color: #ff4b4b; color: white;">🔴 Professor Busy</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-badge" style="background-color: #28a745; color: white;">🟢 Professor Ready</div>', unsafe_allow_html=True)

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
    draw_header_with_status(f"Welcome, {st.session_state.user_name}!")
    st.info("Select a focus area to begin your Socratic practice.")
    
    categories = [
        ("Derivatives", "CAL_1"),
        ("Integrals", "CAL_2"),
        ("Partial Derivatives", "CAL_3"),
        ("Vector Analysis", "CAL_4"),
        ("Multiple Integrals", "CAL_5")
    ]
    
    # SECTION A: Interactive Lectures
    st.markdown("### 🎓 Interactive Lectures")
    col_l1, col_l2, col_l3, col_l4, col_l5 = st.columns(5)
    l_cols = [col_l1, col_l2, col_l3, col_l4, col_l5]
    
    for i, (name, prefix) in enumerate(categories):
        with l_cols[i]:
            if st.button(f"🎓 Lecture: {name}", key=f"lec_{prefix}", use_container_width=True):
                st.session_state.lecture_topic = name
                st.session_state.page = "lecture"
                st.rerun()

    st.markdown("---")
    
    # SECTION B: Practice Problems
    st.markdown("### 📝 Problem Practice")
    col_p1, col_p2, col_p3, col_p4, col_p5 = st.columns(5)
    p_cols = [col_p1, col_p2, col_p3, col_p4, col_p5]
    
    for i, (name, prefix) in enumerate(categories):
        with p_cols[i]:
            if st.button(f"📘 {name} Problems", key=f"cat_{prefix}", use_container_width=True):
                cat_probs = [p for p in PROBLEMS if p['id'].startswith(prefix)]
                if cat_probs:
                    st.session_state.current_prob = random.choice(cat_probs)
                    st.session_state.page = "chat"
                    st.rerun()

# --- Page 2: Socratic Chat ---
elif st.session_state.page == "chat":
    prob = st.session_state.current_prob
    draw_header_with_status("📝 Problem Practice")
    
    col_info, col_chat = st.columns([1, 1.2])
    
    with col_info:
        st.markdown(f"**Category:** {prob['category']}")
        st.info(prob['statement'])
        if st.button("🏠 Exit to Main", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()
    
    if "chat_session" not in st.session_state or st.session_state.last_id != prob['id']:
        sys_prompt = (
            f"You are a Socratic Calculus Tutor. Solve: {prob['statement']}. "
            "Ask ONE targeted question at a time. ALWAYS use LaTeX for math. "
            "Do not provide direct answers. Guide the student step-by-step."
        )
        try:
            st.session_state.chat_model = get_gemini_model(sys_prompt)
            st.session_state.chat_session = st.session_state.chat_model.start_chat(history=[])
            start_msg = f"Hello {st.session_state.user_name}. Looking at this problem, what would be our first step?"
            st.session_state.chat_session.history.append({"role": "model", "parts": [{"text": start_msg}]})
            st.session_state.last_id = prob['id']
        except Exception as e:
            st.error(f"Professor Initialization Error: {e}")

    with col_chat:
        st.markdown("### 💬 Socratic Discussion")
        chat_box = st.container(height=400, border=True)
        with chat_box:
            if "chat_session" in st.session_state:
                for msg in st.session_state.chat_session.history:
                    text = get_text(msg)
                    if "HIDDEN_INSTRUCTION" not in text:
                        with st.chat_message(get_role(msg)):
                            st.markdown(text)

        if user_input := st.chat_input("Analyze..."):
            st.session_state.api_busy = True
            is_correct = any(check_numeric_match(user_input, val) for val in prob['targets'].values())
            
            try:
                if is_correct:
                    st.session_state.chat_session.history.append({"role": "user", "parts": [{"text": user_input}]})
                    hidden_prompt = f"HIDDEN_INSTRUCTION: Correct was {user_input}. Congratulate and summarize steps."
                    st.session_state.chat_session.send_message(hidden_prompt)
                    history_text = "".join([f"{get_role(m)}: {get_text(m)}\n" for m in st.session_state.chat_session.history])
                    analyze_and_send_report(st.session_state.user_name, f"Calculus Success: {prob['id']}", history_text)
                else:
                    st.session_state.chat_session.send_message(user_input)
                
                st.session_state.api_busy = False
                st.rerun()
            except exceptions.ResourceExhausted:
                st.session_state.api_busy = False
                st.error("The Professor is currently overwhelmed (Rate Limit). Please wait 60 seconds.")
            except Exception as e:
                st.session_state.api_busy = False
                st.error(f"Connection Pause: {e}")

    st.markdown("---")
    if st.button("⏭️ Next Problem"):
        current_prefix = prob['id'].split('_')[0] + "_" + prob['id'].split('_')[1]
        cat_probs = [p for p in PROBLEMS if p['id'].startswith(current_prefix)]
        if cat_probs:
            remaining = [p for p in cat_probs if p['id'] != prob['id']]
            st.session_state.current_prob = random.choice(remaining if remaining else cat_probs)
        st.session_state.last_id = None
        st.rerun()

# --- Page 3: Interactive Lecture ---
elif st.session_state.page == "lecture":
    topic = st.session_state.lecture_topic
    draw_header_with_status(f"🎓 Lecture: {topic}")
    col_content, col_tutor = st.columns([1, 1])
    
    with col_content:
        st.write(f"### Understanding {topic}")
        st.markdown(f"In this module, we explore the fundamental principles of **{topic}** required for your calculus progress.")
        if st.button("🏠 Exit to Main", use_container_width=True):
            if "lec_session" in st.session_state: del st.session_state.lec_session
            st.session_state.page = "landing"
            st.rerun()

    with col_tutor:
        st.subheader("💬 Ask the Professor")
        if "lec_session" not in st.session_state:
            try:
                model = get_gemini_model(f"You are a Calculus Professor teaching {topic}. Lead with Socratic questions.")
                st.session_state.lec_session = model.start_chat(history=[])
                greeting = f"Welcome! What part of {topic} would you like to discuss first?"
                st.session_state.lec_session.history.append({"role": "model", "parts": [{"text": greeting}]})
            except Exception as e:
                st.error(f"Professor Error: {e}")
        
        lec_container = st.container(height=400, border=True)
        with lec_container:
            if "lec_session" in st.session_state:
                for msg in st.session_state.lec_session.history:
                    with st.chat_message(get_role(msg)):
                        st.markdown(get_text(msg))
            
        if lec_input := st.chat_input("Ask a question..."):
            st.session_state.api_busy = True
            try:
                st.session_state.lec_session.send_message(lec_input)
                st.session_state.api_busy = False
                st.rerun()
            except exceptions.ResourceExhausted:
                st.session_state.api_busy = False
                st.error("Professor is thinking deeply (Rate Limit). Please wait a moment.")
            except Exception as e:
                st.session_state.api_busy = False
                st.error(f"Error: {e}")
