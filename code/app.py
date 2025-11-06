# ============================================================
# AI Legal Document Analyzer - Final Cloud Version (Secure + Owner + Stable)
# Developed by Jahnavi Kodavati & Swejan | CSE - AI | SSE Chennai
# ============================================================

import streamlit as st
import json
import os
from pathlib import Path
import hashlib
from datetime import datetime
import pandas as pd
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
import uuid

# ------------------ PATH SETUP ------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_RAW = BASE_DIR.parent / "data" / "raw documents"
DATA_REPORTS = BASE_DIR.parent / "data" / "reports"

for path in [DATA_RAW, DATA_REPORTS]:
    path.mkdir(parents=True, exist_ok=True)

USERS_FILE = BASE_DIR / "users.json"
HISTORY_FILE = BASE_DIR / "history.json"
LAST_USER_FILE = BASE_DIR / "last_user.json"
ACTIVITY_FILE = BASE_DIR / "login_activity.csv"

for f in [USERS_FILE, HISTORY_FILE, LAST_USER_FILE]:
    if not f.exists():
        f.write_text("{}")

# ------------------ PASSWORD UTILS ------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users = {}

    # Upgrade old users
    upgraded = False
    for email, data in list(users.items()):
        if isinstance(data, str):
            users[email] = {"password": data, "role": "user"}
            upgraded = True

    # Ensure owner
    if "jahnavi.kodavati483@gmail.com" not in users:
        users["jahnavi.kodavati483@gmail.com"] = {
            "password": hash_password("admin123"),
            "role": "owner"
        }
        upgraded = True

    if upgraded:
        save_users(users)

    return users

def verify_user(email, password):
    users = load_users()
    hashed = hash_password(password)
    return email in users and users[email]["password"] == hashed

def register_user(email, password):
    users = load_users()
    if email in users:
        return False
    users[email] = {"password": hash_password(password), "role": "user"}
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

# ------------------ ACTIVITY TRACKING ------------------
def log_activity(email, action):
    record = pd.DataFrame([[email, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]],
                          columns=["User", "Action", "Time"])
    if ACTIVITY_FILE.exists():
        old = pd.read_csv(ACTIVITY_FILE)
        record = pd.concat([old, record], ignore_index=True)
    record.to_csv(ACTIVITY_FILE, index=False)

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
                users = load_users()
                st.session_state["user"] = {"email": email, "role": users[email]["role"]}
                remember_user(email)
                log_activity(email, "Logged in")
                st.success(f"✅ Welcome back, {email}!")
                st.rerun()
            else:
                st.error("❌ Invalid credentials.")

    with tab2:
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_pass")
        if st.button("Register"):
            if register_user(email, password):
                st.success("✅ Account created successfully! Please login.")
            else:
                st.warning("⚠ Email already registered. Please login.")

# ------------------ SIDEBAR ------------------
def sidebar_nav(role):
    st.sidebar.markdown(
        """
        <style>
        [data-testid="stSidebar"] { background-color: #e3e8ff; }
        .sidebar-title { font-weight: 700; color: #1e3a8a; margin-bottom: 18px; }
        div[role="radiogroup"] > label {
            margin-bottom: 12px !important;
            padding: 8px 12px !important;
            border-radius: 10px !important;
            background: white !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            display: flex;
            align-items: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("<h2 class='sidebar-title'>⚖ Legal Analyzer Dashboard</h2>", unsafe_allow_html=True)
    menu = ["📄 Analyze Document", "🔍 Compare Documents", "📊 Reports", "⚠ Risk Analysis"]
    if role == "owner":
        menu.append("👁️ User Activity")
    menu.append("🚪 Logout")
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
    user_info = st.session_state["user"]
    user = user_info["email"]
    role = user_info["role"]
    choice = sidebar_nav(role)

    with open(BASE_DIR.parent / "styles.css") as css:
        st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)

    st.markdown("<h1 class='title'>AI Legal Document Analyzer</h1>", unsafe_allow_html=True)
    st.caption(f"Welcome, {user} | Smart Legal Insights in {st.session_state['language']}")

    if choice == "🚪 Logout":
        log_activity(user, "Logged out")
        forget_user()
        st.session_state.clear()
        st.success("✅ Logged out successfully!")
        st.rerun()

    elif choice == "👁️ User Activity" and role == "owner":
        st.subheader("👁️ User Login & Activity Log")
        if ACTIVITY_FILE.exists():
            df = pd.read_csv(ACTIVITY_FILE)
            st.dataframe(df.sort_values("Time", ascending=False), use_container_width=True)
        else:
            st.info("No user activity recorded yet.")

    elif choice == "📄 Analyze Document":
        uploaded_file = st.file_uploader("📂 Upload Legal Document (PDF)", type=["pdf"])
        manual_text = st.text_area("📝 Or Paste Document Text Here", height=150)
        if uploaded_file or manual_text.strip():
            if uploaded_file:
                user_folder = DATA_RAW / user.replace("@", "_")
                user_folder.mkdir(exist_ok=True, parents=True)
                file_path = user_folder / uploaded_file.name
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                log_activity(user, f"Uploaded file: {uploaded_file.name}")
                text = extract_text_from_pdf(str(file_path))
                if not text or len(text) < 20:
                    st.warning("⚠ Detected a scanned document. Applying OCR extraction...")
                    text = extract_text_with_ocr(str(file_path))
            else:
                text = manual_text
                log_activity(user, "Analyzed manual text")

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
                st.write(f"Detected Type: **{doc_type}**")
                st.info(risk_comment)

                st.subheader("📑 Key Clauses Found")
                for clause, info in clauses.items():
                    excerpt = info["excerpt"][:250] + "..." if info["excerpt"] else ""
                    status_icon = "✅" if info["found"] else "❌"
                    status_text = "Found" if info["found"] else "Missing"
                    st.markdown(
                        f"<div class='clause-card' style='position:relative;'>"
                        f"<b>{clause}</b>"
                        f"<span style='position:absolute; right:15px; top:15px; font-weight:600; color:#1e3a8a;'>"
                        f"{status_icon} {status_text}</span><br><small>{excerpt}</small></div>",
                        unsafe_allow_html=True,
                    )

                st.subheader("🧠 Summary")
                st.success(summary)
                st.subheader("📜 Extracted Text")
                st.text_area("Full Document Text", text[:10000] + "...", height=250)

    elif choice == "🔍 Compare Documents":
        st.subheader("🔍 Compare Two Legal Documents")
        file1 = st.file_uploader("Upload First Document", type=["pdf"], key="file1")
        file2 = st.file_uploader("Upload Second Document", type=["pdf"], key="file2")
        if file1 and file2:
            path1 = DATA_RAW / file1.name
            path2 = DATA_RAW / file2.name
            with open(path1, "wb") as f:
                f.write(file1.getbuffer())
            with open(path2, "wb") as f:
                f.write(file2.getbuffer())
            text1 = extract_text_from_pdf(str(path1))
            text2 = extract_text_from_pdf(str(path2))
            differences = compare_versions(text1, text2)

            st.markdown("### 📄 Comparison Result")
            if not differences:
                st.info("No major differences found.")
            else:
                for diff in differences:
                    st.markdown(f"<div class='report-card'>{diff}</div>", unsafe_allow_html=True)

    elif choice == "📊 Reports":
        st.subheader("📊 Document Analysis Reports")
        history = json.loads(HISTORY_FILE.read_text())
        user_history = history.get(user, [])
        if not user_history:
            st.info("No reports yet.")
        else:
            for item in user_history[::-1]:
                st.markdown(
                    f"<div class='report-card'><b>📄 {item['file']}</b><br>"
                    f"<span>📁 Type: <b>{item['type']}</b></span><br>"
                    f"<span>⚠ Risk Level: <b>{item['risk']}</b></span></div>",
                    unsafe_allow_html=True,
                )

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

            st.markdown("<div style='background:#e0e7ff;padding:10px;border-radius:10px;margin-bottom:8px;'>🟢 Low Risk: "
                        f"{len(low)} document(s)</div>", unsafe_allow_html=True)
            st.markdown("<div style='background:#e0e7ff;padding:10px;border-radius:10px;margin-bottom:8px;'>🟡 Medium Risk: "
                        f"{len(med)} document(s)</div>", unsafe_allow_html=True)
            st.markdown("<div style='background:#e0e7ff;padding:10px;border-radius:10px;margin-bottom:8px;'>🔴 High Risk: "
                        f"{len(high)} document(s)</div>", unsafe_allow_html=True)

            if st.button("🗑 Clear History"):
                if st.confirm("Are you sure you want to clear all history?"):
                    history[user] = []
                    HISTORY_FILE.write_text(json.dumps(history, indent=2))
                    log_activity(user, "Cleared history")
                    st.success("✅ History cleared successfully!")
                    st.rerun()

# ------------------ APP ENTRY ------------------
def main():
    st.set_page_config(page_title="AI Legal Document Analyzer", layout="wide")

    # Always force login for new visitors (no shared session)
    forget_user()
    st.session_state.clear()

    if "user" not in st.session_state:
        login_page()
    else:
        main_dashboard()

if __name__ == "__main__":
    main()
