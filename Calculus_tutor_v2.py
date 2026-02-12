import streamlit as st
import json
import random
import re
import time
from logic_v2_GitHub import get_gemini_model, load_problems, check_numeric_match, analyze_and_send_report

# 1. Page Configuration
st.set_page_config(page_title="TAMUCC Calculus Tutor", layout="wide")

# 2. CSS: Professional UI & LaTeX formatting
st.markdown("""
    <style>
    div.stButton > button {
        height: 50px;
        font-size: 14px;
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
    /* Scannable layout adjustments */
    .block-container { padding-top: 2rem; }
    </style>
""", unsafe_allow_html=True)

# 3. Initialize Session State
if "page" not in st.session_state: st.session_state.page = "landing"
if "user_name" not in st.session_state: st.session_state.user_name = None
if "current_prob" not in st.session_state: st.session_state.current_prob = None
if "last_id" not in st.session_state: st.session_state.last_id = None
if "api_busy" not in st.session_state: st.session_state.api_busy = False
if "hint_history" not in st.session_state: st.session_state.hint_history = []

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
    if st.session_state.api_busy:
        st.markdown('<div class="status-badge" style="background-color: #ff4b4b; color: white;">🔴 Professor is reflecting...</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="status-badge" style="background-color: #28a745; color: white;">🟢 Professor is Ready</div>', unsafe_allow_html=True)

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
    categories = [("Derivatives", "CAL_1"), ("Integrals", "CAL_2"), ("Partial Derivatives", "CAL_3"), ("Vector Analysis", "CAL_4"), ("Multiple Integrals", "CAL_5")]
    
    for i, (name, prefix) in enumerate(categories):
        with [col1, col2, col3, col4, col5][i]:
            if st.button(f"📘 {name}", key=f"cat_{prefix}", use_container_width=True):
                cat_probs = [p for p in PROBLEMS if p['id'].startswith(prefix)]
                if cat_probs:
                    st.session_state.current_prob = random.choice(cat_probs)
                    st.session_state.hint_history = []
                    st.session_state.page = "chat"; st.rerun()

# --- Page 2: Socratic Chat ---
elif st.session_state.page == "chat":
    draw_status()
    prob = st.session_state.current_prob
    if st.button("🏠 Home"):
        st.session_state.page = "landing"; st.rerun()
    
    st.title("📝 Problem Practice")
    cols = st.columns([1.5, 1])
    
    with cols[0]:
        st.markdown("### Current Problem")
        st.info(prob['statement'])
        
        if "chat_session" not in st.session_state or st.session_state.last_id != prob['id']:
            sys_prompt = f"You are a Socratic Calculus Tutor. Solve: {prob['statement']}. Only one targeted question at a time. ALWAYS use LaTeX for math (e.g., $x^2$)."
            st.session_state.chat_model = get_gemini_model(sys_prompt)
            st.session_state.chat_session = st.session_state.chat_model.start_chat(history=[])
            start_msg = f"Hello {st.session_state.user_name}. Looking at this expression, what would be our first step in finding the derivative?"
            st.session_state.chat_session.history.append({"role": "model", "parts": [{"text": start_msg}]})
            st.session_state.last_id = prob['id']

        chat_box = st.container(height=400)
        with chat_box:
            for msg in st.session_state.chat_session.history:
                with st.chat_message(get_role(msg)):
                    st.markdown(get_text(msg))

        if user_input := st.chat_input("Enter your step..."):
            st.session_state.api_busy = True
            if any(check_numeric_match(user_input, val) for val in prob['targets'].values()):
                st.success("Correct! Excellent logic.")
                history_text = "".join([f"{get_role(m)}: {get_text(m)}\n" for m in st.session_state.chat_session.history])
                analyze_and_send_report(st.session_state.user_name, f"SUCCESS: {prob['id']}", history_text)
            else:
                st.session_state.chat_session.send_message(user_input)
            st.session_state.api_busy = False
            st.rerun()

    with cols[1]:
        st.write("### 💡 Hint Mini-Chat")
        hint_display = st.container(height=300, border=True)
        with hint_display:
            if not st.session_state.hint_history:
                st.caption("Need a specific derivative rule? Ask here.")
            for hint in st.session_state.hint_history:
                with st.chat_message("assistant" if hint['role'] == "model" else "user"):
                    st.markdown(hint['text'])
        
        if h_input := st.chat_input("Ask for a rule or equation", key="hint_input"):
            st.session_state.hint_history.append({"role": "user", "text": h_input})
            # Force the hint model to use proper LaTeX and avoid HTML tags
            hint_instruction = (
                "Provide a concise math hint. Use ONLY LaTeX for formulas. "
                "Example: Use $\\sec^2(x)$ instead of HTML tags. "
                "Reference these if relevant: "
                "$\\frac{d}{dx}[\\sin(x)] = \\cos(x)$, $\\frac{d}{dx}[\\tan(x)] = \\sec^2(x)$."
            )
            hint_model = get_gemini_model(hint_instruction)
            response = hint_model.generate_content(h_input)
            st.session_state.hint_history.append({"role": "model", "text": response.text})
            st.rerun()

        st.markdown("---")
        if st.button("⏭️ Next Problem", use_container_width=True):
            st.session_state.last_id = None
            st.rerun()
