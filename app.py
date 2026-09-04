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

# Mobile-Optimized Enterprise UI
st.set_page_config(page_title="Sinha AI Tech - OCR Portal", layout="wide")

st.markdown("""
    <div style="background: #0f172a; padding: 18px; border-radius: 10px; border-left: 5px solid #38bdf8; margin-bottom: 20px;">
        <h2 style="color: #ffffff; margin: 0; font-size: 22px;">Sinha AI Tech Solutions</h2>
        <p style="color: #94a3b8; margin: 5px 0 0 0; font-size: 13px;">AI Document Digitization & Automated Record Extraction</p>
    </div>
""", unsafe_allow_html=True)

def process_image(uploaded_file):
    image = Image.open(uploaded_file).convert("RGB")
    open_cv_image = np.array(image)
    
    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    
    text = pytesseract.image_to_string(thresh, config='--psm 3 -l eng')
    
    name_m = re.search(r"Name\s*[:\-]\s*([A-Za-z\s]+)", text, re.IGNORECASE)
    father_m = re.search(r"Father(?:\s+Name)?\s*[:\-]\s*([A-Za-z\s]+)", text, re.IGNORECASE)
    id_m = re.search(r"(?:Registration\s*No|ID\s*No|Reg\s*No)\s*[:\-]\s*([A-Za-z0-9\-]+)", text, re.IGNORECASE)
    dob_m = re.search(r"(?:DOB|Date of Birth)\s*[:\-]?\s*(\d{2}[/-]\d{2}[/-]\d{4})", text, re.IGNORECASE)
    gender_m = re.search(r"(?:Gender|Sex)\s*[:\-]\s*(MALE|FEMALE)", text, re.IGNORECASE)
    
    if not dob_m:
        dob_m = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", text)
    if not gender_m:
        gender_m = re.search(r"\b(MALE|FEMALE)\b", text, re.IGNORECASE)

    extracted_name = name_m.group(1).strip().split("\n")[0] if name_m else "Pending Review"
    extracted_father = father_m.group(1).strip().split("\n")[0] if father_m else "Not Detected"
    extracted_id = id_m.group(1).strip() if id_m else "Not Detected"
    extracted_dob = dob_m.group(1).strip() if dob_m else "Not Detected"
    extracted_gender = gender_m.group(1).strip().upper() if gender_m else "Not Detected"
    
    is_verified = (extracted_name != "Pending Review" and extracted_id != "Not Detected")
    
    return {
        "File Name": uploaded_file.name,
        "Citizen / Candidate Name": extracted_name,
        "Father / Spouse Name": extracted_father,
        "ID / Registration No": extracted_id,
        "DOB": extracted_dob,
        "Gender": extracted_gender,
        "Status": "Verified" if is_verified else "Needs Review"
    }

st.subheader("📁 Scanned Documents Upload")
files = st.file_uploader("Select Scanned Images (JPG, PNG)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

if files:
    st.info(f"{len(files)} files uploaded successfully.")
    if st.button("🚀 Start AI Digitization", type="primary"):
        progress_bar = st.progress(0)
        records = []
        
        for idx, f in enumerate(files):
            records.append(process_image(f))
            progress_bar.progress((idx + 1) / len(files))
        
        st.success("Extraction Completed!")
        df = pd.DataFrame(records)
        st.dataframe(df, use_container_width=True)
        
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="📥 Download Sinha AI Tech Verified Excel",
            data=excel_buffer.getvalue(),
            file_name=f"Sinha_AI_Batch_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      )
      
