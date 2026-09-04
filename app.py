def extract_universal_data(uploaded_file):
    raw_pil = Image.open(uploaded_file)
    processed_bin, gray_img = preprocess_camera_image(raw_pil)
    
    # Dual OCR: Gray image for layout, Hindi+Eng support
    raw_text = pytesseract.image_to_string(gray_img, config='--psm 6 -l eng+hin')
    if len(re.sub(r'[^A-Za-z0-9]', '', raw_text)) < 15:
        raw_text = pytesseract.image_to_string(processed_bin, config='--psm 3 -l eng')

    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

    name = "Not Detected"
    father = "Not Detected"
    gov_id = "Not Detected"
    dob = "Not Detected"
    gender = "Not Detected"
    doc_type = "General Document"

    full_text_upper = raw_text.upper()

    # 1. Document Classification
    if "AADHAAR" in full_text_upper or "UNIQUE IDENTIFICATION" in full_text_upper or "MERA AADHAAR" in full_text_upper or "आधार" in raw_text:
        doc_type = "Aadhaar Card"
    elif "PERMANENT ACCOUNT" in full_text_upper or "INCOME TAX" in full_text_upper:
        doc_type = "PAN Card"
    elif "DRIVING LICENCE" in full_text_upper:
        doc_type = "Driving License"

    # 2. Aadhaar Specific Extraction (Priority)
    aadhaar_match = re.search(r"\b([2-9]\d{3}\s\d{4}\s\d{4})\b", raw_text)
    if aadhaar_match:
        gov_id = aadhaar_match.group(1)

    # 3. DOB Extraction
    dob_match = re.search(r"(?:DOB|जन्म|Date of Birth)[\s:\-/]*(\d{2}[/-]\d{2}[/-]\d{4})", raw_text, re.IGNORECASE)
    if dob_match:
        dob = dob_match.group(1)
    else:
        fallback_dob = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", raw_text)
        if fallback_dob:
            dob = fallback_dob.group(1)

    # 4. Gender Extraction (Handles slash like पुरुष/ MALE)
    if re.search(r"(?:MALE|पुरुष)\b", raw_text, re.IGNORECASE):
        if re.search(r"(?:FEMALE|महिला)\b", raw_text, re.IGNORECASE):
            gender = "FEMALE"
        else:
            gender = "MALE"

    # 5. Aadhaar Name Extraction (Direct Line Before DOB)
    if doc_type == "Aadhaar Card":
        for i, line in enumerate(lines):
            if any(k in line.upper() for k in ["DOB", "YEAR OF BIRTH", "जन्म"]):
                # Usually English name is 1 line above DOB line
                if i >= 1:
                    cand = re.sub(r"[^A-Za-z\s]", "", lines[i-1]).strip()
                    if len(cand) > 3 and not any(w in cand.upper() for w in ["INDIA", "GOVERNMENT", "AADHAAR"]):
                        name = cand
                break

    # 6. Fallback General Extraction for Other Forms / PAN
    if name == "Not Detected":
        for line in lines:
            if re.search(r"(?:Candidate|Citizen|Name)\s*[:\-]", line, re.IGNORECASE):
                parts = re.split(r"[:\-]", line, maxsplit=1)
                if len(parts) > 1:
                    clean_val = re.sub(r"[^A-Za-z\s]", "", parts[1]).strip()
                    if len(clean_val) > 2 and "FATHER" not in clean_val.upper():
                        name = clean_val
                        break

    if gov_id == "Not Detected":
        pan_m = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", raw_text)
        if pan_m:
            gov_id = pan_m.group(1)
            doc_type = "PAN Card"

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
    
