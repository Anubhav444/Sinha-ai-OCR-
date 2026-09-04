import streamlit as st
import os
import re
import cv2
import numpy as np
import pytesseract
from PIL import Image
import pandas as pd
from datetime import datetime
import io

st.set_page_config(
    page_title="Sinha AI Tech Solutions - Universal Document Engine",
    page_icon="⚡",
    layout="wide"
)

st.markdown("""
    <div style="background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%); padding: 22px; border-radius: 12px; margin-bottom: 22px; border-left: 6px solid #38bdf8;">
        <h2 style="color: #ffffff; margin: 0; font-size: 22px;">Sinha AI Tech Solutions</h2>
        <p style="color: #94a3b8; margin: 6px 0 0 0; font-size: 13px;">Universal Document Digitization, Automated Audit & Excel Extraction Engine</p>
    </div>
""", unsafe_allow_html=True)

def clean_text_field(txt):
    if not txt:
        return ""
    # Strip garbage punctuation, keep alphanumeric and clean spacing
    cleaned = re.sub(r"^[^\w]+|[^\w]+$", "", txt.strip())
    return cleaned

def extract_universal_data(uploaded_file):
    image = Image.open(uploaded_file).convert("RGB")
    open_cv_image = np.array(image)
    
    # Adaptive image enhancement
    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    
    # Run OCR (Both PSM 6 and general text extraction fallback)
    raw_text = pytesseract.image_to_string(thresh, config='--psm 6 -l eng')
    if len(raw_text.strip()) < 15:
        raw_text = pytesseract.image_to_string(thresh, config='--psm 3 -l eng')

    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

    name = "Not Detected"
    father = "Not Detected"
    gov_id = "Not Detected"
    dob = "Not Detected"
    gender = "Not Detected"
    doc_type = "General Document"

    # Detect Document Family
    full_text_upper = raw_text.upper()
    if "AADHAAR" in full_text_upper or "UNIQUE IDENTIFICATION" in full_text_upper:
        doc_type = "Aadhaar Card / UIDAI"
    elif "INCOME TAX" in full_text_upper or "PERMANENT ACCOUNT" in full_text_upper:
        doc_type = "PAN Card"
    elif "DRIVING LICENCE" in full_text_upper or "TRANSPORT" in full_text_upper:
        doc_type = "Driving License"
    elif "BOARD" in full_text_upper or "EDUCATION" in full_text_upper or "ENROLLMENT" in full_text_upper:
        doc_type = "Academic / Enrollment Slip"
    elif "ELECTION" in full_text_upper or "VOTER" in full_text_upper:
        doc_type = "Voter ID"

    # Line-by-Line Attribute Parsing
    for line in lines:
        # Candidate / Citizen Name
        if re.search(r"(?:Candidate|Citizen|Student|Applicant)?\s*Name\s*[:\-]", line, re.IGNORECASE):
            parts = re.split(r"[:\-]", line, maxsplit=1)
            if len(parts) > 1:
                val = re.sub(r"[^A-Za-z\s]", "", parts[1]).strip()
                if len(val) > 2 and "FATHER" not in val.upper():
                    name = val

        # Father / Guardian / Husband Name
        if re.search(r"(?:Father|Guardian|Spouse|Husband|S/o|D/o|W/o)\s*(?:Name)?\s*[:\-]", line, re.IGNORECASE):
            parts = re.split(r"[:\-]", line, maxsplit=1)
            if len(parts) > 1:
                val = re.sub(r"[^A-Za-z\s]", "", parts[1]).strip()
                if len(val) > 2:
                    father = val

        # Labeled ID / Registration / Roll No
        if re.search(r"(?:Registration|Enrollment|Roll|Certificate|Licence|Card|ID)\s*(?:No|Number)?\s*[:\-]", line, re.IGNORECASE):
            parts = re.split(r"[:\-]", line, maxsplit=1)
            if len(parts) > 1:
                val = re.sub(r"[^A-Za-z0-9\-/]", "", parts[1]).strip()
                if len(val) >= 4:
                    gov_id = val

    # Universal Regex Fallbacks across full document text
    # 1. DOB / Date Extraction (DD/MM/YYYY or DD-MM-YYYY)
    dob_match = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", raw_text)
    if dob_match:
        dob = dob_match.group(1)

    # 2. Gender Detection
    gen_match = re.search(r"\b(MALE|FEMALE|TRANSGENDER)\b", raw_text, re.IGNORECASE)
    if gen_match:
        gender = gen_match.group(1).upper()

    # 3. Aadhaar Number pattern (12 digits formatted as XXXX XXXX XXXX)
    if gov_id == "Not Detected":
        aadhaar_match = re.search(r"\b(\d{4}\s\d{4}\s\d{4})\b", raw_text)
        if aadhaar_match:
            gov_id = aadhaar_match.group(1)

    # 4. PAN Card Pattern (5 letters + 4 digits + 1 letter)
    if gov_id == "Not Detected":
        pan_match = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", raw_text)
        if pan_match:
            gov_id = pan_match.group(1)

    # 5. General ID Number fallback (Alphanumeric with dashes/slashes, 6-20 chars)
    if gov_id == "Not Detected":
        id_fallback = re.search(r"\b([A-Z]{2,4}[-/\s]?[0-9]{4,12}[A-Z0-9\-/]*)\b", raw_text)
        if id_fallback and len(id_fallback.group(1).replace(" ", "")) >= 6:
            gov_id = id_fallback.group(1).strip()

    # Fallback Candidate Name if unlabeled (Takes first clean capitalized multi-word name)
    if name == "Not Detected":
        for l in lines:
            words = l.strip().split()
            if 2 <= len(words) <= 4:
                clean_candidate = " ".join([w for w in words if w.isalpha() and w.isupper()])
                if len(clean_candidate.split()) >= 2 and not any(k in clean_candidate for k in ["GOVERNMENT", "DEPARTMENT", "STATE", "EDUCATION", "INDIA", "RECORD", "APPLICATION"]):
                    name = clean_candidate
                    break

    # Dynamic Verification Logic:
    # If Document yields at least 2 primary verified data points, it qualifies as Verified.
    score = sum([
        1 if name != "Not Detected" else 0,
        1 if gov_id != "Not Detected" else 0,
        1 if dob != "Not Detected" else 0,
        1 if father != "Not Detected" else 0
    ])

    status = "Verified" if score >= 2 else "Needs Review"

    return {
        "File Name": uploaded_file.name,
        "Document Type": doc_type,
        "Candidate / Citizen Name": name,
        "Father / Guardian Name": father,
        "ID / Registration / Roll No": gov_id,
        "DOB": dob,
        "Gender": gender,
        "Audit Status": status,
        "Full Scanned Text (Audit Trail)": " ".join(lines[:6]) # First few lines preview
    }

st.subheader("📂 Upload Any Document / Multi-Format Batch")
uploaded_files = st.file_uploader(
    "Upload Scans (Aadhaar, Forms, Licenses, Marksheets, Certificates)",
    type=["jpg", "png", "jpeg"],
    accept_multiple_files=True
)

if uploaded_files:
    st.info(f"Queued {len(uploaded_files)} document(s) for extraction.")
    if st.button("🚀 Run Universal Digitization", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        extracted_rows = []
        for i, file_obj in enumerate(uploaded_files):
            status_text.text(f"Extracting ({i+1}/{len(uploaded_files)}): {file_obj.name}")
            data_row = extract_universal_data(file_obj)
            extracted_rows.append(data_row)
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        status_text.success("Extraction & Audit Pipeline Complete!")
        df = pd.DataFrame(extracted_rows)
        
        st.subheader("📊 Extracted Multi-Format Master Table")
        st.dataframe(df, use_container_width=True)
        
        # Build Downloadable Excel
        output_buffer = io.BytesIO()
        df.to_excel(output_buffer, index=False, engine="openpyxl")
        
        time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="📥 Download Contractor Deliverable (Excel)",
            data=output_buffer.getvalue(),
            file_name=f"Sinha_AI_Universal_Extract_{time_stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
