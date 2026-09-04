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
    <div style="background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%); padding: 20px; border-radius: 12px; margin-bottom: 20px; border-left: 6px solid #38bdf8;">
        <h2 style="color: #ffffff; margin: 0; font-size: 22px;">Sinha AI Tech Solutions</h2>
        <p style="color: #94a3b8; margin: 6px 0 0 0; font-size: 13px;">Universal Document Digitization & Automated Audit Engine</p>
    </div>
""", unsafe_allow_html=True)

def preprocess_camera_image(pil_img):
    img = ImageOps.exif_transpose(pil_img).convert("RGB")
    cv_img = np.array(img)
    
    h, w = cv_img.shape[:2]
    if w > 1600:
        scaling = 1600.0 / w
        cv_img = cv2.resize(cv_img, (1600, int(h * scaling)), interpolation=cv2.INTER_AREA)
    elif w < 800:
        scaling = 1200.0 / w
        cv_img = cv2.resize(cv_img, (1200, int(h * scaling)), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    thresh = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 11)
    
    return thresh, gray

def extract_universal_data(uploaded_file):
    raw_pil = Image.open(uploaded_file)
    processed_bin, gray_img = preprocess_camera_image(raw_pil)
    
    # Fast, universal OCR without external language pack dependency
    raw_text = pytesseract.image_to_string(gray_img, config='--psm 6')
    if len(re.sub(r'[^A-Za-z0-9]', '', raw_text)) < 15:
        raw_text = pytesseract.image_to_string(processed_bin, config='--psm 3')

    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

    name = "Not Detected"
    father = "Not Detected"
    gov_id = "Not Detected"
    dob = "Not Detected"
    gender = "Not Detected"
    doc_type = "General Document"

    full_text_upper = raw_text.upper()

    # 1. Classify
    if "AADHAAR" in full_text_upper or "UNIQUE IDENTIFICATION" in full_text_upper or "GOVERNMENT OF INDIA" in full_text_upper:
        doc_type = "Aadhaar Card"
    elif "PERMANENT ACCOUNT" in full_text_upper or "INCOME TAX" in full_text_upper or re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", raw_text):
        doc_type = "PAN Card"
    elif "DRIVING" in full_text_upper or "TRANSPORT" in full_text_upper:
        doc_type = "Driving License"

    # 2. Aadhaar 12-digit format (XXXX XXXX XXXX)
    aadhaar_m = re.search(r"\b([2-9]\d{3}\s\d{4}\s\d{4})\b", raw_text)
    if aadhaar_m:
        gov_id = aadhaar_m.group(1)

    # 3. PAN pattern
    if gov_id == "Not Detected":
        pan_m = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", raw_text)
        if pan_m:
            gov_id = pan_m.group(1)

    # 4. DOB Detection
    dob_m = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", raw_text)
    if dob_m:
        dob = dob_m.group(1)

    # 5. Gender
    if re.search(r"\bMALE\b", raw_text, re.IGNORECASE):
        gender = "FEMALE" if re.search(r"\bFEMALE\b", raw_text, re.IGNORECASE) else "MALE"

    # 6. Aadhaar English Name (Row right before DOB)
    if doc_type == "Aadhaar Card":
        for i, line in enumerate(lines):
            if any(k in line.upper() for k in ["DOB", "YEAR OF BIRTH"]):
                if i >= 1:
                    cand = re.sub(r"[^A-Za-z\s]", "", lines[i-1]).strip()
                    if len(cand) > 3 and not any(w in cand.upper() for w in ["INDIA", "GOVERNMENT", "AADHAAR"]):
                        name = cand
                break

    # 7. Form Line Extraction fallback
    if name == "Not Detected":
        for line in lines:
            if re.search(r"(?:Candidate|Citizen|Name)\s*[:\-]", line, re.IGNORECASE):
                parts = re.split(r"[:\-]", line, maxsplit=1)
                if len(parts) > 1:
                    clean_val = re.sub(r"[^A-Za-z\s]", "", parts[1]).strip()
                    if len(clean_val) > 2 and "FATHER" not in clean_val.upper():
                        name = clean_val
                        break

    score = sum([
        1 if name != "Not Detected" else 0,
        1 if gov_id != "Not Detected" else 0,
        1 if dob != "Not Detected" else 0
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

st.subheader("📂 Upload Documents (Aadhaar / Scans / Certificates)")
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
        
