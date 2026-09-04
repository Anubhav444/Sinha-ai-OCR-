def extract_universal_data(uploaded_file):
    raw_pil = Image.open(uploaded_file)
    processed_bin, gray_img = preprocess_camera_image(raw_pil)
    
    # Dual-pass OCR for complex background cards
    raw_text = pytesseract.image_to_string(gray_img, config='--psm 6')
    if len(re.sub(r'[^A-Za-z0-9]', '', raw_text)) < 25:
        raw_text = pytesseract.image_to_string(processed_bin, config='--psm 4')

    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

    name = "Not Detected"
    father = "Not Detected"
    gov_id = "Not Detected"
    dob = "Not Detected"
    gender = "Not Detected"
    doc_type = "General Document"

    full_text_upper = raw_text.upper()

    # Document Classification
    if "AADHAAR" in full_text_upper or "UNIQUE IDENTIFICATION" in full_text_upper or "GOVERNMENT OF INDIA" in full_text_upper:
        doc_type = "Aadhaar Card"
    elif "PERMANENT ACCOUNT" in full_text_upper or "INCOME TAX" in full_text_upper or re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", raw_text):
        doc_type = "PAN Card"
    elif "DRIVING" in full_text_upper or "TRANSPORT" in full_text_upper:
        doc_type = "Driving License"

    # ID Parsing
    if doc_type == "PAN Card" or gov_id == "Not Detected":
        pan_m = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", raw_text)
        if pan_m:
            gov_id = pan_m.group(1)

    if gov_id == "Not Detected" or doc_type == "Aadhaar Card":
        aadhaar_m = re.search(r"\b([2-9]\d{3}\s\d{4}\s\d{4})\b", raw_text)
        if aadhaar_m:
            gov_id = aadhaar_m.group(1)

    # DOB Parsing
    dob_m = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", raw_text)
    if dob_m:
        dob = dob_m.group(1)

    # Gender Parsing
    if re.search(r"\bMALE\b", raw_text, re.IGNORECASE):
        gender = "FEMALE" if re.search(r"\bFEMALE\b", raw_text, re.IGNORECASE) else "MALE"

    # Aadhaar Clean Name Parsing (Strip any single/double character noise prefix)
    if doc_type == "Aadhaar Card":
        for i, line in enumerate(lines):
            if any(k in line.upper() for k in ["DOB", "YEAR OF BIRTH"]):
                if i >= 1:
                    cand = re.sub(r"[^A-Za-z\s]", "", lines[i-1]).strip()
                    # Filter out noise prefix like 'Sq '
                    words = cand.split()
                    clean_words = [w for w in words if len(w) > 2 or w.upper() in ["OM", "AL"]]
                    if len(clean_words) >= 1:
                        cand = " ".join(clean_words)
                    if len(cand) > 3 and not any(w in cand.upper() for w in ["INDIA", "GOVERNMENT", "AADHAAR"]):
                        name = cand
                break

    # PAN Specific Name & Father Name Parsing
    if doc_type == "PAN Card":
        # Look for labels like "Name" / "Father's Name" or isolate clean uppercase lines
        for i, line in enumerate(lines):
            if re.search(r"(?:Name|नाम)\b", line, re.IGNORECASE) and not re.search(r"(?:Father|Department|Card|Account)", line, re.IGNORECASE):
                # Target value line
                cand_val = re.sub(r"(?:Name|नाम|[:\-])", "", line, flags=re.IGNORECASE).strip()
                cand_val = re.sub(r"[^A-Za-z\s]", "", cand_val).strip()
                if len(cand_val) > 3:
                    name = cand_val
                elif i + 1 < len(lines):
                    next_cand = re.sub(r"[^A-Za-z\s]", "", lines[i+1]).strip()
                    if len(next_cand) > 3 and next_cand.isupper():
                        name = next_cand

            if re.search(r"(?:Father|पिता)\b", line, re.IGNORECASE):
                f_val = re.sub(r"(?:Father|Name|नाम|पिता|[:\-])", "", line, flags=re.IGNORECASE).strip()
                f_val = re.sub(r"[^A-Za-z\s]", "", f_val).strip()
                if len(f_val) > 3:
                    father = f_val
                elif i + 1 < len(lines):
                    next_f = re.sub(r"[^A-Za-z\s]", "", lines[i+1]).strip()
                    if len(next_f) > 3 and next_f.isupper():
                        father = next_f

    # Labeled Line Extraction Fallback
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
                                       
