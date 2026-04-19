import os, re, asyncio, pdfplumber, json
import gradio as gr
import google.generativeai as genai
from datetime import datetime
from hindsight_client import Hindsight

# ── API SETUP ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY = "AIzaSyANVOFHsMaa97EqGLxPWVAvJQEU0w6adz4"
genai.configure(api_key=GEMINI_API_KEY)

hs = Hindsight(
    base_url=os.environ.get("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io"),
    api_key=os.environ.get("HINDSIGHT_API_KEY", "hsk_4cbd649d6568ddccb45d9819cd649d77_b50c04c42f6077d0")
)
BANK = "ap-memory-v2"
seen_invoices = {}

# ── STEP 1: FAST TEXT EXTRACTION (no images, no Gemini Vision) ────────────────
def extract_text_from_pdf(pdf_path):
    """Extract text using pdfplumber only — instant, no API calls needed."""
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    full_text += t + "\n"
    except Exception as e:
        return "", f"PDF read error: {e}"
    return full_text.strip(), None

# ── STEP 2: GEMINI FRAUD ANALYSIS (text only, fast) ──────────────────────────
def gemini_fraud_analysis(text):
    """Send extracted text to Gemini for fraud analysis — no image upload."""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        # Only send first 1000 chars to keep it fast
        trimmed = text[:1000]
        response = model.generate_content(
            f"You are an AP fraud expert. Analyze this invoice text and list any issues "
            f"such as: double charge, missing PO, suspicious items, high tax, duplicate invoice. "
            f"Be brief. Say NO ISSUES DETECTED if clean.\n\nInvoice:\n{trimmed}"
        )
        return response.text
    except Exception as e:
        return f"Gemini analysis error: {e}"

# ── STEP 3: FIELD EXTRACTION ──────────────────────────────────────────────────
def extract_invoice_fields(text):
    fields = {}

    # Invoice number
    for pattern in [r"Invoice\s*#\s*:?\s*([\w\-]+)", r"INV[\-:\s]+([\w\-]+)"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            fields["invoice_number"] = m.group(1).strip()
            break

    # Vendor name
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if "INVOICE" in line.upper() and i + 1 < len(lines):
            fields["vendor_name"] = lines[i + 1]
            break
    if "vendor_name" not in fields:
        for pattern in [r"From[:\s]+(.+)", r"Vendor[:\s]+(.+)", r"Bill\s*From[:\s]+(.+)"]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                fields["vendor_name"] = m.group(1).strip()
                break

    # Total amount
    for pattern in [
        r"TOTAL\s*DUE\s*:?\s*\$?([\d,]+\.?\d*)",
        r"AMOUNT\s*DUE\s*:?\s*\$?([\d,]+\.?\d*)",
        r"GRAND\s*TOTAL\s*:?\s*\$?([\d,]+\.?\d*)",
        r"TOTAL\s*:?\s*\$?([\d,]+\.?\d*)",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            fields["total"] = float(m.group(1).replace(",", ""))
            break

    # PO number — handles all formats
    po_patterns = [
        r"P\.?O\.?\s*Number\s*:?\s*([\w\-]+)",
        r"P\.?O\.?\s*#\s*:?\s*([\w\-]+)",
        r"Purchase\s*Order\s*(?:No|Number|#)?\s*:?\s*([\w\-]+)",
        r"\bPO\s*:\s*([\w\-]+)",
        r"(PO-[\w\-]+)",
    ]
    for pattern in po_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if len(candidate) >= 3 and candidate.upper() not in ["NUMBER", "NO", "NUM", "REF"]:
                fields["po_number"] = candidate
                break

    # Tax and subtotal
    m = re.search(r"Tax\s*:?\s*\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    fields["tax"] = float(m.group(1).replace(",", "")) if m else 0.0

    m = re.search(r"Subtotal\s*:?\s*\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    fields["subtotal"] = float(m.group(1).replace(",", "")) if m else None

    # Double overcharge keyword scan
    overcharge_keywords = [
        "double charge", "double overcharge", "charged twice",
        "billed twice", "duplicate charge", "overcharge", "double billed"
    ]
    fields["has_overcharge"] = any(kw in text.lower() for kw in overcharge_keywords)

    # Defaults
    fields.setdefault("total", 0)
    fields.setdefault("vendor_name", "Unknown Vendor")
    fields.setdefault("invoice_number", "INV-UNKNOWN")
    fields.setdefault("po_number", None)
    return fields

# ── STEP 4: ANOMALY DETECTION ─────────────────────────────────────────────────
def detect_anomalies(fields, memories, gemini_analysis):
    anomalies = []
    total    = fields.get("total", 0)
    vendor   = fields.get("vendor_name", "Unknown")
    po       = fields.get("po_number")
    tax      = fields.get("tax", 0)
    subtotal = fields.get("subtotal") or total
    inv_num  = fields.get("invoice_number", "")

    # 1. Double overcharge keyword in invoice text
    if fields.get("has_overcharge"):
        anomalies.append({
            "type": "DOUBLE_OVERCHARGE", "severity": "HIGH",
            "detail": "Invoice text contains double charge / overcharge indicator.",
            "action": "REJECT — Block payment. Request corrected invoice."
        })

    # 2. Gemini AI flagged fraud
    if gemini_analysis and "NO ISSUES DETECTED" not in gemini_analysis.upper():
        if any(w in gemini_analysis.lower() for w in ["double", "overcharge", "fraud", "duplicate"]):
            anomalies.append({
                "type": "GEMINI_FRAUD_DETECTED", "severity": "HIGH",
                "detail": f"Gemini AI flagged: {gemini_analysis[:200]}",
                "action": "REJECT — Gemini AI detected fraud."
            })
        elif any(w in gemini_analysis.lower() for w in ["missing", "suspicious", "violation", "issue"]):
            anomalies.append({
                "type": "GEMINI_ISSUE_DETECTED", "severity": "MEDIUM",
                "detail": f"Gemini AI flagged: {gemini_analysis[:200]}",
                "action": "HOLD — Review issue detected by Gemini AI."
            })

    # 3. Vendor average overcharge
    avg_amount = None
    if memories:
        amounts = re.findall(r"\$?([\d,]+\.?\d+)", " ".join(memories))
        nums = [float(a.replace(",", "")) for a in amounts if float(a.replace(",", "")) > 100]
        if nums:
            avg_amount = sum(nums) / len(nums)
    if avg_amount and total > avg_amount * 1.15:
        pct = ((total - avg_amount) / avg_amount) * 100
        anomalies.append({
            "type": "AMOUNT_OVERCHARGE", "severity": "HIGH",
            "detail": f"Total ${total:,.2f} is {pct:.1f}% above vendor average ${avg_amount:,.2f}.",
            "action": "Hold payment and dispute with vendor."
        })

    # 4. Missing PO number
    if not po:
        anomalies.append({
            "type": "MISSING_PO", "severity": "MEDIUM",
            "detail": "No Purchase Order number found on invoice.",
            "action": "Request PO number from vendor."
        })

    # 5. High tax rate
    if subtotal and subtotal > 0 and tax:
        rate = (tax / subtotal) * 100
        if rate > 12:
            anomalies.append({
                "type": "TAX_ANOMALY", "severity": "MEDIUM",
                "detail": f"Tax rate is {rate:.1f}% — above standard 8-10%.",
                "action": "Verify tax rate with vendor."
            })

    # 6. New vendor
    if not memories:
        anomalies.append({
            "type": "NEW_VENDOR", "severity": "MEDIUM",
            "detail": f"No prior history found for {vendor}.",
            "action": "Verify vendor registration."
        })

    # 7. Round number flag
    if total > 1000 and total % 500 == 0:
        anomalies.append({
            "type": "ROUND_NUMBER_FLAG", "severity": "LOW",
            "detail": f"Total ${total:,.2f} is a suspiciously round number.",
            "action": "Verify all line items."
        })

    # 8. High value invoice
    if total > 5000:
        anomalies.append({
            "type": "HIGH_VALUE_INVOICE", "severity": "MEDIUM",
            "detail": f"Total ${total:,.2f} exceeds $5,000 threshold.",
            "action": "Escalate to senior AP manager."
        })

    return anomalies

# ── STEP 5: DISPUTE EMAIL ─────────────────────────────────────────────────────
def generate_email(vendor, inv_num, total, anomaly):
    email_to = f"billing@{vendor.lower().replace(' ', '')}.com"
    return (
        f"To: {email_to}\n"
        f"Subject: Invoice {inv_num} — {anomaly['type'].replace('_', ' ')}\n\n"
        f"Dear {vendor} Finance Team,\n\n"
        f"We received invoice {inv_num} for ${total:,.2f} and flagged:\n\n"
        f"{anomaly['detail']}\n\n"
        f"Required action: {anomaly['action']}\n\n"
        f"Please respond within 2 business days.\n\n"
        f"Regards,\nAccounts Payable Team"
    )

# ── STEP 6: HINDSIGHT MEMORY ──────────────────────────────────────────────────
def get_memories(vendor):
    try:
        loop = asyncio.new_event_loop()
        r = loop.run_until_complete(
            hs.arecall(bank_id=BANK, query=f"invoice history for vendor {vendor}")
        )
        loop.close()
        return [x.text for x in r.results] if r.results else []
    except:
        return []

def save_memory(vendor, inv_num, total, status):
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            hs.aretain(
                bank_id=BANK,
                content=f"Vendor: {vendor}. Invoice: {inv_num}. Total: ${total:,.2f}. Status: {status}.",
                context=f"vendor_{vendor.replace(' ', '_')}"
            )
        )
        loop.close()
    except:
        pass

# ── MAIN PROCESS FUNCTION ─────────────────────────────────────────────────────
def process_invoice(pdf_file):
    if pdf_file is None:
        return "❌ Please upload a PDF file.", "", "", ""

    # STEP 1: Fast text extraction (pdfplumber — no images, no API)
    raw_text, err = extract_text_from_pdf(pdf_file.name)
    if err or not raw_text.strip():
        return f"❌ Could not read PDF text: {err or 'Empty PDF'}", "", "", ""

    # STEP 2: Gemini fraud analysis (text only — fast)
    gemini_analysis = gemini_fraud_analysis(raw_text)

    # STEP 3: Extract fields
    fields  = extract_invoice_fields(raw_text)
    vendor  = fields.get("vendor_name", "Unknown")
    inv_num = fields.get("invoice_number", "N/A")
    total   = fields.get("total", 0)

    # STEP 4: Hindsight memory recall
    memories = get_memories(vendor)

    # STEP 5: Detect anomalies
    anomalies = detect_anomalies(fields, memories, gemini_analysis)

    # STEP 6: Make decision
    high   = [a for a in anomalies if a["severity"] == "HIGH"]
    medium = [a for a in anomalies if a["severity"] == "MEDIUM"]
    low    = [a for a in anomalies if a["severity"] == "LOW"]

    if high:     status, risk = "REJECTED", "HIGH"
    elif medium: status, risk = "HOLD FOR REVIEW", "MEDIUM"
    elif low:    status, risk = "APPROVED WITH NOTE", "LOW"
    else:        status, risk = "APPROVED", "LOW"

    icons = {"APPROVED": "✅", "APPROVED WITH NOTE": "✅⚠️",
             "HOLD FOR REVIEW": "⚠️", "REJECTED": "❌"}

    # STEP 7: Build result text
    result  = f"{icons.get(status)} {status}\n\n"
    result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    result += "INVOICE DETAILS\n"
    result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    result += f"Vendor:          {vendor}\n"
    result += f"Invoice Number:  {inv_num}\n"
    result += f"Total Amount:    ${total:,.2f}\n"
    result += f"PO Number:       {fields.get('po_number') or 'NOT FOUND'}\n"
    result += f"Tax:             ${fields.get('tax', 0):,.2f}\n"
    result += f"Risk Level:      {risk}\n"
    result += f"Memory Records:  {len(memories)}\n\n"
    result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    result += "GEMINI AI ANALYSIS\n"
    result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    result += gemini_analysis + "\n\n"
    result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    result += f"ANOMALIES FOUND ({len(anomalies)})\n"
    result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"

    if anomalies:
        for a in anomalies:
            result += f"❗ [{a['severity']}] {a['type']}\n"
            result += f"   → {a['detail']}\n\n"
    else:
        result += "✅ None — invoice is clean\n"

    result += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    result += "EXTRACTED TEXT (first 300 chars)\n"
    result += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    result += raw_text[:300] + "..."

    # Action required
    actions = {
        "APPROVED":           "✅ Approve payment — no issues found",
        "APPROVED WITH NOTE": "✅ Approve with low-risk note",
        "HOLD FOR REVIEW":    "⚠️ Hold — review dispute email below",
        "REJECTED":           "❌ Block payment — send dispute email now"
    }
    action = actions.get(status, "Manual review required")

    # Draft email
    draft = ""
    if status in ["REJECTED", "HOLD FOR REVIEW"] and anomalies:
        draft = generate_email(vendor, inv_num, total, anomalies[0])

    # Save to memory
    save_memory(vendor, inv_num, total, status)
    memory_status = f"Vendor: {vendor} | Records: {len(memories)} | ✓ Saved to Hindsight"

    return result, action, draft, memory_status

# ── GRADIO UI ─────────────────────────────────────────────────────────────────
with gr.Blocks(title="AP Intelligence Agent") as app:
    gr.Markdown("# 🧾 AP Intelligence Agent")
    gr.Markdown("Upload any invoice PDF — **fast text OCR** + Gemini fraud analysis + Hindsight memory")

    with gr.Row():
        with gr.Column(scale=1):
            pdf_input  = gr.File(label="📄 Upload Invoice PDF", file_types=[".pdf"])
            scan_btn   = gr.Button("🔍 Scan Invoice", variant="primary", size="lg")
            memory_out = gr.Textbox(label="💾 Hindsight Memory", interactive=False)

        with gr.Column(scale=2):
            result_out = gr.Textbox(label="📊 Scan Results + Decision", lines=28, interactive=False)
            action_out = gr.Textbox(label="⚡ Action Required", interactive=False)
            email_out  = gr.Textbox(label="📧 Draft Dispute Email", lines=14, interactive=True)

    scan_btn.click(
        fn=process_invoice,
        inputs=[pdf_input],
        outputs=[result_out, action_out, email_out, memory_out]
    )

app.launch(share=True)
