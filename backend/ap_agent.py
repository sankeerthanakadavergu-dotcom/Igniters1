import os, re, asyncio, pdfplumber, json
from datetime import datetime
from hindsight_client import Hindsight

DATA_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data")
BANK = "ap-memory-v2"
seen_invoices = {}

hs = Hindsight(
    base_url=os.environ["HINDSIGHT_BASE_URL"],
    api_key=os.environ["HINDSIGHT_API_KEY"]
)

# ── FAST TEXT EXTRACTION (no images, no Gemini Vision) ──────────────────────
def extract_text_from_pdf(path):
    """Extract text using pdfplumber only — instant, no API calls."""
    try:
        with pdfplumber.open(path) as pdf:
            pages_text = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages_text.append(t)
            return "\n".join(pages_text)
    except Exception as e:
        print(f"  PDF read error: {e}")
        return ""

# ── FIELD EXTRACTION ─────────────────────────────────────────────────────────
def extract_invoice_fields(text):
    fields = {}

    # Invoice number
    for pattern in [r"Invoice\s*#[:\s]*([\w\-]+)", r"INV[:\-\s]*([\w\-]+)"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            fields["invoice_number"] = m.group(1).strip()
            break

    # Vendor name — line after "INVOICE" heading
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if "INVOICE" in line.upper() and i + 1 < len(lines):
            fields["vendor_name"] = lines[i + 1]
            break
    # Fallback: look for "From:" or "Vendor:" label
    if "vendor_name" not in fields:
        for pattern in [r"From[:\s]+(.+)", r"Vendor[:\s]+(.+)", r"Bill\s*From[:\s]+(.+)"]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                fields["vendor_name"] = m.group(1).strip()
                break

    # Total amount
    for pattern in [
        r"TOTAL\s*DUE[:\s]*\$?([\d,]+\.?\d*)",
        r"AMOUNT\s*DUE[:\s]*\$?([\d,]+\.?\d*)",
        r"TOTAL[:\s]*\$?([\d,]+\.?\d*)",
        r"GRAND\s*TOTAL[:\s]*\$?([\d,]+\.?\d*)",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            fields["total"] = float(m.group(1).replace(",", ""))
            break

    # PO number — improved: handles PO#, PO Number, PO:, PO-XXXX, Purchase Order
    po = None
    po_patterns = [
        r"P\.?O\.?\s*Number[:\s]*([\w\-]+)",
        r"P\.?O\.?\s*#[:\s]*([\w\-]+)",
        r"Purchase\s*Order\s*(?:No|Number|#)?[:\s]*([\w\-]+)",
        r"\bPO[:\s]+([\w\-]+)",
        r"(PO-[\w\-]+)",
    ]
    for pattern in po_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            # Must be at least 3 chars and not a generic word
            if len(candidate) >= 3 and candidate.upper() not in ["NUMBER", "NO", "NUM", "REF"]:
                po = candidate
                break
    fields["po_number"] = po

    # Tax
    m = re.search(r"Tax[:\s]*\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    fields["tax"] = float(m.group(1).replace(",", "")) if m else 0.0

    # Subtotal
    m = re.search(r"Subtotal[:\s]*\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    fields["subtotal"] = float(m.group(1).replace(",", "")) if m else None

    # Double overcharge detection — scan raw text for keywords
    overcharge_keywords = [
        "double charge", "double overcharge", "charged twice",
        "billed twice", "duplicate charge", "overcharge",
        "double billed", "duplicate line"
    ]
    fields["has_overcharge_flag"] = any(
        kw in text.lower() for kw in overcharge_keywords
    )

    # Defaults
    fields.setdefault("total", 0)
    fields.setdefault("vendor_name", "Unknown")
    fields.setdefault("invoice_number", "INV-UNKNOWN")
    return fields

# ── ANOMALY DETECTION ─────────────────────────────────────────────────────────
def detect_all_anomalies(fields, vendor_memory, seen_invoices):
    anomalies = []
    inv_num  = fields.get("invoice_number", "")
    total    = fields.get("total", 0)
    vendor   = fields.get("vendor_name", "Unknown")
    po       = fields.get("po_number")
    tax      = fields.get("tax", 0)
    subtotal = fields.get("subtotal") or total

    # 1. Duplicate invoice — exact same invoice number
    if inv_num in seen_invoices:
        prev = seen_invoices[inv_num]
        anomalies.append({
            "type": "DUPLICATE_INVOICE", "severity": "HIGH",
            "detail": f"Invoice {inv_num} already processed on {prev['date']}.",
            "action": "REJECT — Do not pay."
        })

    # 2. Double overcharge keyword in invoice text
    if fields.get("has_overcharge_flag"):
        anomalies.append({
            "type": "DOUBLE_OVERCHARGE", "severity": "HIGH",
            "detail": "Invoice text contains double charge / overcharge indicator.",
            "action": "REJECT — Block payment. Request corrected invoice from vendor."
        })

    # 3. Amount significantly above vendor average
    avg = vendor_memory.get("avg_amount")
    if avg and total > avg * 1.15:
        pct = ((total - avg) / avg) * 100
        anomalies.append({
            "type": "AMOUNT_OVERCHARGE", "severity": "HIGH",
            "detail": f"Total ${total:,.2f} is {pct:.1f}% above vendor average ${avg:,.2f}.",
            "action": "HOLD — Draft dispute email."
        })

    # 4. Missing PO number
    if not po or po.strip() == "":
        anomalies.append({
            "type": "MISSING_PO", "severity": "MEDIUM",
            "detail": "No Purchase Order number found on invoice.",
            "action": "HOLD — Request PO number from vendor."
        })

    # 5. High tax rate
    if subtotal and subtotal > 0 and tax:
        rate = (tax / subtotal) * 100
        if rate > 12:
            anomalies.append({
                "type": "TAX_ANOMALY", "severity": "MEDIUM",
                "detail": f"Tax rate is {rate:.1f}% — above standard 8-10%.",
                "action": "VERIFY — Confirm tax rate with vendor."
            })

    # 6. New vendor — no prior history
    if vendor_memory.get("is_new_vendor"):
        anomalies.append({
            "type": "NEW_VENDOR", "severity": "MEDIUM",
            "detail": f"No prior payment history found for {vendor}.",
            "action": "REVIEW — Verify vendor registration and bank details."
        })

    # 7. Partial duplicate — same vendor + same amount, different invoice number
    for seen_num, seen_data in seen_invoices.items():
        if (seen_data.get("vendor") == vendor
                and seen_data.get("amount") == total
                and seen_num != inv_num):
            anomalies.append({
                "type": "PARTIAL_DUPLICATE", "severity": "HIGH",
                "detail": f"Same vendor and amount as invoice {seen_num} but different number.",
                "action": "HOLD — Investigate before paying."
            })
            break

    # 8. Suspiciously round number
    if total > 1000 and total % 500 == 0:
        anomalies.append({
            "type": "ROUND_NUMBER_FLAG", "severity": "LOW",
            "detail": f"Invoice total ${total:,.2f} is a suspiciously round number.",
            "action": "NOTE — Verify all line items."
        })

    return anomalies

# ── DISPUTE EMAIL GENERATOR ───────────────────────────────────────────────────
def generate_dispute_email(vendor, inv_num, total, anomaly):
    email_to = f"billing@{vendor.lower().replace(' ', '')}.com"
    atype = anomaly["type"]
    detail = anomaly["detail"]
    action = anomaly["action"]

    subjects = {
        "DUPLICATE_INVOICE": f"Duplicate Invoice — {inv_num}",
        "DOUBLE_OVERCHARGE": f"Invoice {inv_num} — Double Charge Detected",
        "AMOUNT_OVERCHARGE": f"Invoice {inv_num} — Amount Discrepancy",
        "MISSING_PO":        f"Invoice {inv_num} — PO Number Required",
        "PARTIAL_DUPLICATE": f"Invoice {inv_num} — Possible Duplicate",
    }
    subject = subjects.get(atype, f"Invoice {inv_num} — Review Required")

    return (
        f"To: {email_to}\n"
        f"Subject: {subject}\n\n"
        f"Dear {vendor} Finance Team,\n\n"
        f"We received invoice {inv_num} for ${total:,.2f} and identified the following issue:\n\n"
        f"{detail}\n\n"
        f"Required action: {action}\n\n"
        f"Please respond within 2 business days.\n\n"
        f"Regards,\nAccounts Payable Team"
    )

# ── HINDSIGHT MEMORY ──────────────────────────────────────────────────────────
async def get_vendor_memory(vendor_name):
    memory = {"is_new_vendor": True, "raw_memories": [], "avg_amount": None}
    try:
        r = await hs.arecall(bank_id=BANK, query=f"invoice history for vendor {vendor_name}")
        if r.results:
            memory["is_new_vendor"] = False
            memory["raw_memories"] = [x.text for x in r.results]
            amounts = re.findall(r"\$?([\d,]+\.?\d+)", " ".join(memory["raw_memories"]))
            nums = [float(a.replace(",", "")) for a in amounts if float(a.replace(",", "")) > 100]
            if nums:
                memory["avg_amount"] = sum(nums) / len(nums)
    except Exception as e:
        print(f"  Memory recall error: {e}")
    return memory

# ── DECISION ENGINE ───────────────────────────────────────────────────────────
async def make_decision(fields, anomalies, vendor_memory, filename):
    vendor  = fields.get("vendor_name", "Unknown")
    inv_num = fields.get("invoice_number", "N/A")
    total   = fields.get("total", 0)

    high   = [a for a in anomalies if a["severity"] == "HIGH"]
    medium = [a for a in anomalies if a["severity"] == "MEDIUM"]
    low    = [a for a in anomalies if a["severity"] == "LOW"]

    if high:     status, risk = "REJECTED", "HIGH"
    elif medium: status, risk = "HOLD FOR REVIEW", "MEDIUM"
    elif low:    status, risk = "APPROVED WITH NOTE", "LOW"
    else:        status, risk = "APPROVED", "LOW"

    draft_email = None
    if status in ["REJECTED", "HOLD FOR REVIEW"] and anomalies:
        draft_email = generate_dispute_email(vendor, inv_num, total, anomalies[0])

    # Save to Hindsight memory
    try:
        await hs.aretain(
            bank_id=BANK,
            content=f"Vendor: {vendor}. Invoice: {inv_num}. Total: ${total:,.2f}. Status: {status}. Anomalies: {[a['type'] for a in anomalies]}.",
            context=f"vendor_{vendor.replace(' ', '_')}"
        )
    except Exception as e:
        print(f"  Memory save error: {e}")

    actions = {
        "APPROVED":           "Send payment approval request to finance.",
        "APPROVED WITH NOTE": "Send payment approval with low-risk note.",
        "HOLD FOR REVIEW":    "Show draft dispute email to user for approval.",
        "REJECTED":           "Block payment. Show rejection reason and draft email.",
    }

    return {
        "file": filename,
        "vendor": vendor,
        "invoice_number": inv_num,
        "total": total,
        "status": status,
        "risk": risk,
        "anomaly_count": len(anomalies),
        "anomaly_types": [a["type"] for a in anomalies],
        "anomalies": anomalies,
        "draft_email": draft_email,
        "action": actions.get(status, "Manual review required.")
    }

# ── MAIN AGENT LOOP ───────────────────────────────────────────────────────────
async def run_ap_agent():
    pdf_files = sorted([f for f in os.listdir(DATA_FOLDER) if f.endswith(".pdf")])
    print(f"\nAP AGENT STARTING — {len(pdf_files)} invoices found\n{'─'*50}")

    results = []
    summary = {"APPROVED": 0, "APPROVED WITH NOTE": 0, "HOLD FOR REVIEW": 0, "REJECTED": 0}
    icons   = {"APPROVED": "✅", "APPROVED WITH NOTE": "✅⚠️", "HOLD FOR REVIEW": "⚠️", "REJECTED": "❌"}

    for i, filename in enumerate(pdf_files, 1):
        print(f"[{i:02d}/{len(pdf_files)}] {filename}")
        path = os.path.join(DATA_FOLDER, filename)

        # Fast text-only extraction — no images, no API
        text = extract_text_from_pdf(path)
        if not text.strip():
            print("  SKIP — Could not extract text from PDF")
            continue

        fields        = extract_invoice_fields(text)
        vendor_memory = await get_vendor_memory(fields.get("vendor_name", "Unknown"))
        anomalies     = detect_all_anomalies(fields, vendor_memory, seen_invoices)
        result        = await make_decision(fields, anomalies, vendor_memory, filename)

        # Track invoice for duplicate detection
        seen_invoices[fields.get("invoice_number", "N/A")] = {
            "date":   str(datetime.now().date()),
            "amount": fields.get("total", 0),
            "vendor": fields.get("vendor_name", "Unknown"),
            "file":   filename
        }

        print(f"  {icons.get(result['status'], '?')} {result['status']} | Risk: {result['risk']}")
        for a in anomalies:
            print(f"    → [{a['severity']}] {a['type']}: {a['detail'][:60]}")

        summary[result["status"]] = summary.get(result["status"], 0) + 1
        results.append(result)

        await asyncio.sleep(0.3)  # reduced from 0.5 for speed

    print(f"\n{'─'*50}")
    print(f"DONE — Approved: {summary['APPROVED']} | "
          f"With Note: {summary['APPROVED WITH NOTE']} | "
          f"Hold: {summary['HOLD FOR REVIEW']} | "
          f"Rejected: {summary['REJECTED']}")
    return results

if __name__ == "__main__":
    results = asyncio.run(run_ap_agent())
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ap_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved → {out_path}")
