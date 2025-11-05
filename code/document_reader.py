import fitz  # PyMuPDF
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

# ------------------ PDF Text Extraction ------------------
def extract_text_from_pdf(pdf_path):
    try:
        text = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
        return text.strip()
    except Exception:
        return ""

# ------------------ Text Summarization ------------------
def summarize_text(text, n=4):
    sentences = text.split(".")
    return ". ".join(sentences[:n]) + "."

# ------------------ Contract Type Detection ------------------
def detect_contract_type(text):
    text = text.lower()
    if "lease" in text:
        return "Lease Agreement"
    elif "employment" in text:
        return "Employment Contract"
    elif "partnership" in text:
        return "Partnership Agreement"
    elif "nda" in text or "confidentiality" in text:
        return "NDA Agreement"
    else:
        return "General Legal Document"

# ------------------ Clause Detection ------------------
def detect_clauses_with_excerpts(text):
    clauses = {
        "Confidentiality": "confidential",
        "Termination": "terminate",
        "Payment": "payment",
        "Liability": "liability",
        "Dispute Resolution": "dispute",
        "Governing Law": "law",
        "Indemnity": "indemnity",
        "Force Majeure": "force majeure"
    }
    found = {}
    lower_text = text.lower()

    for clause, keyword in clauses.items():
        match = re.search(rf".{{0,100}}{keyword}.{{0,100}}", lower_text)
        found[clause] = {
            "found": bool(match),
            "excerpt": match.group(0) if match else ""
        }
    return found

# ------------------ Risk Assessment ------------------
def assess_risk(clauses):
    total = len(clauses)
    found = sum(1 for c in clauses.values() if c["found"])
    ratio = found / total

    if ratio >= 0.75:
        return "Low", "Most key clauses are present. Document seems comprehensive."
    elif ratio >= 0.4:
        return "Medium", "Some clauses are missing. Review recommended."
    else:
        return "High", "Critical clauses missing. Document may be risky."

# ------------------ Compare Versions ------------------
def compare_versions(text1, text2):
    cv = CountVectorizer().fit_transform([text1, text2])
    sim = cosine_similarity(cv)[0, 1]
    return round(sim * 100, 2)
