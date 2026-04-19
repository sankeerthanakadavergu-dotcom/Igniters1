import re
import pdfplumber

# AP Intelligence Agent — Fast Version
# No API calls — instant processing
# pip install pdfplumber gradio

def read_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text

def extract_fields(text):
    fields = {}
    for p in [r"Invoice\s*#[:\s]*([\w\-]+)"]:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            fields["invoice_number"] = m.group(1).strip()
            break
    for p in [r"From[:\s]+(.+)", r"Vendor[:\s]+(.+)"]:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            fields["vendor"] = m.group(1).strip()
            break
    if "vendor" not in fields:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            if "INVOICE" in line.upper() and i+1 < len(lines):
                fields["vendor"] = lines[i+1]
                break
    for p in [r"TOTAL DUE[:\s]*\$?([\d,]+\.?\d*)",
              r"TOTAL[:\s]*\$?([\d,]+\.?\d*)"]:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            fields["total"] = float(m.group(1).replace(",",""))
            break
    for p in [r"PO\s*Number[:\s]*([\w\-]+)",
              r"PO\s*#[:\s]*([\w\-]+)",
              r"PO[:\s]+([\w\-]+)",
              r"(PO-[\w\-]+)"]:
        m = re.search(p, text, re.IGNORECASE)
        if m and len(m.group(1)) > 2:
            fields["po_number"] = m.group(1).strip()
            break
    m = re.search(r"Tax[:\s]*\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    fields["tax"] = float(m.group(1).replace(",","")) if m else 0.0
    m = re.search(r"Subtotal[:\s]*\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    fields["subtotal"] = float(m.group(1).replace(",","")) if m else fields.get("total",0)
    m = re.search(r"Due\s*Date[:\s]*([\d\-\/\w\s]+)", text, re.IGNORECASE)
    fields["due_date"] = m.group(1).strip()[:10] if m else "N/A"
    m = re.search(r"Issue\s*Date[:\s]*([\d\-\/\w\s]+)", text, re.IGNORECASE)
    fields["issue_date"] = m.group(1).strip()[:10] if m else "N/A"
    m = re.search(r"Terms[:\s]*([\w\s\d]+)", text, re.IGNORECASE)
    fields["terms"] = m.group(1).strip()[:10] if m else "N/A"
    fields.setdefault("total", 0)
    fields.setdefault("vendor", "Unknown Vendor")
    fields.setdefault("invoice_number", "INV-UNKNOWN")
    fields.setdefault("po_number", None)
    return fields

def detect_anomalies(fields, raw_text):
    anomalies = []
    total    = fields.get("total", 0)
    po       = fields.get("po_number")
    tax      = fields.get("tax", 0)
    subtotal = fields.get("subtotal", total)
    terms    = fields.get("terms", "")
    inv_num  = fields.get("invoice_number", "")

    # Check 1 — Missing PO
    if not po:
        anomalies.append({"type": "MISSING_PO", "severity": "MEDIUM",
            "detail": "No Purchase Order number found.",
            "action": "Request PO number from vendor."})

    # Check 2 — Double overcharge
    for kw in ["double overcharge","double charge","duplicate charge","billed twice","overcharge"]:
        if kw.lower() in raw_text.lower():
            anomalies.append({"type": "DOUBLE_OVERCHARGE", "severity": "HIGH",
                "detail": "Double charge detected in invoice.",
                "action": "REJECT — Block payment."})
            break

    # Check 3 — Tax anomaly
    if subtotal and subtotal > 0 and tax:
        rate = (tax / subtotal) * 100
        if rate > 12:
            anomalies.append({"type": "TAX_ANOMALY", "severity": "MEDIUM",
                "detail": "Tax rate "+str(round(rate,1))+"% above 8-10%.",
                "action": "Verify tax rate with vendor."})

    # Check 4 — Round number
    if total > 1000 and total % 500 == 0:
        anomalies.append({"type": "ROUND_NUMBER_FLAG", "severity": "LOW",
            "detail": "Total $"+str(total)+" is suspiciously round.",
            "action": "Verify all line items."})

    # Check 5 — High value
    if total > 5000:
        anomalies.append({"type": "HIGH_VALUE_INVOICE", "severity": "MEDIUM",
            "detail": "Total $"+str(total)+" exceeds $5,000.",
            "action": "Escalate to senior AP manager."})

    # Check 6 — Short payment terms
    if any(t in terms.lower() for t in ["net 7","net 10","net 14"]):
        anomalies.append({"type": "SHORT_PAYMENT_TERMS", "severity": "MEDIUM",
            "detail": "Payment terms "+terms+" shorter than Net 30.",
            "action": "Verify payment terms."})

    # Check 7 — Vague line items
    for kw in ["misc","miscellaneous","unspecified","admin fee"]:
        if kw.lower() in raw_text.lower():
            anomalies.append({"type": "VAGUE_LINE_ITEM", "severity": "MEDIUM",
                "detail": "Vague line item found: "+kw,
                "action": "Request itemized breakdown."})
            break

    # Check 8 — Duplicate invoice
    if inv_num and raw_text.lower().count(inv_num.lower()) > 2:
        anomalies.append({"type": "POSSIBLE_DUPLICATE", "severity": "HIGH",
            "detail": "Invoice number appears multiple times.",
            "action": "Verify not already paid."})

    return anomalies
