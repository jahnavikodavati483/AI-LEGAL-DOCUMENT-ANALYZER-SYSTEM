# ============================================================
# AI Legal Document Analyzer - Streamlit Dashboard
# Developed by Jahnavi Kodavati & Swejan | CSE - AI | SSE Chennai
# Final Version - Functional Pages + OCR Support + Styled Clauses
# (Updated: stable user persistence + robust JSON handling)
# ============================================================

import streamlit as st
import json
import os
import hashlib
from pathlib import Path

from legal_core import (
    extract_text_from_pdf,
    summarize_text,
    detect_contract_type,
    detect_clauses_with_excerpts,
    assess_risk,
    compare_versions,
)

# OCR dependencies (optional; may fail if poppler not installed)
try:
    from pdf2image import convert_from_path
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

# ------------------ PATH SETUP ------------------
# app.py lives in code/ — store persistent files (users/history) at repo root
BASE_DIR = Path(_file_).resolve().parent            # code/
REPO_ROOT = BASE_DIR.parent                           # project root
DATA_RAW = REPO_ROOT / "data" / "raw documents"
DATA_REPORTS = REPO_ROOT / "data" / "reports"
for path in [DATA_RAW, DATA_REPORTS]:
    path.mkdir(parents=True, exist_ok=True)

USERS_FILE = REPO_ROOT / "users.json"
HISTORY_FILE = REPO_ROOT / "history.json"

# ensure files exist
for _f in [USERS_FILE, HISTORY_FILE]:
    if not _f.exists():
        _f.write_text("{}")

# ------------------ UTIL: Safe JSON read/write ------------------
def safe_load_json(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        return json.loads(text)
    except (FileNotFoundError, json.JSONDecodeError):
        path.write_text("{}", encoding="utf-8")
        return {}

def safe_write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

# ------------------ PASSWORD / USER HELPERS ------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def load_users() -> dict:
    """Return dictionary of users. Each entry is { email: { 'password': <hash>, 'remember': bool } }.
       Also supports legacy simple mapping (email: hash) and converts it automatically.
    """
    raw = safe_load_json(USERS_FILE)
    # convert legacy format where value may be string hash
    converted = {}
    for email, val in raw.items():
        if isinstance(val, dict):
            pwd = val.get("password") or val.get("pwd") or ""
            remember = bool(val.get("remember", False))
            converted[email] = {"password": pwd, "remember": remember}
        else:
            # legacy: val is hash string
            converted[email] = {"password": str(val), "remember": False}
    return converted

def save_users(users: dict):
    safe_write_json(USERS_FILE, users)

def verify_user(email: str, password: str) -> bool:
    users = load_users()
    if email not in users:
        return False
    stored = users[email].get("password", "")
    return stored == hash_password(password)

def register_user(email: str, password: str) -> bool:
    users = load_users()
    if email in users:
        return False
    users[email] = {"password": hash_password(password), "remember": True}
    # unset remember flag for all other users (only one auto-remembered user)
    for e in users:
        if e != email:
            users[e]["remember"] = False
    save_users(users)
    return True

def remember_user(email: str):
    users = load_users()
    for e in users:
        users[e]["remember"] = (e == email)
    save_users(users)

def get_remembered_user():
    users = load_users()
    for email, info in users.items():
        try:
            if info.get("remember"):
                return email
        except Exception:
            continue
    return None

def forget_user(email: str):
    users = load_users()
    if email in users:
        users[email]["remember"] = False
        save_users(users)

# ------------------ OCR FUNCTION ------------------
def extract_text_with_ocr(pdf_path):
    """Attempt OCR if pdf2image + pytesseract available. Returns extracted string (may be empty)."""
    if not OCR_AVAILABLE:
        raise RuntimeError("OCR unavailable: pdf2image/pytesseract or poppler not installed.")
    text = ""
    try:
        pages = convert_from_path(pdf_path, dpi=300)
        for page in pages:
            text += pytesseract.image_to_string(page, lang="eng") + "\n"
    except Exception as e:
        # bubble exception up so caller can present appropriate message
        raise e
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

    # ---------- LOGIN ----------
    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if verify_user(email, password):
                # set session and remember this user for future auto-login
                st.session_state["user"] = email
                remember_user(email)
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid credentials. If you registered earlier, check spelling of email or password.")

    # ---------- REGISTER ----------
    with tab2:
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_pass")
        if st.button("Register"):
            if register_user(email, password):
                # auto-login after register
                st.session_state["user"] = email
                st.success("✅ Account created and remembered! You will be auto-logged in next time.")
                st.rerun()
            else:
                st.warning("⚠ Email already registered. Please use Login tab.")

# ------------------ SIDEBAR ------------------
def sidebar_nav():
    st.sidebar.markdown("<h2 class='sidebar-title'>⚖ Legal Analyzer Dashboard</h2>", unsafe_allow_html=True)
    menu = ["📄 Analyze Document", "🔍 Compare Documents", "📊 Reports", "⚠ Risk Analysis", "🚪 Logout"]
    choice = st.sidebar.radio("Navigate", menu, label_visibility="collapsed")

    st.sidebar.markdown("---")
    lang = st.sidebar.selectbox("🌐 Language", ["English", "Hindi", "Tamil", "Telugu"], key="lang_select")
    st.session_state["language"] = lang
    return choice

# ------------------ SAVE HISTORY ------------------
def save_history(user: str, doc_type: str, risk: str, filename: str):
    history = safe_load_json(HISTORY_FILE)
    if not isinstance(history, dict):
        history = {}
    if user not in history:
        history[user] = []
    entry = {"file": filename, "type": doc_type, "risk": risk}
    if entry not in history[user]:
        history[user].append(entry)
    safe_write_json(HISTORY_FILE, history)

# ------------------ MAIN DASHBOARD ------------------
def main_dashboard():
    user = st.session_state["user"]
    choice = sidebar_nav()

    # load styles if present
    css_path = BASE_DIR / "styles.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as css:
            st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)

    st.markdown("<h1 class='title'>AI Legal Document Analyzer</h1>", unsafe_allow_html=True)
    st.caption(f"Welcome, {user} | Smart Legal Insights in {st.session_state.get('language','English')}")

    # -------- Logout --------
    if choice == "🚪 Logout":
        # forget remember flag and clear session
        forget_user(user)
        if "user" in st.session_state:
            del st.session_state["user"]
        st.success("✅ Logged out. You won't be auto-logged in anymore.")
        st.rerun()

    # -------- Analyze Document --------
    elif choice == "📄 Analyze Document":
        uploaded_file = st.file_uploader("📂 Upload Legal Document (PDF)", type=["pdf"])
        manual_text = st.text_area("📝 Or Paste Document Text Here", height=150)

        if uploaded_file or manual_text.strip():
            if uploaded_file:
                file_path = DATA_RAW / uploaded_file.name
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                # try standard extraction first
                try:
                    text = extract_text_from_pdf(str(file_path))
                except Exception:
                    text = ""

                # If standard extraction fails or short, try OCR
                if not text or len(text) < 20:
                    st.info("⚠ Detected low-text/possibly scanned document. Attempting OCR...")
                    try:
                        text = extract_text_with_ocr(str(file_path))
                    except Exception as e:
                        # show helpful message about poppler / OCR availability
                        st.error(f"OCR failed: {e}. If you need OCR, install poppler and pytesseract.")
                        text = ""

            else:
                text = manual_text

            if not text or len(text) < 20:
                st.error("❌ Could not extract readable text. Try uploading a clearer document or paste text manually.")
            else:
                st.success("✅ Document successfully processed!")
                doc_type = detect_contract_type(text)
                clauses = detect_clauses_with_excerpts(text)
                risk_level, risk_comment = assess_risk(clauses)
                summary = summarize_text(text, n=4)

                save_history(user, doc_type, risk_level, uploaded_file.name if uploaded_file else "Manual Text")

                word_count = len(text.split())
                char_count = len(text)
                sentence_count = text.count(".")

                # display metrics in boxes (keeps your layout)
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Words", word_count)
                col2.metric("Characters", char_count)
                col3.metric("Sentences", sentence_count)
                col4.metric("Risk", risk_level)

                st.markdown("---")
                st.subheader("📘 Document Overview")
                st.write(f"Detected Type: {doc_type}")
                st.write(f"Risk Level: {risk_level}")
                st.info(risk_comment)
                st.subheader("🧠 Summary")
                st.success(summary)

                # -------- KEY CLAUSES (Styled Layout) --------
                st.subheader("📑 Key Clauses Found")
                st.markdown("""
                <style>
                .clause-box {
                    background-color: #f9f9ff;
                    border-left: 5px solid #919dee;
                    padding: 10px 15px;
                    border-radius: 8px;
                    margin-bottom: 10px;
                }
                .clause-title {
                    font-weight: 600;
                    color: #2b2b2b;
                }
                .clause-status {
                    float: right;
                    font-weight: bold;
                }
                .found { color: #008000; }
                .missing { color: #e63946; opacity: 0.95; }
                </style>
                """, unsafe_allow_html=True)

                # separate found and missing
                found_clauses = {k: v for k, v in clauses.items() if v.get("found")}
                missing_clauses = {k: v for k, v in clauses.items() if not v.get("found")}

                if found_clauses:
                    st.markdown("### ✅ Found Clauses")
                    for clause, info in found_clauses.items():
                        excerpt = (info.get("excerpt") or "")[:200] + "..." if info.get("excerpt") else ""
                        st.markdown(
                            f"""
                            <div class="clause-box">
                                <span class="clause-title">{clause}</span>
                                <span class="clause-status found">✅ Found</span><br>
                                <small>{excerpt}</small>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                if missing_clauses:
                    st.markdown("### ❌ Missing Clauses")
                    for clause, info in missing_clauses.items():
                        st.markdown(
                            f"""
                            <div class="clause-box">
                                <span class="clause-title">{clause}</span>
                                <span class="clause-status missing">❌ Missing</span><br>
                                <small>No relevant excerpt detected in the document.</small>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                st.subheader("📜 Extracted Text")
                st.text_area("Full Document Text", text[:4000] + "...", height=250)

    # -------- Compare Documents --------
    elif choice == "🔍 Compare Documents":
        col1, col2 = st.columns(2)
        file1 = col1.file_uploader("Upload First Document", type=["pdf"], key="cmp1")
        file2 = col2.file_uploader("Upload Second Document", type=["pdf"], key="cmp2")
        if file1 and file2:
            p1 = DATA_RAW / file1.name
            p2 = DATA_RAW / file2.name
            with open(p1, "wb") as f:
                f.write(file1.getbuffer())
            with open(p2, "wb") as f:
                f.write(file2.getbuffer())
            t1 = extract_text_from_pdf(str(p1))
            t2 = extract_text_from_pdf(str(p2))
            sim = compare_versions(t1, t2)
            st.metric("Similarity", f"{sim}%")
            if sim > 80:
                st.success("✅ Documents are very similar.")
            elif sim > 50:
                st.warning("⚠ Moderate differences found.")
            else:
                st.error("❌ Significant differences detected.")

    # -------- Reports --------
    elif choice == "📊 Reports":
        st.subheader("📊 Document Analysis Reports")
        history = safe_load_json(HISTORY_FILE)
        user_history = history.get(user, [])
        if not user_history:
            st.info("No reports available yet.")
        else:
            for item in user_history:
                st.markdown(f"📄 {item['file']} → Type: {item['type']} | Risk: {item['risk']}")

    # -------- Risk Analysis --------
    elif choice == "⚠ Risk Analysis":
        st.subheader("⚠ Risk Level Overview")
        history = safe_load_json(HISTORY_FILE)
        user_history = history.get(user, [])

        if not user_history:
            st.info("No analyzed documents yet.")
        else:
            low = [d for d in user_history if d["risk"] == "Low"]
            med = [d for d in user_history if d["risk"] == "Medium"]
            high = [d for d in user_history if d["risk"] == "High"]
            st.write(f"🟢 Low Risk: {len(low)} documents")
            st.write(f"🟡 Medium Risk: {len(med)} documents")
            st.write(f"🔴 High Risk: {len(high)} documents")

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑 Clear History"):
                history[user] = []
                safe_write_json(HISTORY_FILE, history)
                st.success("✅ History cleared successfully!")
                st.rerun()

# ------------------ APP ENTRY ------------------
def main():
    st.set_page_config(page_title="AI Legal Document Analyzer", layout="wide")

    # Auto-login last remembered user (if any)
    if "user" not in st.session_state:
        remembered = get_remembered_user()
        if remembered:
            st.session_state["user"] = remembered
            st.info(f"👋 Welcome back, {remembered}!")

    if "user" not in st.session_state:
        login_page()
    else:
        main_dashboard()

if _name_ == "_main_":
    main()
