import streamlit as st
from google import genai
from google.genai import types
from PIL import Image, ImageOps
import pandas as pd
from datetime import datetime
import json
import io

st.set_page_config(
    page_title="Sinha AI Tech Solutions",
    page_icon="⚡",
    layout="wide"
)

st.markdown("""
    <div style="background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%); padding: 18px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #38bdf8;">
        <h2 style="color: #ffffff; margin: 0; font-size: 20px;">Sinha AI Tech Solutions</h2>
        <p style="color: #94a3b8; margin: 4px 0 0 0; font-size: 13px;">Enterprise AI Document Digitization & Audit Engine</p>
    </div>
""", unsafe_allow_html=True)

# Direct Production Client
API_KEY = "AQ.Ab8RN6J2xxqu4ZT1YQERsRdDt5oUNFQu7sErmpZhcq9RtMLUTw"
client = genai.Client(api_key=API_KEY)

def analyze_document_with_ai(image_file):
    pil_img = Image.open(image_file)
    pil_img = ImageOps.exif_transpose(pil_img).convert("RGB")
    
    prompt = """
    You are an expert government document parser. Analyze this uploaded image with 100% precision.
    
    Extract the following details in pure JSON format:
    {
        "document_type": "PAN Card / Aadhaar Card / Driving License / Educational Certificate / General Form",
        "candidate_name": "Full legal name of the person (Uppercase English)",
        "father_name": "Father or Guardian or Spouse name (if present, else Not Detected)",
        "id_number": "Exact ID number (PAN, Aadhaar, Roll No, or Reg No)",
        "dob": "Date of birth in DD/MM/YYYY format",
        "gender": "MALE / FEMALE / TRANSGENDER",
        "audit_status": "Verified"
    }

    Strict Rules:
    1. If it is a PAN card, correctly extract the Cardholder Name and separate it from Father's Name.
    2. Ignore background textures, stamps, and watermarks.
    3. Return ONLY valid JSON without markdown formatting, backticks, or extra text.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[pil_img, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1
        )
    )
    
    cleaned_json = response.text.strip()
    if cleaned_json.startswith("```json"):
        cleaned_json = cleaned_json[7:]
    if cleaned_json.startswith("```"):
        cleaned_json = cleaned_json[3:]
    if cleaned_json.endswith("```"):
        cleaned_json = cleaned_json[:-3]
        
    parsed = json.loads(cleaned_json.strip())
    
    return {
        "File Name": image_file.name,
        "Document Type": parsed.get("document_type", "General Document"),
        "Candidate / Citizen Name": parsed.get("candidate_name", "Not Detected"),
        "Father / Guardian Name": parsed.get("father_name", "Not Detected"),
        "ID / Registration / Roll No": parsed.get("id_number", "Not Detected"),
        "DOB": parsed.get("dob", "Not Detected"),
        "Gender": parsed.get("gender", "Not Detected"),
        "Audit Status": parsed.get("audit_status", "Verified")
    }

st.subheader("📂 Upload Documents (Aadhaar / PAN / Forms / Certificates)")
uploaded_files = st.file_uploader(
    "Select Documents (JPG, PNG)",
    type=["jpg", "png", "jpeg"],
    accept_multiple_files=True
)

if uploaded_files:
    st.info(f"Queued {len(uploaded_files)} document(s) for extraction.")
    if st.button("🚀 Run Universal AI Digitization", type="primary"):
        progress_bar = st.progress(0)
        extracted_rows = []
        
        for i, file_obj in enumerate(uploaded_files):
            try:
                data_row = analyze_document_with_ai(file_obj)
                extracted_rows.append(data_row)
            except Exception as e:
                extracted_rows.append({
                    "File Name": file_obj.name,
                    "Document Type": "Unrecognized",
                    "Candidate / Citizen Name": "Extraction Failed",
                    "Father / Guardian Name": "Not Detected",
                    "ID / Registration / Roll No": "Not Detected",
                    "DOB": "Not Detected",
                    "Gender": "Not Detected",
                    "Audit Status": f"Needs Review ({str(e)[:35]})"
                })
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        st.success("Universal AI Pipeline Complete!")
        df = pd.DataFrame(extracted_rows)
        st.dataframe(df, use_container_width=True)
        
        output_buffer = io.BytesIO()
        df.to_excel(output_buffer, index=False, engine="openpyxl")
        
        time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="📥 Download Sinha AI Tech Verified Excel",
            data=output_buffer.getvalue(),
            file_name=f"Sinha_AI_Final_Extract_{time_stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
            
