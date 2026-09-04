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
    page_title="Sinha AI Tech Solutions - Universal Engine",
    page_icon="⚡",
    layout="wide"
)

st.markdown("""
    <div style="background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%); padding: 22px; border-radius: 12px; margin-bottom: 22px; border-left: 6px solid #38bdf8;">
        <h2 style="color: #ffffff; margin: 0; font-size: 22px;">Sinha AI Tech Solutions</h2>
        <p style="color: #94a3b8; margin: 6px 0 0 0; font-size: 13px;">Enterprise Universal Document Digitization & Automated Extraction Pipeline</p>
    </div>
""", unsafe_allow_html=True)

def preprocess_camera_image(pil_img):
    # Auto-orient based on EXIF camera metadata
    img = ImageOps.exif_transpose(pil_img).convert("RGB")
    cv_img = np.array(img)
    
    # Resize camera captures to optimal OCR resolution (Max width 1800px)
    h, w = cv_img.shape[:2]
    if w > 1800:
        scaling = 1800.0 / w
        cv_img = cv2.resize(cv_img, (1800, int(h * scaling)), interpolation=cv2.INTER_AREA)
    elif w < 900:
        scaling = 1200.0 / w
        cv_img = cv2.resize(cv_img, (1200, int(h * scaling)), interpolation=cv2.INTER_CUBIC)

    # Grayscale
    gray = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)
    
    # Contrast Enhancement (CLAHE) - tackles shadows and dark camera scans
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # Adaptive thresholding handles camera lighting variations
    thresh = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 11
    )
    return thresh, gray

def extract_universal_data(uploaded_file):
    raw_pil = Image.open(uploaded_file)
    processed_bin, gray_img = preprocess_camera_image(raw_pil)
    
    # Try reading processed binary; fallback to gray image if text is thin
    raw_text = pytesseract.image_to_string(processed_bin, config='--psm 6 -l eng')
    if len(re.sub(r'[^A-Za-z0-9]', '', raw_text)) < 20:
        raw_text = pytesseract.image_to_string(gray_img, config='--psm 4 -l eng')

    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

    name = "Not Detected"
    father = "Not Detected"
    gov_id = "Not Detected"
    dob = "Not Detected"
    gender = "Not Detected"
    doc_type = "General Document"

    full_text_upper = raw_text.upper()

    # Document Classification
    if "PERMANENT ACCOUNT NUMBER" in full_text_upper or "INCOME TAX" in full_text_upper or re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", raw_text):
        doc_type = "PAN Card"
    elif "AADHAAR" in full_text_upper or "UNIQUE IDENTIFICATION" in full_text_upper or "GOVERNMENT OF INDIA" in full_text_upper:
        doc_type = "Aadhaar Card"
    elif "DRIVING LICENCE" in full_text_upper or "TRANSPORT" in full_text_upper:
        doc_type = "Driving License"
    elif "BOARD" in full_text_upper or "EDUCATION" in full_text_upper:
        doc_type = "Educational Certificate"

    # Labeled Line Extraction
    for line in lines:
        if re.search(r"(?:Candidate|Citizen|Name|नाम)\s*[:\-]", line, re.IGNORECASE):
            parts = re.split(r"[:\-]", line, maxsplit=1)
            if len(parts) > 1:
                val = re.sub(r"[^A-Za-z\s]", "", parts[1]).strip()
                if len(val) > 2 and "FATHER" not in val.upper():
                    name = val

        if re.search(r"(?:Father|Guardian|Spouse|Husband|S/o|D/o)\s*(?:Name)?\s*[:\-]", line, re.IGNORECASE):
            parts = re.split(r"[:\-]", line, maxsplit=1)
            if len(parts) > 1:
                val = re.sub(r"[^A-Za-z\s]", "", parts[1]).strip()
                if len(val) > 2:
                    father = val

    # Universal Pattern Search
    # 1. PAN Number regex (5 letters + 4 digits + 1 letter)
    pan_match = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", raw_text)
    if pan_match:
        gov_id = pan_match.group(1)

    # 2. Aadhaar regex (12 digits)
    if gov_id == "Not Detected":
        aadhaar_match = re.search(r"\b(\d{4}\s\d{4}\s\d{4})\b", raw_text)
        if aadhaar_match:
            gov_id = aadhaar_match.group(1)

    # 3. Any General Reg/Roll Number
    if gov_id == "Not Detected":
        id_gen = re.search(r"(?:No|Number|ID)[:\-\s]*([A-Za-z0-9\-/]{6,22})", raw_text, re.IGNORECASE)
        if id_gen:
            gov_id = id_gen.group(1).strip()

    # 4. DOB Pattern (DD/MM/YYYY)
    dob_match = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", raw_text)
    if dob_match:
        dob = dob_match.group(1)

    # 5. Gender
    gen_match = re.search(r"\b(MALE|FEMALE)\b", raw_text, re.IGNORECASE)
    if gen_match:
        gender = gen_match.group(1).upper()

    # PAN Specific Fallback for Names
    if doc_type == "PAN Card" and name == "Not Detected":
        # Usually names on PAN cards are written in full uppercase words
        filtered_lines = [
            l for l in lines 
            if re.match(r"^[A-Z\s]{4,30}$", l.strip()) 
            and not any(w in l for w in ["INDIA", "GOVT", "TAX", "DEPARTMENT", "PERMANENT", "ACCOUNT", "NUMBER", "CARD", "SIGNATURE"])
        ]
        if len(filtered_lines) >= 1:
            name = filtered_lines[0].strip()
        if len(filtered_lines) >= 2 and father == "Not Detected":
            father = filtered_lines[1].strip()

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

st.subheader("📂 Upload Scanned Documents (Camera Photos / HD Scans)")
uploaded_files = st.file_uploader(
    "Select Documents (JPG, PNG)",
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
            status_text.text(f"Processing ({i+1}/{len(uploaded_files)}): {file_obj.name}")
            data_row = extract_universal_data(file_obj)
            extracted_rows.append(data_row)
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        status_text.success("Pipeline Execution Complete!")
        df = pd.DataFrame(extracted_rows)
        
        st.subheader("📊 Extracted Multi-Format Master Table")
        st.dataframe(df, use_container_width=True)
        
        output_buffer = io.BytesIO()
        df.to_excel(output_buffer, index=False, engine="openpyxl")
        
        time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="📥 Download Contractor Deliverable (Excel)",
            data=output_buffer.getvalue(),
            file_name=f"Sinha_AI_Universal_Extract_{time_stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
        
