import streamlit as st
import google.generativeai as genai
import json
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_gemini_model(system_instruction):
    """Gemini 2.0 Flash 모델을 초기화합니다."""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(
            model_name='models/gemini-2.0-flash', 
            system_instruction=system_instruction
        )
    except Exception as e:
        st.error(f"Gemini Initialization Failed: {e}")
        return None

def load_problems():
    """Calculus 문제 은행(JSON)을 로드합니다."""
    try:
        # 파일명을 교수님이 저장하신 이름으로 확인해 주세요.
        with open('calculus_problems.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Problem bank load error: {e}")
        return []

def check_numeric_match(user_val, correct_val, tolerance=0.05):
    """숫자를 추출하여 5% 오차 범위 내에 있는지 확인합니다."""
    try:
        u_match = re.search(r"[-+]?\d*\.\d+|\d+", str(user_val))
        if not u_match: return False
        u = float(u_match.group())
        c = float(correct_val)
        if c == 0: return abs(u) < tolerance
        return abs(u - c) <= abs(tolerance * c)
    except (ValueError, TypeError, AttributeError):
        return False

def evaluate_understanding_score(chat_history):
    """
    미분적분학 원리에 기반하여 학생의 이해도(0-10)를 평가합니다.
    """
    eval_instruction = (
        "You are a strict Engineering Professor at Texas A&M University - Corpus Christi. "
        "Evaluate the student's mastery of Calculus (0-10) based ONLY on the chat history.\n\n"
        "STRICT SCORING RUBRIC:\n"
        "0-3: Purely non-technical chat or complete misunderstanding of limits/derivatives.\n"
        "4-5: Good conceptual understanding but fails to state formal derivative or integral rules.\n"
        "6-8: Correctly identifies and uses LaTeX for calculus notations (e.g., $\\frac{dy}{dx}$, $\\int f(x)dx$, $\\nabla f$).\n"
        "9-10: Flawless logic. Correctly applies Chain Rule, Integration by Parts, or Partial Differentiation with perfect LaTeX.\n\n"
        "CRITICAL RULES:\n"
        "1. If the student does not use LaTeX for mathematical expressions, do NOT exceed 6.\n"
        "2. If the student fails to explain the logic (e.g., why L'Hopital's rule applies), penalize the score.\n"
        "3. Output ONLY the integer."
    )
    
    model = get_gemini_model(eval_instruction)
    if not model: return 0

    try:
        response = model.generate_content(f"Chat history to evaluate:\n{chat_history}")
        score_match = re.search(r"\d+", response.text)
        if score_match:
            score = int(score_match.group())
            return min(max(score, 0), 10)
        return 0
    except Exception:
        return 0

def analyze_and_send_report(user_name, topic_title, chat_history):
    """Calculus 세션을 분석하고 교수님께 리포트를 이메일로 발송합니다."""
    
    score = evaluate_understanding_score(chat_history)
    
    report_instruction = (
        "You are an academic evaluator analyzing a Calculus session for Dr. Dugan Um.\n"
        "Your report must include:\n"
        "1. Session Overview\n"
        f"2. Numerical Understanding Score: {score}/10\n"
        "3. Mathematical Rigor: Did the student use proper LaTeX for derivatives/integrals?\n"
        "4. Logic Analysis: Did the student correctly identify steps (e.g., $u$-substitution, partial derivative steps)?\n"
        "5. Engagement Level\n"
        "6. CRITICAL: Quote the section '--- STUDENT FEEDBACK ---' exactly."
    )
    
    model = get_gemini_model(report_instruction)
    if not model: return "AI Analysis Unavailable"

    prompt = (
        f"Student Name: {user_name}\n"
        f"Topic: {topic_title}\n"
        f"Assigned Score: {score}/10\n\n"
        f"DATA:\n{chat_history}\n\n"
        "Format for Dr. Dugan Um. Ensure all calculus notations in the report use LaTeX."
    )
    
    try:
        response = model.generate_content(prompt)
        report_text = response.text
    except Exception as e:
        report_text = f"Analysis failed: {str(e)}"

    # Email Logic
    sender = st.secrets["EMAIL_SENDER"]
    password = st.secrets["EMAIL_PASSWORD"] 
    receiver = "dugan.um@gmail.com" 

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = f"Calculus Tutor ({user_name}): {topic_title} [Score: {score}/10]"
    msg.attach(MIMEText(report_text, 'plain'))

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"SMTP Error: {e}")
    
    return report_text