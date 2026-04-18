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

def extract_invoice_fields(text):
    fields = {}
    for pattern in [r"Invoice\s*#[:\s]*([\w\-]+)", r"INV[:\-\s]*([\w\-]+)"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            fields["invoice_number"] = m.group(1).strip()
            break
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if "INVOICE" in line.upper() and i + 1 < len(lines):
            fields["vendor_name"] = lines[i + 1]
            break
    for pattern in [r"TOTAL\s*DUE[:\s]*\$?([\d,]+\.?\d*)", r"TOTAL[:\s]*\$?([\d,]+\.?\d*)"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            fields["total"] = float(m.group(1).replace(",", ""))
            break
    m = re.search(r"PO\s*(?:Number|#|No)?[:\s]*([\w\-]+)", text, re.IGNORECASE)
    fields["po_number"] = m.group(1).strip() if m else None
    m = re.search(r"Tax[:\s]*\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    fields["tax"] = float(m.group(1).replace(",", "")) if m else 0.0
    m = re.search(r"Subtotal[:\s]*\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    fields["subtotal"] = float(m.group(1).replace(",", "")) if m else None
    fields.setdefault("total", 0)
    fields.setdefault("vendor_name", "Unknown")
    fields.setdefault("invoice_number", "INV-UNKNOWN")
    return fields

def detect_all_anomalies(fields, vendor_memory, seen_invoices):
    anomalies = []
    inv_num  = fields.get("invoice_number", "")
    total    = fields.get("total", 0)
    vendor   = fields.get("vendor_name", "Unknown")
    po       = fields.get("po_number")
    tax      = fields.get("tax", 0)
    subtotal = fields.get("subtotal", total)
    if inv_num in seen_invoices:
        anomalies.append({"type": "DUPLICATE_INVOICE", "severity": "HIGH",
            "detail": f"Invoice {inv_num} already processed on {seen_invoices[inv_num][chr(39)]date[chr(39)]}",
            "action": "REJECT — Do not pay."})
    if vendor_memory.get("avg_amount") and total > vendor_memory["avg_amount"] * 1.15:
        pct = ((total - vendor_memory["avg_amount"]) / vendor_memory["avg_amount"]) * 100
        anomalies.append({"type": "AMOUNT_OVERCHARGE", "severity": "HIGH",
            "detail": f"Total ${total:,.2f} is {pct:.1f}% above vendor average ${vendor_memory[chr(39)]avg_amount[chr(39)]:,.2f}",
            "action": "HOLD — Draft dispute email."})
    if not po or po.strip() == "":
        anomalies.append({"type": "MISSING_PO", "severity": "MEDIUM",
            "detail": "No Purchase Order number found on invoice.",
            "action": "HOLD — Request PO number from vendor."})
    if subtotal and subtotal > 0 and tax:
        rate = (tax / subtotal) * 100
        if rate > 12:
            anomalies.append({"type": "TAX_ANOMALY", "severity": "MEDIUM",
                "detail": f"Tax rate is {rate:.1f}% above standard 8-10%.",
                "action": "VERIFY — Confirm tax rate with vendor."})
    if vendor_memory.get("is_new_vendor"):
        anomalies.append({"type": "NEW_VENDOR", "severity": "MEDIUM",
            "detail": f"No prior history found for {vendor}.",
            "action": "REVIEW — Verify vendor registration."})
    for seen_num, seen_data in seen_invoices.items():
        if seen_data.get("vendor") == vendor and seen_data.get("amount") == total and seen_num != inv_num:
            anomalies.append({"type": "PARTIAL_DUPLICATE", "severity": "HIGH",
                "detail": f"Same vendor and amount as invoice {seen_num} but different number.",
                "action": "HOLD — Investigate before paying."})
            break
    if total > 1000 and total % 500 == 0:
        anomalies.append({"type": "ROUND_NUMBER_FLAG", "severity": "LOW",
            "detail": f"Invoice total ${total:,.2f} is a suspiciously round number.",
            "action": "NOTE — Verify line items."})
    return anomalies

def generate_dispute_email(vendor, inv_num, total, anomaly):
    templates = {
        "DUPLICATE_INVOICE": f"To: billing@{vendor.lower().replace(' ','')}.com\nSubject: Duplicate Invoice — {inv_num}\n\nDear {vendor} Finance Team,\n\nInvoice {inv_num} for ${total:,.2f} appears already processed. Please investigate.\n\nRegards,\nAP Team",
        "AMOUNT_OVERCHARGE": f"To: billing@{vendor.lower().replace(' ','')}.com\nSubject: Invoice {inv_num} — Amount Discrepancy\n\nDear {vendor} Finance Team,\n\n{anomaly[chr(39)]detail[chr(39)]}\n\nPlease review and issue a credit note.\n\nRegards,\nAP Team",
        "MISSING_PO": f"To: billing@{vendor.lower().replace(' ','')}.com\nSubject: Invoice {inv_num} — PO Number Required\n\nDear {vendor} Finance Team,\n\nPlease resubmit with a valid PO number.\n\nRegards,\nAP Team",
    }
    return templates.get(anomaly["type"],
        f"To: billing@{vendor.lower().replace(' ','')}.com\nSubject: Invoice {inv_num} — Review Required\n\nDear {vendor} Finance Team,\n\n{anomaly[chr(39)]detail[chr(39)]}\n\nRegards,\nAP Team")

async def get_vendor_memory(vendor_name):
    memory = {"is_new_vendor": True, "raw_memories": [], "avg_amount": None}
    try:
        r = await hs.arecall(bank_id=BANK, query=f"invoice history for vendor {vendor_name}")
        if r.results:
            memory["is_new_vendor"] = False
            memory["raw_memories"] = [x.text for x in r.results]
            amounts = re.findall(r"\$?([\d,]+\.?\d+)", " ".join(memory["raw_memories"]))
            if amounts:
                nums = [float(a.replace(",","")) for a in amounts if float(a.replace(",","")) > 100]
                if nums:
                    memory["avg_amount"] = sum(nums) / len(nums)
    except Exception as e:
        print(f"  Memory error: {e}")
    return memory

async def make_decision(fields, anomalies, vendor_memory, filename):
    vendor  = fields.get("vendor_name", "Unknown")
    inv_num = fields.get("invoice_number", "N/A")
    total   = fields.get("total", 0)
    high    = [a for a in anomalies if a["severity"] == "HIGH"]
    medium  = [a for a in anomalies if a["severity"] == "MEDIUM"]
    low     = [a for a in anomalies if a["severity"] == "LOW"]
    if high:     status, risk = "REJECTED", "HIGH"
    elif medium: status, risk = "HOLD FOR REVIEW", "MEDIUM"
    elif low:    status, risk = "APPROVED WITH NOTE", "LOW"
    else:        status, risk = "APPROVED", "LOW"
    draft_email = None
    if status in ["REJECTED", "HOLD FOR REVIEW"] and anomalies:
        draft_email = generate_dispute_email(vendor, inv_num, total, anomalies[0])
    try:
        await hs.aretain(bank_id=BANK,
            content=f"Vendor: {vendor}. Invoice: {inv_num}. Total: ${total:,.2f}. Status: {status}. Anomalies: {[a[chr(39)]type[chr(39)] for a in anomalies]}.",
            context=f"vendor_{vendor.replace(' ','_')}")
    except: pass
    actions = {
        "APPROVED": "Send payment approval request to user.",
        "APPROVED WITH NOTE": "Send payment approval with low-risk note to user.",
        "HOLD FOR REVIEW": "Show draft dispute email to user for approval.",
        "REJECTED": "Block payment. Show rejection reason and draft email to user.",
    }
    return {"file": filename, "vendor": vendor, "invoice_number": inv_num,
            "total": total, "status": status, "risk": risk,
            "anomalies": anomalies, "draft_email": draft_email,
            "vendor_memory": vendor_memory, "action_required": actions.get(status, "Manual review.")}

async def run_ap_agent():
    pdf_files = sorted([f for f in os.listdir(DATA_FOLDER) if f.endswith(".pdf")])
    print(f"AP AGENT STARTING — {len(pdf_files)} invoices")
    results = []
    summary = {"APPROVED": 0, "HOLD FOR REVIEW": 0, "REJECTED": 0, "APPROVED WITH NOTE": 0}
    for i, filename in enumerate(pdf_files, 1):
        print(f"[{i:02d}/{len(pdf_files)}] {filename}")
        path = os.path.join(DATA_FOLDER, filename)
        try:
            with pdfplumber.open(path) as pdf:
                text = "\n".join([p.extract_text() or "" for p in pdf.pages])
        except Exception as e:
            print(f"  ERROR: {e}")
            continue
        fields        = extract_invoice_fields(text)
        vendor_memory = await get_vendor_memory(fields.get("vendor_name", "Unknown"))
        anomalies     = detect_all_anomalies(fields, vendor_memory, seen_invoices)
        result        = await make_decision(fields, anomalies, vendor_memory, filename)
        seen_invoices[fields.get("invoice_number", "N/A")] = {
            "date": str(datetime.now().date()),
            "amount": fields.get("total", 0),
            "vendor": fields.get("vendor_name", "Unknown"),
            "file": filename
        }
        icons = {"APPROVED": "✅", "APPROVED WITH NOTE": "✅⚠️", "HOLD FOR REVIEW": "⚠️", "REJECTED": "❌"}
        print(f"  {icons.get(result[chr(39)]status[chr(39)], chr(63))} {result[chr(39)]status[chr(39)]} | Risk: {result[chr(39)]risk[chr(39)]}")
        for a in anomalies:
            print(f"    → [{a[chr(39)]severity[chr(39)]}] {a[chr(39)]type[chr(39)]}")
        summary[result["status"]] = summary.get(result["status"], 0) + 1
        results.append(result)
        await asyncio.sleep(0.5)
    print(f"\nDONE — Approved:{summary[chr(39)]APPROVED[chr(39)]} Hold:{summary[chr(39)]HOLD FOR REVIEW[chr(39)]} Rejected:{summary[chr(39)]REJECTED[chr(39)]}")
    return results

if __name__ == "__main__":
    results = asyncio.run(run_ap_agent())
    os.makedirs("backend", exist_ok=True)
    with open("backend/ap_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Results saved.")
