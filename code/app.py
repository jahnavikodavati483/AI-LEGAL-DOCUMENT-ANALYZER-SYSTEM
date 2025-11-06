# ============================================================
# AI Legal Document Analyzer - Final Version (All features)
# Developed by Jahnavi Kodavati & Swejan | CSE - AI | SSE Chennai
# Features: OCR, Metrics, Reports, Risk Analysis, Comparison,
# Spinner, GitHub user persistence, Email alerts, Admin view
# Compatible with Streamlit 1.51.0
# ============================================================

import streamlit as st
import json
import os
import hashlib
import requests
import base64
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
from email.mime.text import MIMEText
import smtplib

# Import your document helpers (must exist in project)
from document_reader import (
    extract_text_from_pdf,
    summarize_text,
    detect_contract_type,
    detect_clauses_with_excerpts,
    assess_risk,
    compare_versions,
)

# ------------------ PATH SETUP ------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_RAW = BASE_DIR.parent / "data" / "raw documents"
DATA_REPORTS = BASE_DIR.parent / "data" / "reports"

for p in [DATA_RAW, DATA_REPORTS]:
    p.mkdir(parents=True, exist_ok=True)

USERS_FILE = BASE_DIR / "users.json"
HISTORY_FILE = BASE_DIR / "history.json"

for f in [USERS_FILE, HISTORY_FILE]:
    if not f.exists():
        f.write_text("{}")

# ------------------ SECRETS (optional) ------------------
GITHUB_TOKEN = None
GITHUB_USER = None
GITHUB_REPO = None
GITHUB_BRANCH = None
GITHUB_FILE_PATH = None

EMAIL_GMAIL = None
EMAIL_PASSWORD = None

try:
    if "github" in st.secrets:
        GITHUB_TOKEN = st.secrets["github"].get("TOKEN")
        GITHUB_USER = st.secrets["github"].get("USERNAME")
        GITHUB_REPO = st.secrets["github"].get("REPO")
        GITHUB_BRANCH = st.secrets["github"].get("BRANCH", "main")
        GITHUB_FILE_PATH = st.secrets["github"].get("FILE_PATH", "code/users.json")
    if "email" in st.secrets:
        EMAIL_GMAIL = st.secrets["email"].get("GMAIL")
        EMAIL_PASSWORD = st.secrets["email"].get("PASSWORD")
except Exception:
    pass

# ------------------ HELPERS: email alert ------------------
def send_login_alert_email(target_email, attempted_by=None):
    """Send alert email to target_email using secrets; returns True if sent"""
    if not EMAIL_GMAIL or not EMAIL_PASSWORD:
        print("Email secrets not configured; skipping alert.")
        return False
    try:
        subject = "⚠️ Alert: Unusual Login Attempt Detected"
        body = f"""Hello,

Someone tried to log in to your AI Legal Document Analyzer account ({target_email}).
If this was not you, please reset your password immediately using the Reset Password tab.

Attempted by: {attempted_by if attempted_by else 'Unknown'}

Stay secure,
AI Legal Document Analyzer
"""
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_GMAIL
        msg["To"] = target_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_GMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f"Alert email sent to {target_email}")
        return True
    except Exception as e:
        print(f"Failed to send alert email: {e}")
        return False

# ------------------ HELPERS: GitHub sync ------------------
def github_get_file_sha():
    if not (GITHUB_TOKEN and GITHUB_USER and GITHUB_REPO and GITHUB_FILE_PATH):
        return None
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json().get("sha")
    return None

def upload_to_github(file_path: Path, commit_msg="Update users.json"):
    if not (GITHUB_TOKEN and GITHUB_USER and GITHUB_REPO and GITHUB_FILE_PATH):
        print("GitHub secrets not configured; skipping upload.")
        return False
    try:
        b64 = base64.b64encode(file_path.read_bytes()).decode("utf-8")
        url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        sha = github_get_file_sha()
        payload = {"message": commit_msg, "content": b64, "branch": GITHUB_BRANCH}
        if sha:
            payload["sha"] = sha
        resp = requests.put(url, headers=headers, json=payload)
        if resp.status_code in (200, 201):
            print("Uploaded users.json to GitHub")
            return True
        else:
            print("GitHub upload failed:", resp.status_code, resp.text)
            return False
    except Exception as e:
        print("Exception uploading to GitHub:", e)
        return False

# ------------------ PASSWORD / USERS ------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    try:
        raw = USERS_FILE.read_text()
        users = json.loads(raw) if raw.strip() else {}
    except Exception:
        users = {}

    upgraded = False
    for email, data in list(users.items()):
        if isinstance(data, str):
            users[email] = {"password": data}
            upgraded = True

    owner_email = "jahnavikodavati483@gmail.com"
    if owner_email not in users:
        users[owner_email] = {"password": hash_password("admin123")}
        upgraded = True

    if upgraded:
        save_users(users, commit_msg="Upgrade users.json format")
    return users

def save_users(users: dict, commit_msg="Update users.json"):
    try:
        USERS_FILE.write_text(json.dumps(users, indent=2))
    except Exception as e:
        print("Failed to write local users.json:", e)
    upload_to_github(USERS_FILE, commit_msg=commit_msg)

def verify_user(email: str, password: str) -> bool:
    users = load_users()
    hashed = hash_password(password)
    return email in users and users[email].get("password") == hashed

def register_user(email: str, password: str) -> bool:
    users = load_users()
    if email in users:
        return False
    users[email] = {"password": hash_password(password)}
    save_users(users, commit_msg=f"Register user {email}")
    return True

def reset_password(email: str, new_password: str) -> bool:
    users = load_users()
    if email in users:
        users[email]["password"] = hash_password(new_password)
        save_users(users, commit_msg=f"Reset password for {email}")
        return True
    return False

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
            <p>Login, Register or Reset Password to continue</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Reset Password"])

    # LOGIN TAB
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            users = load_users()
            if verify_user(email, password):
                st.session_state["user"] = email
                st.success(f"✅ Welcome back, {email}!")
                st.rerun()
            else:
                # if email exists but password wrong -> send alert
                if email in users:
                    send_login_alert_email(email, attempted_by="Unknown")
                st.error("❌ Invalid credentials.")

    # REGISTER TAB
    with tab2:
        email = st.text_input("New Email", key="reg_email")
        password = st.text_input("New Password", type="password", key="reg_pass")
        if st.button("Register"):
            if register_user(email, password):
                st.success("✅ Account created successfully! Please login.")
            else:
                st.warning("⚠ Email already registered.")

    # RESET PASSWORD TAB
    with tab3:
        email = st.text_input("Your Registered Email", key="reset_email")
        new_pass = st.text_input("New Password", type="password", key="reset_pass")
        if st.button("Reset Password"):
            if reset_password(email, new_pass):
                st.success("✅ Password reset successfully! You can now login.")
            else:
                st.error("❌ Email not found. Please register first.")

# ------------------ SIDEBAR ------------------
def sidebar_nav():
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
            display: flex; align-items: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown("<h2 class='sidebar-title'>⚖ Legal Analyzer Dashboard</h2>", unsafe_allow_html=True)
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
    except Exception:
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

    st.markdown("<h1 class='title'>AI Legal Document Analyzer</h1>", unsafe_allow_html=True)
    st.caption(f"Welcome, {user} | Smart Legal Insights in {st.session_state['language']}")

    if choice == "🚪 Logout":
        del st.session_state["user"]
        st.success("✅ Logged out successfully!")
        st.rerun()

    elif choice == "📄 Analyze Document":
        uploaded_file = st.file_uploader("📂 Upload Legal Document (PDF)", type=["pdf"])
        manual_text = st.text_area("📝 Or Paste Document Text Here", height=150)

        if uploaded_file or manual_text.strip():
            with st.spinner("🔍 Analyzing document... Please wait..."):
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
                    # nothing further
                else:
                    st.success("✅ Document successfully processed!")
                    doc_type = detect_contract_type(text)
                    clauses = detect_clauses_with_excerpts(text)
                    risk_level, risk_comment = assess_risk(clauses)
                    summary = summarize_text(text, n=4)
                    save_history(user, doc_type, risk_level, uploaded_file.name if uploaded_file else "Manual Text")

            # ------- Metrics (blue cards row) -------
            try:
                words = len(text.split())
                chars = len(text)
                sentences = text.count(".")
            except Exception:
                words = chars = sentences = 0

            col1, col2, col3, col4 = st.columns(4)
            col1.markdown(f"<div style='background:#dbeafe;padding:12px;border-radius:10px;text-align:center;'><b>Words</b><br>{words}</div>", unsafe_allow_html=True)
            col2.markdown(f"<div style='background:#dbeafe;padding:12px;border-radius:10px;text-align:center;'><b>Characters</b><br>{chars}</div>", unsafe_allow_html=True)
            col3.markdown(f"<div style='background:#dbeafe;padding:12px;border-radius:10px;text-align:center;'><b>Sentences</b><br>{sentences}</div>", unsafe_allow_html=True)
            col4.markdown(f"<div style='background:#dbeafe;padding:12px;border-radius:10px;text-align:center;'><b>Risk</b><br>{risk_level}</div>", unsafe_allow_html=True)

            st.markdown("---")
            st.subheader("📘 Document Overview")
            st.write(f"Detected Type: **{doc_type}**")
            st.info(risk_comment)

            st.subheader("📑 Key Clauses Found")
            for clause, info in clauses.items():
                excerpt = info.get("excerpt", "")[:250] + "..." if info.get("excerpt") else ""
                status_icon = "✅" if info.get("found") else "❌"
                status_text = "Found" if info.get("found") else "Missing"
                st.markdown(
                    f"""
                    <div style='background:#eef2ff;padding:12px;border-radius:10px;margin:8px 0;
                    box-shadow:0 1px 3px rgba(0,0,0,0.1);'>
                        <div style='display:flex; justify-content:space-between; align-items:center;'>
                            <b>{clause}</b>
                            <span style='font-weight:600;color:#1e3a8a;'>{status_icon} {status_text}</span>
                        </div>
                        <br><small>{excerpt}</small>
                    </div>
                    """, unsafe_allow_html=True
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
            with st.spinner("🔍 Comparing documents... Please wait..."):
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
                    st.markdown(f"<div style='background:#eef2ff;padding:10px;border-radius:10px;margin:6px;'>{diff}</div>", unsafe_allow_html=True)

    elif choice == "📊 Reports":
        st.subheader("📊 Document Analysis Reports")

        # Admin view (owner only)
        if user == "jahnavikodavati483@gmail.com":
            st.markdown("### 👁 View All User Reports (Admin Access)")
            if st.button("Show All User Data"):
                try:
                    history_all = json.loads(HISTORY_FILE.read_text())
                except Exception:
                    history_all = {}
                if not history_all:
                    st.info("No user has uploaded any document yet.")
                else:
                    for usr, reports in history_all.items():
                        st.markdown(f"<div style='background:#dbeafe;padding:10px;border-radius:10px;margin:8px 0;'><b>👤 {usr}</b></div>", unsafe_allow_html=True)
                        for item in reports[::-1]:
                            st.markdown(
                                f"""
                                <div style='background:#eef2ff;padding:10px;border-radius:10px;margin:6px;
                                box-shadow:0 1px 3px rgba(0,0,0,0.1);'>
                                    <b>📄 {item['file']}</b><br>
                                    <span>📁 Type: <b>{item['type']}</b></span><br>
                                    <span>⚠ Risk Level: <b>{item['risk']}</b></span>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

        try:
            history = json.loads(HISTORY_FILE.read_text())
        except Exception:
            history = {}
        user_history = history.get(user, [])
        if not user_history:
            st.info("No reports yet.")
        else:
            for item in user_history[::-1]:
                st.markdown(
                    f"""
                    <div style='background:#eef2ff;padding:10px;border-radius:10px;margin:6px;
                    box-shadow:0 1px 3px rgba(0,0,0,0.1);'>
                        <b>📄 {item['file']}</b><br>
                        <span>📁 Type: <b>{item['type']}</b></span><br>
                        <span>⚠ Risk Level: <b>{item['risk']}</b></span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    elif choice == "⚠ Risk Analysis":
        st.subheader("⚠ Risk Level Overview")
        try:
            history = json.loads(HISTORY_FILE.read_text())
        except Exception:
            history = {}
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
                history[user] = []
                HISTORY_FILE.write_text(json.dumps(history, indent=2))
                st.success("✅ History cleared successfully!")
                st.rerun()

# ------------------ APP ENTRY ------------------
def main():
    st.set_page_config(page_title="AI Legal Document Analyzer", layout="wide")
    try:
        if "user" not in st.session_state:
            login_page()
        else:
            main_dashboard()
    except Exception as e:
        st.error("⚠️ App failed to load correctly. Please refresh or check logs.")
        st.code(str(e))

if __name__ == "__main__":
    main()
