# ============================================================
# AI Legal Document Analyzer - Streamlit Dashboard
# Developed by Jahnavi Kodavati & Swejan | CSE - AI | SSE Chennai
# Final Version - Functional Pages + OCR Support + Styled Clauses
# ============================================================

import streamlit as st
import json
import os
from pathlib import Path
import hashlib
from document_reader import (
    extract_text_from_pdf,
    summarize_text,
    detect_contract_type,
    detect_clauses_with_excerpts,
    assess_risk,
    compare_versions,
)
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

# ------------------ PATH SETUP ------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_RAW = BASE_DIR.parent / "data" / "raw documents"
DATA_REPORTS = BASE_DIR.parent / "data" / "reports"

for path in [DATA_RAW, DATA_REPORTS]:
    path.mkdir(parents=True, exist_ok=True)

USERS_FILE = BASE_DIR / "users.json"
HISTORY_FILE = BASE_DIR / "history.json"
LAST_USER_FILE = BASE_DIR / "last_user.json"

for f in [USERS_FILE, HISTORY_FILE, LAST_USER_FILE]:
    if not f.exists():
        f.write_text("{}")

# ------------------ PASSWORD UTILS ------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        USERS_FILE.write_text("{}")
        return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def verify_user(email, password):
    users = load_users()
    hashed = hash_password(password)
    return email in users and users[email] == hashed

def register_user(email, password):
    users = load_users()
    if email in users:
        return False
    users[email] = hash_password(password)
    save_users(users)
    return True

def remember_user(email):
    with open(LAST_USER_FILE, "w") as f:
        json.dump({"email": email}, f)

def get_remembered_user():
    try:
        with open(LAST_USER_FILE, "r") as f:
            data = json.load(f)
            return data.get("email")
    except:
        return None

def forget_user():
    if LAST_USER_FILE.exists():
        LAST_USER_FILE.write_text("{}")

# ------------------ OCR FUNCTION ------------------
def extract_text_with_ocr(pdf_path):
    text = ""
    try:
        pages = convert_from_path(pdf_path, dpi=300)
        for page in pages:
            text += pytesseract.image_to_string(page, lang="eng")
    except Exception as e:
        st.error(f"OCR failed: {e}")
    return text.strip()

# ------------------ LOGIN PAGE ------------------
def login_page():
    st.markdown(
        """
        <div class="login-card">
            <h2>🔐 AI Legal Document Analyzer</h2>
            <p>Login or Register to continue</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if verify_user(email, password):
                st.session_state["user"] = email
                remember_user(email)
                st.success(f"✅ Welcome back, {email}!")
                st.rerun()
            else:
                st.error("❌ Invalid credentials.")

    with tab2:
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_pass")
        if st.button("Register"):
            if register_user(email, password):
                st.success("✅ Account created successfully!")
                st.session_state["user"] = email
                remember_user(email)
                st.rerun()
            else:
                st.warning("⚠ Email already registered. Please login.")

# ------------------ SIDEBAR ------------------
def sidebar_nav():
    st.sidebar.markdown("<h2>⚖ Legal Analyzer Dashboard</h2>", unsafe_allow_html=True)
    menu = ["📄 Analyze Document", "🔍 Compare Documents", "📊 Reports", "⚠ Risk Analysis", "🚪 Logout"]
    choice = st.sidebar.radio("Navigate", menu, label_visibility="collapsed")
    st.sidebar.markdown("---")
    lang = st.sidebar.selectbox("🌐 Language", ["English", "Hindi", "Tamil", "Telugu"])
    st.session_state["language"] = lang
    return choice

# ------------------ SAVE HISTORY ------------------
def save_history(user, doc_type, risk, filename):
    try:
        history = json.loads(HISTORY_FILE.read_text())
    except json.JSONDecodeError:
        history = {}

    if user not in history:
        history[user] = []
    entry = {"file": filename, "type": doc_type, "risk": risk}
    if entry not in history[user]:
        history[user].append(entry)
    HISTORY_FILE.write_text(json.dumps(history, indent=2))

# ------------------ MAIN DASHBOARD ------------------
def main_dashboard():
    user = st.session_state["user"]
    choice = sidebar_nav()

    with open(BASE_DIR.parent / "styles.css") as css:
        st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)

    st.markdown("<h1 class='title'>AI Legal Document Analyzer</h1>", unsafe_allow_html=True)
    st.caption(f"Welcome, {user} | Smart Legal Insights in {st.session_state['language']}")

    if choice == "🚪 Logout":
        forget_user()
        del st.session_state["user"]
        st.success("✅ Logged out successfully!")
        st.rerun()

    elif choice == "📄 Analyze Document":
        uploaded_file = st.file_uploader("📂 Upload Legal Document (PDF)", type=["pdf"])
        manual_text = st.text_area("📝 Or Paste Document Text Here", height=150)

        if uploaded_file or manual_text.strip():
            if uploaded_file:
                file_path = DATA_RAW / uploaded_file.name
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                text = extract_text_from_pdf(str(file_path))
                if not text or len(text) < 20:
                    st.warning("⚠ Detected a scanned document. Applying OCR extraction...")
                    text = extract_text_with_ocr(str(file_path))
            else:
                text = manual_text

            if not text or len(text) < 20:
                st.error("❌ Could not extract readable text. Try uploading a clearer document.")
            else:
                st.success("✅ Document successfully processed!")
                doc_type = detect_contract_type(text)
                clauses = detect_clauses_with_excerpts(text)
                risk_level, risk_comment = assess_risk(clauses)
                summary = summarize_text(text, n=4)
                save_history(user, doc_type, risk_level, uploaded_file.name if uploaded_file else "Manual Text")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Words", len(text.split()))
                col2.metric("Characters", len(text))
                col3.metric("Sentences", text.count("."))
                col4.metric("Risk", risk_level)

                st.markdown("---")
                st.subheader("📘 Document Overview")
                st.write(f"Detected Type: {doc_type}")
                st.info(risk_comment)
                st.subheader("🧠 Summary")
                st.success(summary)

                # -------- Key Clauses --------
                st.subheader("📑 Key Clauses")
                for clause, info in clauses.items():
                    found = info["found"]
                    excerpt = info["excerpt"][:250] + "..." if info["excerpt"] else ""
                    color = "green" if found else "red"
                    status = "✅ Found" if found else "❌ Missing"
                    st.markdown(
                        f"""
                        <div style='background:#f9f9ff;padding:10px;border-left:5px solid {color};
                        border-radius:8px;margin-bottom:10px;'>
                            <b>{clause}</b> — <span style='color:{color};font-weight:bold'>{status}</span><br>
                            <small>{excerpt}</small>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    elif choice == "📊 Reports":
        st.subheader("📊 Document Analysis Reports")
        history = json.loads(HISTORY_FILE.read_text())
        user_history = history.get(user, [])
        if not user_history:
            st.info("No reports yet.")
        else:
            for item in user_history:
                st.markdown(f"📄 {item['file']} → Type: {item['type']} | Risk: {item['risk']}")

    elif choice == "⚠ Risk Analysis":
        st.subheader("⚠ Risk Level Overview")
        history = json.loads(HISTORY_FILE.read_text())
        user_history = history.get(user, [])
        if not user_history:
            st.info("No analyzed documents yet.")
        else:
            low = [d for d in user_history if d["risk"] == "Low"]
            med = [d for d in user_history if d["risk"] == "Medium"]
            high = [d for d in user_history if d["risk"] == "High"]
            st.write(f"🟢 Low: {len(low)} | 🟡 Medium: {len(med)} | 🔴 High: {len(high)}")

# ------------------ APP ENTRY ------------------
def main():
    st.set_page_config(page_title="AI Legal Document Analyzer", layout="wide")
    if "user" not in st.session_state:
        remembered = get_remembered_user()
        if remembered:
            st.session_state["user"] = remembered
    if "user" not in st.session_state:
        login_page()
    else:
        main_dashboard()

if __name__ == "__main__":
    main()
