import nest_asyncio
nest_asyncio.apply()

import os, asyncio, re, io
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pdfplumber
from hindsight_client import Hindsight
from google.adk.agents import Agent, SequentialAgent
from google.adk.tools import FunctionTool
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

# ── App setup ─────────────────────────────────────────────
app = FastAPI(title="AP Intelligence Agent")
app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_methods=["*"],
                   allow_headers=["*"])

# ── 5 Groq keys — rotates automatically when one hits limit ──
GROQ_KEYS = [
    os.getenv("GROQ_API_KEY_1", ""),
    os.getenv("GROQ_API_KEY_2", ""),
    os.getenv("GROQ_API_KEY_3", ""),
    os.getenv("GROQ_API_KEY_4", ""),
    os.getenv("GROQ_API_KEY_5", ""),
]
GROQ_KEYS = [k for k in GROQ_KEYS if k]
print(f"Loaded {len(GROQ_KEYS)} Groq keys")

current_key = [0]
os.environ["GROQ_API_KEY"] = GROQ_KEYS[0] if GROQ_KEYS else ""
MODEL = LiteLlm(model="groq/llama-3.3-70b-versatile")

BANK = "ap-memory-v2"

# ── Hindsight client ──────────────────────────────────────
hs = Hindsight(
    base_url=os.getenv("HINDSIGHT_BASE_URL"),
    api_key=os.getenv("HINDSIGHT_API_KEY")
)

# ── Vendor baseline data ──────────────────────────────────
VENDORS = {
    "Apex Supplies Co.": {
        "avg_total":    700.0,
        "dispute_rate": 0.10,
        "template":     "standard_dispute_v1"
    },
    "BrightMove Freight Ltd.": {
        "avg_freight":  200.0,
        "avg_total":    1580.0,
        "dispute_rate": 0.20,
        "template":     "freight_dispute_v2"
    },
    "CloudCore Tech Solutions": {
        "avg_total":    831.60,
        "dispute_rate": 0.05,
        "template":     "standard_dispute_v1"
    },
}

counter = [0]
store   = {}


# ═════════════════════════════════════════════════════════
# TOOLS
# ═════════════════════════════════════════════════════════

def parse_invoice(invoice_text: str) -> dict:
    """Step 1 — extract fields from invoice text"""
    lines   = [l.strip() for l in invoice_text.split("\n") if l.strip()]
    vendor  = "Unknown Vendor"
    for i, line in enumerate(lines):
        if "INVOICE" in line.upper() and i + 1 < len(lines):
            vendor = lines[i + 1]
            break

    vendor_match  = re.search(r"Vendor[:\s]+(.+)",                    invoice_text)
    inv_num       = re.search(r"Invoice[\s#]*(?:Number)?[:\s]+(\S+)", invoice_text)
    po_num        = re.search(r"PO[\s#]*(?:Number)?[:\s]+(\S+)",      invoice_text)
    freight       = re.search(r"[Ff]reight[^\d$]*\$?([\d,]+\.?\d*)",  invoice_text)
    total         = re.search(r"TOTAL\s*DUE[:\s]*\$?([\d,]+\.?\d*)",  invoice_text)

    if vendor_match:
        vendor = vendor_match.group(1).strip()

    amounts = []
    for a in re.findall(r"\$?([\d,]+\.?\d*)", invoice_text):
        try:
            val = float(a.replace(",", ""))
            if val > 100:
                amounts.append(val)
        except:
            pass

    total_amount = float(total.group(1).replace(",", "")) if total else (max(amounts) if amounts else 0.0)

    return {
        "vendor":         vendor,
        "invoice_number": inv_num.group(1).strip() if inv_num else "INV-UNKNOWN",
        "po_number":      po_num.group(1).strip()  if po_num  else "MISSING",
        "total_amount":   total_amount,
        "freight_charge": float(freight.group(1).replace(",", "")) if freight else 0.0,
    }


def check_memory(vendor_name: str) -> str:
    """Step 2 — recall vendor history from Hindsight"""
    async def _run():
        try:
            results = await hs.arecall(
                bank_id=BANK,
                query=f"invoice history disputes patterns for vendor {vendor_name}"
            )
            if results.results:
                memories = "\n".join([r.text for r in results.results[:4]])
                return f"Memory found for {vendor_name}:\n{memories}"
            return f"No history found for {vendor_name}. This is a new vendor."
        except Exception:
            return f"Memory temporarily unavailable for {vendor_name}. Processing without history."
    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception:
        return f"Memory check skipped for {vendor_name}."


def check_anomalies(vendor_name: str,
                    total_amount: float,
                    freight_charge: float) -> dict:
    """Step 3 — check if amounts are suspicious"""
    v = VENDORS.get(vendor_name, {})

    if not v:
        return {
            "status": "NEW_VENDOR",
            "anomalies": [{
                "type": "new_vendor",
                "message": (
                    f"{vendor_name} is a new vendor with no baseline yet. "
                    f"Invoice total ${total_amount} requires manual verification. "
                    f"After approval, this becomes the baseline for future invoices."
                )
            }]
        }

    anomalies = []
    if freight_charge > 0 and "avg_freight" in v:
        avg = v["avg_freight"]
        if freight_charge > avg * 1.10:
            delta = round(freight_charge - avg, 2)
            pct   = round((freight_charge / avg - 1) * 100)
            anomalies.append({
                "type":     "freight_overcharge",
                "expected": avg,
                "actual":   freight_charge,
                "delta":    delta,
                "message":  f"Freight ${freight_charge} is {pct}% above average ${avg}. Overcharge: ${delta}"
            })

    avg_t = v["avg_total"]
    if total_amount > avg_t * 1.20:
        delta = round(total_amount - avg_t, 2)
        pct   = round((total_amount / avg_t - 1) * 100)
        anomalies.append({
            "type":     "total_overcharge",
            "expected": avg_t,
            "actual":   total_amount,
            "delta":    delta,
            "message":  f"Total ${total_amount} is {pct}% above average ${avg_t}. Overcharge: ${delta}"
        })

    return {"status": "ANOMALIES_FOUND" if anomalies else "CLEAN",
            "anomalies": anomalies}


def draft_dispute_email(vendor_name: str,
                         issue_description: str,
                         expected_amount: float,
                         actual_amount: float) -> str:
    """Step 4 — write dispute email"""
    delta    = round(actual_amount - expected_amount, 2)
    template = VENDORS.get(vendor_name, {}).get("template", "standard_v1")
    return f"""DRAFT EMAIL | Template: {template}
---
To: billing@{vendor_name.lower().replace(" ", "").replace(".", "")}.com
Subject: Invoice Discrepancy — Charge Review Required

Dear {vendor_name} Billing Team,

We reviewed your recent invoice and found a discrepancy in {issue_description}.

  Expected  : ${expected_amount:,.2f}
  Billed    : ${actual_amount:,.2f}
  Difference: ${delta:,.2f}

Please issue a credit of ${delta:,.2f}.

Thank you,
Accounts Payable Team
---
END DRAFT"""


def save_to_memory(vendor_name: str,
                    invoice_number: str,
                    outcome: str,
                    template_used: str,
                    user_edited: str = "false") -> str:
    """Step 5 — save outcome to Hindsight"""
    user_edited_bool = str(user_edited).lower() not in ("false", "0", "no", "")

    if vendor_name not in VENDORS:
        VENDORS[vendor_name] = {
            "avg_total":    0,
            "dispute_rate": 0,
            "template":     "standard_dispute_v1"
        }

    async def _run():
        try:
            await hs.aretain(
                bank_id=BANK,
                content=(
                    f"Vendor: {vendor_name}. "
                    f"Invoice: {invoice_number}. "
                    f"Outcome: {outcome}. "
                    f"Template: {template_used}. "
                    f"User edited: {user_edited_bool}."
                ),
                context=f"vendor_{vendor_name.replace(' ', '_')}"
            )
            return f"Memory saved for {vendor_name}."
        except Exception:
            return "Memory save skipped (server busy) — invoice processed successfully."
    try:
        return asyncio.get_event_loop().run_until_complete(_run())
    except Exception:
        return "Memory save skipped — invoice processed successfully."


# ═════════════════════════════════════════════════════════
# CASCADEFLOW PIPELINE
# ═════════════════════════════════════════════════════════

def build_pipeline(pid: str):
    s1 = Agent(
        name=f"Step1_Read_{pid}", model=MODEL,
        instruction=(
            "Call parse_invoice with the full invoice text. "
            "Return all extracted fields: vendor, invoice number, "
            "PO number, total amount, freight charge."
        ),
        tools=[FunctionTool(parse_invoice)]
    )
    s2 = Agent(
        name=f"Step2_Memory_{pid}", model=MODEL,
        instruction=(
            "Take the vendor name from Step 1. Call check_memory with it. "
            "Report what Hindsight remembers about this vendor. "
            "If no history found, clearly state this is a new vendor."
        ),
        tools=[FunctionTool(check_memory)]
    )
    s3 = Agent(
        name=f"Step3_Validate_{pid}", model=MODEL,
        instruction=(
            "Take vendor name, total amount, freight charge from Step 1. "
            "Call check_anomalies with them. "
            "Report CLEAN, list anomalies found, or state NEW_VENDOR."
        ),
        tools=[FunctionTool(check_anomalies)]
    )
    s4 = Agent(
        name=f"Step4_Decide_{pid}", model=MODEL,
        instruction="""
        Look at all previous steps and decide:

        If the vendor status is NEW_VENDOR:
          Write exactly: DECISION: NEEDS REVIEW
          Write: REQUEST TO USER: This is a new vendor with no payment history.
          List all extracted invoice details clearly.

        If NO anomalies found AND vendor is known:
          Write exactly: DECISION: CLEAN
          Write: REQUEST TO USER: Approve payment of $[amount] to [vendor]

        If anomalies found:
          Write exactly: DECISION: DISPUTED
          Call draft_dispute_email with vendor name, issue description,
          expected amount, actual amount.
          Show the full draft email.
          Write: REQUEST TO USER: Reply SEND EDIT or PAY

        Always explain reasoning using vendor memory from Step 2.
        """,
        tools=[FunctionTool(draft_dispute_email)]
    )
    s5 = Agent(
        name=f"Step5_Learn_{pid}", model=MODEL,
        instruction=(
            "Call save_to_memory with vendor name, invoice number, "
            "what decision was made, template used (or 'none' if clean), "
            "and 'false' for user_edited. Confirm memory saved."
        ),
        tools=[FunctionTool(save_to_memory)]
    )
    return SequentialAgent(
        name=f"CascadeFlow_{pid}",
        sub_agents=[s1, s2, s3, s4, s5]
    )


# ═════════════════════════════════════════════════════════
# API ROUTES
# ═════════════════════════════════════════════════════════

class ApproveRequest(BaseModel):
    invoice_id:   str
    action:       str
    edited_email: str = ""


@app.post("/process-invoice")
async def process_invoice(file: UploadFile = File(...)):
    global MODEL

    raw = await file.read()
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            text = "\n".join([p.extract_text() or "" for p in pdf.pages])
    except:
        text = raw.decode("utf-8", errors="ignore")

    if not text.strip():
        return {"error": "Could not read invoice file"}

    counter[0] += 1
    pid = str(counter[0])

    steps     = []
    full_text = ""

    for attempt in range(max(len(GROQ_KEYS), 1)):
        try:
            pipeline = build_pipeline(f"{pid}_{attempt}")
            svc      = InMemorySessionService()
            runner   = Runner(agent=pipeline, app_name="ap", session_service=svc)
            await svc.create_session(app_name="ap", user_id="u", session_id=f"{pid}_{attempt}")

            msg = Content(role="user", parts=[Part(text=f"Process this invoice:\n\n{text}")])

            steps     = []
            full_text = ""

            async for event in runner.run_async(
                user_id="u",
                session_id=f"{pid}_{attempt}",
                new_message=msg
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            steps.append({"agent": event.author, "text": part.text})
                            full_text += part.text + "\n"

            if steps:
                break

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate_limit" in error_msg.lower():
                if len(GROQ_KEYS) > 1:
                    current_key[0] = (current_key[0] + 1) % len(GROQ_KEYS)
                    new_key = GROQ_KEYS[current_key[0]]
                    os.environ["GROQ_API_KEY"] = new_key
                    MODEL = LiteLlm(model="groq/llama-3.3-70b-versatile")
                    print(f"Rotated to key {current_key[0] + 1}")
                else:
                    raise e
            else:
                raise e

    if "DECISION: DISPUTED" in full_text:
        decision = "DISPUTED"
    elif "DECISION: NEEDS REVIEW" in full_text:
        decision = "NEEDS REVIEW"
    else:
        decision = "CLEAN"

    draft = ""
    if "DRAFT EMAIL" in full_text:
        s     = full_text.find("DRAFT EMAIL")
        e     = full_text.find("END DRAFT", s)
        draft = full_text[s:e + 9] if e != -1 else full_text[s:s + 700]

    result = {
        "invoice_id":  pid,
        "decision":    decision,
        "steps":       steps,
        "draft_email": draft,
        "full_output": full_text
    }
    store[pid] = result
    return result


@app.post("/approve")
async def approve(req: ApproveRequest):
    return {"status": "recorded", "action": req.action, "invoice_id": req.invoice_id}


@app.get("/vendors")
def get_vendors():
    return {"vendors": list(VENDORS.keys())}


@app.get("/vendor-memory/{vendor_name}")
async def vendor_memory(vendor_name: str):
    results = await hs.arecall(
        bank_id=BANK,
        query=f"all invoice history for vendor {vendor_name}"
    )
    v = VENDORS.get(vendor_name, {})
    return {
        "vendor":       vendor_name,
        "dispute_rate": v.get("dispute_rate", 0),
        "avg_freight":  v.get("avg_freight",  0),
        "avg_total":    v.get("avg_total",    0),
        "memories":     [r.text for r in results.results[:6]] if results.results else []
    }


@app.get("/health")
def health():
    return {"status": "ok"}