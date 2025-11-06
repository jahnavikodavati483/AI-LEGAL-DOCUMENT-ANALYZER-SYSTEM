# ============================================================
# AI Legal Document Analyzer - Final Cloud Version (with Owner Password Reset)
# Developed by Jahnavi Kodavati & Swejan | CSE-AI | SSE Chennai
# ============================================================

import streamlit as st
import json
import os
from pathlib import Path
import hashlib
from datetime import datetime
import pandas as pd
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import uuid
from document_reader import (
    extract_text_from_pdf,
    summarize_text,
    detect_contract_type,
    detect_clauses_with_excerpts,
    assess_risk,
    compare_versions,
)

# ------------------ PATHS ------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_RAW = BASE_DIR.parent / "data" / "raw documents"
for p in [DATA_RAW]: p.mkdir(parents=True, exist_ok=True)
USERS_FILE   = BASE_DIR / "users.json"
HISTORY_FILE = BASE_DIR / "history.json"
LAST_USER_FILE = BASE_DIR / "last_user.json"
ACTIVITY_FILE  = BASE_DIR / "login_activity.csv"
for f in [USERS_FILE,HISTORY_FILE,LAST_USER_FILE]:
    if not f.exists(): f.write_text("{}")

# ------------------ PASSWORD UTILS ------------------
def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()

def save_users(u):
    with open(USERS_FILE,"w") as f: json.dump(u,f,indent=2)

def load_users():
    try: users=json.load(open(USERS_FILE))
    except: users={}
    upgraded=False
    for e,d in list(users.items()):
        if isinstance(d,str):
            users[e]={"password":d,"role":"user"}; upgraded=True
    # ensure owner
    if "jahnavi.kodavati483@gmail.com" not in users:
        users["jahnavi.kodavati483@gmail.com"]={"password":hash_password("admin123"),"role":"owner"}; upgraded=True
    if upgraded: save_users(users)
    return users

def verify_user(e,p):
    u=load_users(); h=hash_password(p)
    return e in u and u[e]["password"]==h

def register_user(e,p):
    u=load_users()
    if e in u: return False
    u[e]={"password":hash_password(p),"role":"user"}; save_users(u); return True

def remember_user(e): json.dump({"email":e},open(LAST_USER_FILE,"w"))
def get_remembered_user():
    try: return json.load(open(LAST_USER_FILE)).get("email")
    except: return None
def forget_user(): LAST_USER_FILE.write_text("{}") if LAST_USER_FILE.exists() else None

def log_activity(mail,act):
    r=pd.DataFrame([[mail,act,datetime.now().strftime("%Y-%m-%d %H:%M:%S")]],columns=["User","Action","Time"])
    if ACTIVITY_FILE.exists(): r=pd.concat([pd.read_csv(ACTIVITY_FILE),r],ignore_index=True)
    r.to_csv(ACTIVITY_FILE,index=False)

# ------------------ OCR ------------------
def extract_text_with_ocr(path):
    text=""
    try:
        for pg in convert_from_path(path,dpi=300): text+=pytesseract.image_to_string(pg,lang="eng")
    except Exception as e: st.error(f"OCR failed: {e}")
    return text.strip()

# ------------------ LOGIN PAGE ------------------
def login_page():
    st.markdown("<h2 style='text-align:center;'>🔐 AI Legal Document Analyzer</h2>",unsafe_allow_html=True)
    tab1,tab2=st.tabs(["Login","Register"])
    users=load_users()

    # --- Login ---
    with tab1:
        email=st.text_input("Email",key="login_email")
        pw=st.text_input("Password",type="password",key="login_pw")
        c1,c2=st.columns(2)
        if c1.button("Login"):
            if verify_user(email,pw):
                st.session_state["user"]={"email":email,"role":users[email]["role"]}
                remember_user(email); log_activity(email,"Logged in"); st.success(f"Welcome {email}!"); st.rerun()
            else: st.error("Invalid credentials")

        # 🔄 Reset owner password
        with c2.popover("Forgot password (Owner only)"):
            new_pw=st.text_input("Enter new password",type="password")
            if st.button("Reset Owner Password"):
                if email=="jahnavi.kodavati483@gmail.com":
                    users["jahnavi.kodavati483@gmail.com"]["password"]=hash_password(new_pw)
                    save_users(users)
                    st.success("Owner password reset successfully!")
                else:
                    st.warning("Only owner can reset this way.")

    # --- Register ---
    with tab2:
        em=st.text_input("Email",key="reg_email")
        pw2=st.text_input("Password",type="password",key="reg_pw")
        if st.button("Register"):
            if register_user(em,pw2): st.success("Account created! Please login.")
            else: st.warning("Email already registered.")

# ------------------ SIDEBAR ------------------
def sidebar(role):
    st.sidebar.markdown("<h2 style='color:#1e3a8a;'>⚖ Dashboard</h2>",unsafe_allow_html=True)
    menu=["📄 Analyze Document","🔍 Compare Documents","📊 Reports","⚠ Risk Analysis"]
    if role=="owner": menu.append("👁️ User Activity")
    menu.append("🚪 Logout")
    return st.sidebar.radio("Menu",menu,label_visibility="collapsed")

# ------------------ HISTORY ------------------
def save_history(u,t,r,f):
    try: h=json.load(open(HISTORY_FILE))
    except: h={}
    h.setdefault(u,[]).append({"file":f,"type":t,"risk":r})
    json.dump(h,open(HISTORY_FILE,"w"),indent=2)

# ------------------ DASHBOARD ------------------
def main_dashboard():
    info=st.session_state["user"]; mail=info["email"]; role=info["role"]
    choice=sidebar(role)
    st.title("AI Legal Document Analyzer"); st.caption(f"Welcome {mail}")

    if choice=="🚪 Logout":
        log_activity(mail,"Logout"); forget_user(); st.session_state.clear(); st.rerun()

    elif choice=="👁️ User Activity" and role=="owner":
        if ACTIVITY_FILE.exists(): st.dataframe(pd.read_csv(ACTIVITY_FILE).sort_values("Time",ascending=False))
        else: st.info("No activity yet")

    elif choice=="📄 Analyze Document":
        up=st.file_uploader("Upload PDF",type=["pdf"])
        txt=st.text_area("Or Paste Text",height=150)
        if up or txt.strip():
            if up:
                path=DATA_RAW/up.name; open(path,"wb").write(up.getbuffer())
                log_activity(mail,f"Uploaded {up.name}")
                text=extract_text_from_pdf(str(path))
                if not text: text=extract_text_with_ocr(str(path))
            else: text=txt
            if len(text)<20: st.error("Not enough text"); return
            dtype=detect_contract_type(text); clauses=detect_clauses_with_excerpts(text)
            risk,comment=assess_risk(clauses); summary=summarize_text(text,n=4)
            save_history(mail,dtype,risk,up.name if up else "Manual")
            col1,col2,col3,col4=st.columns(4)
            col1.metric("Words",len(text.split())); col2.metric("Chars",len(text))
            col3.metric("Sentences",text.count(".")); col4.metric("Risk",risk)
            st.markdown("---"); st.subheader("📘 Overview")
            st.write(f"Type: **{dtype}**"); st.info(comment)
            st.subheader("📑 Clauses")
            for c,i in clauses.items():
                exc=(i["excerpt"][:250]+"...") if i["excerpt"] else ""
                st.markdown(f"<div style='background:#f8fafc;padding:10px;border-radius:10px;'>"
                            f"<b>{c}</b> {'✅' if i['found'] else '❌'}<br><small>{exc}</small></div>",unsafe_allow_html=True)
            st.subheader("🧠 Summary"); st.success(summary)

    elif choice=="🔍 Compare Documents":
        f1=st.file_uploader("First PDF",type=["pdf"],key="f1")
        f2=st.file_uploader("Second PDF",type=["pdf"],key="f2")
        if f1 and f2:
            p1,p2=DATA_RAW/f1.name,DATA_RAW/f2.name
            open(p1,"wb").write(f1.getbuffer()); open(p2,"wb").write(f2.getbuffer())
            diff=compare_versions(extract_text_from_pdf(str(p1)),extract_text_from_pdf(str(p2)))
            st.subheader("📄 Comparison Result")
            if not diff: st.info("No major differences.")
            else:
                for d in diff: st.markdown(f"<div style='background:#eef2ff;padding:10px;border-radius:10px;margin:4px;'>{d}</div>",unsafe_allow_html=True)

    elif choice=="📊 Reports":
        hist=json.load(open(HISTORY_FILE))
        uh=hist.get(mail,[])
        if not uh: st.info("No reports yet."); return
        for it in uh[::-1]:
            st.markdown(f"<div style='background:#f1f5f9;padding:10px;border-radius:10px;margin:4px;'>"
                        f"<b>{it['file']}</b><br>Type:{it['type']} | Risk:{it['risk']}</div>",unsafe_allow_html=True)

    elif choice=="⚠ Risk Analysis":
        hist=json.load(open(HISTORY_FILE))
        uh=hist.get(mail,[])
        if not uh: st.info("No docs yet."); return
        low=[d for d in uh if d["risk"]=="Low"]; med=[d for d in uh if d["risk"]=="Medium"]; hi=[d for d in uh if d["risk"]=="High"]
        for label,count,color in [("🟢 Low",len(low),"#e0e7ff"),("🟡 Medium",len(med),"#e0e7ff"),("🔴 High",len(hi),"#e0e7ff")]:
            st.markdown(f"<div style='background:{color};padding:10px;border-radius:10px;margin:6px;'>{label}: {count}</div>",unsafe_allow_html=True)
        if st.button("🗑 Clear History"):
            if st.confirm("Are you sure you want to clear all history?"):
                hist[mail]=[]; json.dump(hist,open(HISTORY_FILE,"w"),indent=2)
                st.success("History cleared!"); st.rerun()

# ------------------ APP ENTRY ------------------
def main():
    st.set_page_config(page_title="AI Legal Document Analyzer",layout="wide")
    forget_user()  # always force fresh login for everyone
    if "user" not in st.session_state: login_page()
    else: main_dashboard()

if __name__=="__main__": main()
