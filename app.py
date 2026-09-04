import streamlit as st
import os
import re
import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageOps
import pandas as pd
from datetime import datetime
import io

st.set_page_config(
    page_title="Sinha AI Tech Solutions",
    page_icon="⚡",
    layout="wide"
)

st.markdown("""
    <div style="background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%); padding: 18px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #38bdf8;">
        <h2 style="color: #ffffff; margin: 0; font-size: 20px;">Sinha AI Tech Solutions</h2>
        <p style="color: #94a3b8; margin: 4px 0 0 0; font-size: 13px;">Universal Multi-Document Digitization & Contractor Audit Portal</p>
    </div>
""", unsafe_allow_html=True)

def preprocess_card(pil_img):
    img = ImageOps.exif_transpose(pil_img).convert("RGB")
    cv_img = np.array(img)
    
    # Scale appropriately for OCR
    h, w = cv_img.shape[:2]
    if w > 1800:
        scaling = 1800.0 / w
        cv_img = cv2.resize(cv_img, (1800, int(h * scaling)), interpolation=cv2.INTER_AREA)
    elif w < 1000:
        scaling = 1400.0 / w
        cv_img = cv2.resize(cv_img, (1400, int(h * scaling)), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)
    
    # Denoise while keeping character edges sharp
    denoised = cv2.bilateralFilter(gray, 9, 75, 75)
    
    # Contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    
    # Adaptive threshold
    thresh = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 23, 11)
    
    return enhanced, thresh

def clean_name_string(txt):
    if not txt:
        return ""
    # Remove junk characters, keep clean English uppercase words
    cleaned = re.sub(r"[^A-Za-z\s]", " ", txt)
    words = [w.strip() for w in cleaned.split() if len(w.strip()) >= 2]
    # Filter out system and government labels
    blocklist = ["NAME", "FATHER", "INCOME", "TAX", "GOVT", "INDIA", "DEPARTMENT", "PERMANENT", "ACCOUNT", "NUMBER", "CARD", "SIGNATURE", "DATE", "BIRTH", "MERA", "AADHAAR", "PEHCHAN", "GOVERNMENT", "CITIZENSHIP", "PROOF", "IDENTITY", "UNION", "AUTHORITY"]
    valid_words = [w for w in words if w.upper() not in blocklist]
    return " ".join(valid_words).strip()

def extract_universal_data(uploaded_file):
    raw_pil = Image.open(uploaded_file)
    enhanced_gray, thresh = preprocess_card(raw_pil)
    
    # Multi-pass text extraction
    raw_text_gray = pytesseract.image_to_string(enhanced_gray, config='--psm 6')
    raw_text_thresh = pytesseract.image_to_string(thresh, config='--psm 6')
    
    # Combined line stream
    combined_text = raw_text_gray + "\n" + raw_text_thresh
    all_lines = [l.strip() for l in combined_text.split("\n") if l.strip()]

    name = "Not Detected"
    father = "Not Detected"
    gov_id = "Not Detected"
    dob = "Not Detected"
    gender = "Not Detected"
    doc_type = "General Document"

    full_upper = combined_text.upper()

    # Document Classification
    if "PERMANENT ACCOUNT" in full_upper or "INCOME TAX" in full_upper or re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", combined_text):
        doc_type = "PAN Card"
    elif "AADHAAR" in full_upper or "UNIQUE IDENTIFICATION" in full_upper or "MERA AADHAAR" in full_upper:
        doc_type = "Aadhaar Card"
    elif "DRIVING" in full_upper or "TRANSPORT" in full_upper:
        doc_type = "Driving License"

    # ID Parsing (PAN format: 5 letters + 4 digits + 1 letter)
    pan_m = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", combined_text)
    if pan_m:
        gov_id = pan_m.group(1)
        if doc_type == "General Document":
            doc_type = "PAN Card"

    # Aadhaar number (12 digits)
    if gov_id == "Not Detected":
        aadhaar_m = re.search(r"\b([2-9]\d{3}\s\d{4}\s\d{4})\b", combined_text)
        if aadhaar_m:
            gov_id = aadhaar_m.group(1)
            doc_type = "Aadhaar Card"

    # Fallback general ID
    if gov_id == "Not Detected":
        gen_m = re.search(r"(?:ID|No|Roll|Reg)[:\-\s]*([A-Za-z0-9\-/]{6,20})", combined_text, re.IGNORECASE)
        if gen_m:
            gov_id = gen_m.group(1).strip()

    # DOB Parsing
    dob_m = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", combined_text)
    if dob_m:
        dob = dob_m.group(1)

    # Gender Parsing
    if re.search(r"\b(MALE|FEMALE)\b", combined_text, re.IGNORECASE):
        gender = "FEMALE" if re.search(r"\bFEMALE\b", combined_text, re.IGNORECASE) else "MALE"

    # Target Field Extraction by Document Type
    if doc_type == "PAN Card":
        # Scanning for lines following Name and Father labels
        for idx, line in enumerate(all_lines):
            l_up = line.upper()
            
            # Check for Name label
            if "NAME" in l_up and not any(k in l_up for k in ["FATHER", "CARD", "ACCOUNT", "DEPARTMENT"]):
                for forward in range(1, 3):
                    if idx + forward < len(all_lines):
                        candidate = clean_name_string(all_lines[idx + forward])
                        if len(candidate.split()) >= 2 and name == "Not Detected":
                            name = candidate
                            break

            # Check for Father Name label
            if "FATHER" in l_up:
                for forward in range(1, 3):
                    if idx + forward < len(all_lines):
                        candidate = clean_name_string(all_lines[idx + forward])
                        if len(candidate.split()) >= 2 and father == "Not Detected":
                            father = candidate
                            break

        # Fallback: scan for any pure 2-3 word uppercase candidate lines
        if name == "Not Detected" or father == "Not Detected":
            clean_candidates = []
            for line in all_lines:
                cand = clean_name_string(line)
                words = cand.split()
                if 2 <= len(words) <= 3 and all(w.isupper() for w in words):
                    if cand not in clean_candidates:
                        clean_candidates.append(cand)
            if name == "Not Detected" and len(clean_candidates) >= 1:
                name = clean_candidates[0]
            if father == "Not Detected" and len(clean_candidates) >= 2:
                father = clean_candidates[1]

    elif doc_type == "Aadhaar Card":
        # On Aadhaar, the English name appears immediately above the DOB line
        for idx, line in enumerate(all_lines):
            if any(k in line.upper() for k in ["DOB", "YEAR OF BIRTH"]):
                for back in range(1, 3):
                    if idx - back >= 0:
                        cand = clean_name_string(all_lines[idx - back])
                        words = cand.split()
                        if len(words) >= 2:
                            name = cand
                            break
                break

    # General fallback for any labeled application forms
    if name == "Not Detected":
        for line in all_lines:
            if re.search(r"(?:Candidate|Citizen|Applicant|Name)\s*[:\-]", line, re.IGNORECASE):
                parts = re.split(r"[:\-]", line, maxsplit=1)
                if len(parts) > 1:
                    cand = clean_name_string(parts[1])
                    if len(cand.split()) >= 2:
                        name = cand
                        break

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
        "Audit Status": status
    }

st.subheader("📂 Upload Documents (Aadhaar / PAN / Official Forms)")
uploaded_files = st.file_uploader(
    "Select Documents (JPG, PNG)",
    type=["jpg", "png", "jpeg"],
    accept_multiple_files=True
)

if uploaded_files:
    st.info(f"Queued {len(uploaded_files)} document(s) for extraction.")
    if st.button("🚀 Run Universal Digitization", type="primary"):
        progress_bar = st.progress(0)
        extracted_rows = []
        
        for i, file_obj in enumerate(uploaded_files):
            data_row = extract_universal_data(file_obj)
            extracted_rows.append(data_row)
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        st.success("Pipeline Execution Complete!")
        df = pd.DataFrame(extracted_rows)
        st.dataframe(df, use_container_width=True)
        
        output_buffer = io.BytesIO()
        df.to_excel(output_buffer, index=False, engine="openpyxl")
        
        time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="📥 Download Contractor Deliverable (Excel)",
            data=output_buffer.getvalue(),
            file_name=f"Sinha_AI_Extract_{time_stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
                                                 
