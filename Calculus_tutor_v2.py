import streamlit as st
import json
import random
import re
import time
from logic_v2_GitHub import get_gemini_model, load_problems, check_numeric_match, analyze_and_send_report

# 1. Page Configuration
st.set_page_config(page_title="TAMUCC Calculus Tutor", layout="wide")

# 2. CSS: UI consistency & Status Badge
st.markdown("""
    <style>
    div.stButton > button {
        height: 60px;
        font-size: 16px;
        font-weight: bold;
    }
    .status-badge {
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 14px;
        font-weight: bold;
        display: inline-block;
        border: 1px solid rgba(0,0,0,0.1);
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# 3. Initialize Session State
if "page" not in st.session_state: st.session_state.page = "landing"
if "user_name" not in st.session_state: st.session_state.user_name = None
if "current_prob" not in st.session_state: st.session_state.current_prob = None
if "last_id" not in st.session_state: st.session_state.last_id = None
if "lecture_topic" not in st.session_state: st.session_state.lecture_topic = None
if "api_busy" not in st.session_state: st.session_state.api_busy = False

# 4. Load Problems
PROBLEMS = load_problems()

# --- Helper Logic: Safe History Parsing ---
def get_role(msg):
    role = msg.role if hasattr(msg, 'role') else msg.get('role')
    return "assistant" if role == "model" else "user"

def get_text(msg):
    if hasattr(msg, 'parts'):
        return msg.parts[0].text
    return msg.get('parts')[0].get('text')

# --- Helper: Activity Indicator ---
def draw_status():
    if st.session_state.api_busy:
        st.markdown('<div class="status-badge" style="background-color: #ff4b4b; color: white;">🔴 Professor is reflecting...</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-badge" style="background-color: #28a745; color: white;">🟢 Professor is Ready</div>', unsafe_allow_html=True)

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
    draw_status()
    st.title(f"Welcome, {st.session_state.user_name}!")
    st.info("Select a focus area. Your progress is monitored for academic support.")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    categories = [
        ("Derivatives", "CAL_1"), ("Integrals", "CAL_2"),
        ("Partial Derivatives", "CAL_3"), ("Vector Analysis", "CAL_4"),
        ("Multiple Integrals", "CAL_5")
    ]
    
    cols = [col1, col2, col3, col4, col5]
    for i, (name, prefix) in enumerate(categories):
        with cols[i]:
            if st.button(f"📘 {name}", key=f"cat_{prefix}", use_container_width=True):
                cat_probs = [p for p in PROBLEMS if p['id'].startswith(prefix)]
                if cat_probs:
                    st.session_state.current_prob = random.choice(cat_probs)
                    st.session_state.page = "chat"; st.rerun()
            
            if st.button(f"🎓 Lecture", key=f"lec_{prefix}", use_container_width=True):
                st.session_state.lecture_topic = name
                st.session_state.page = "lecture"; st.rerun()

# --- Page 2: Socratic Chat Practice ---
elif st.session_state.page == "chat":
    draw_status()
    prob = st.session_state.current_prob
    if st.button("🏠 Home"):
        st.session_state.page = "landing"; st.rerun()
    
    st.title("📝 Problem Practice")
    cols = st.columns([2, 1])
    
    with cols[0]:
        st.subheader(prob['category'])
        st.info(prob['statement'])
        
        if "chat_session" not in st.session_state or st.session_state.last_id != prob['id']:
            sys_prompt = (f"You are the Calculus Tutor for {st.session_state.user_name} at TAMUCC. "
                          f"Solve: {prob['statement']}. Socratic method only. Use LaTeX.")
            st.session_state.chat_model = get_gemini_model(sys_prompt)
            st.session_state.chat_session = st.session_state.chat_model.start_chat(history=[])
            start_msg = f"Hello {st.session_state.user_name}. To begin, how would you approach the first derivative/integral of this function?"
            st.session_state.chat_session.history.append({"role": "model", "parts": [{"text": start_msg}]})
            st.session_state.last_id = prob['id']

        # Rendering History
        for msg in st.session_state.chat_session.history:
            with st.chat_message(get_role(msg)):
                st.markdown(get_text(msg))

        # Handle Chat Input
        if user_input := st.chat_input("Enter your answer or step..."):
            st.session_state.api_busy = True
            is_correct = any(check_numeric_match(user_input, val) for val in prob['targets'].values())
            
            if is_correct:
                st.success("Correct! Excellent logic.")
                history_text = "".join([f"{'Tutor' if get_role(m)=='assistant' else 'Student'}: {get_text(m)}\n" for m in st.session_state.chat_session.history])
                analyze_and_send_report(st.session_state.user_name, f"SUCCESS: {prob['id']}", history_text)
                st.session_state.api_busy = False
            else:
                st.session_state.chat_session.send_message(user_input)
                st.session_state.api_busy = False
                st.rerun()

    with cols[1]:
        st.write("### Tutor Tools")
        # Revised Hint Logic: Now works by adding to chat history
        if st.button("💡 Get a Hint", use_container_width=True):
            with st.spinner("Professor is reflecting on a hint..."):
                st.session_state.chat_session.send_message("I am a bit stuck. Could you give me a small hint for the next step?")
            st.rerun()
            
        if st.button("⏭️ New Problem", use_container_width=True):
            prefix = prob['id'].split('_')[0]
            cat_probs = [p for p in PROBLEMS if p['id'].startswith(prefix)]
            st.session_state.current_prob = random.choice(cat_probs)
            st.rerun()

# --- Page 3: Interactive Lecture ---
elif st.session_state.page == "lecture":
    draw_status()
    topic = st.session_state.lecture_topic
    st.title(f"🎓 Lecture: {topic}")
    col_content, col_tutor = st.columns([1, 1])
    
    with col_content:
        st.write(f"### Fundamental Concepts of {topic}")
        st.info("Review the concepts on the right with the Professor.")
        if st.button("Back to Menu", use_container_width=True):
            st.session_state.page = "landing"; st.rerun()

    with col_tutor:
        st.subheader("💬 Conceptual Discussion")
        if "lec_session" not in st.session_state:
            model = get_gemini_model(f"You are Prof. Um teaching {topic}. Socratic method.")
            st.session_state.lec_session = model.start_chat(history=[])
            st.session_state.lec_session.history.append({"role": "model", "parts": [{"text": f"Hello {st.session_state.user_name}. What is your current understanding of {topic}?"}]})
        
        for msg in st.session_state.lec_session.history:
            with st.chat_message(get_role(msg)):
                st.markdown(get_text(msg))
        
        if lec_input := st.chat_input("Ask about the concept..."):
            st.session_state.lec_session.send_message(lec_input)
            st.rerun()
