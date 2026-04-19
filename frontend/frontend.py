
import streamlit as st
import requests

st.set_page_config(page_title="AP Intelligence Agent", page_icon="🧾", layout="wide")

st.markdown("""
<style>
.clean    {background:#e6f4ea;border-left:5px solid #34a853;padding:14px;border-radius:8px;margin:10px 0;color:#000}
.disputed {background:#fce8e6;border-left:5px solid #ea4335;padding:14px;border-radius:8px;margin:10px 0;color:#000}
.review   {background:#fff3cd;border-left:5px solid #ffc107;padding:14px;border-radius:8px;margin:10px 0;color:#000}
.memory   {background:#e8f0fe;border-left:5px solid #4285f4;padding:14px;border-radius:8px;margin:10px 0;color:#000}
.step     {background:#f8f9fa;border:1px solid #dee2e6;padding:10px;border-radius:6px;margin:6px 0;font-size:13px;color:#000}
</style>
""", unsafe_allow_html=True)

API = "https://shindig-washday-moonbeam.ngrok-free.dev"
HEADERS = {"ngrok-skip-browser-warning": "true"}

st.title("🧾 AP Intelligence Agent")
st.caption("Google ADK  •  Hindsight Memory  •  CascadeFlow  •  Groq")
st.divider()

left, right = st.columns([1.1, 1])

with left:
    st.subheader("📤 Upload Invoice")
    TESTS = {
        "Apex Supplies": """Vendor: Apex Supplies Co.
Invoice #: INV-A-0001
PO Number: PO-2026-A1274
TOTAL DUE: $612.90""",
        "BrightMove": """Vendor: BrightMove Freight Ltd.
Invoice #: INV-B-TEST-01
Freight Services: $1,200.00
Fuel Surcharge: $580.00
TOTAL DUE: $2,200.00""",
        "CloudCore": """Vendor: CloudCore Tech Solutions
Invoice #: INV-C-TEST-01
Cloud Subscription: $831.60
TOTAL DUE: $831.60"""
    }
    selected = st.radio("", list(TESTS.keys()) + ["Upload my own PDF"],
                        horizontal=True, label_visibility="collapsed")
    invoice_bytes = None
    invoice_name  = "invoice.txt"
    mime_type     = "text/plain"
    if selected in TESTS:
        st.text_area("Invoice preview:", TESTS[selected], height=160, disabled=True)
        invoice_bytes = TESTS[selected].encode()
    elif selected == "Upload my own PDF":
        uploaded = st.file_uploader("Upload PDF or TXT", type=["pdf","txt"])
        if uploaded:
            invoice_bytes = uploaded.getvalue()
            invoice_name  = uploaded.name
            mime_type     = "application/pdf" if uploaded.name.endswith(".pdf") else "text/plain"
            st.success(f"Ready: {uploaded.name}")
    if invoice_bytes is not None:
        if st.button("🚀 Run Agent Pipeline", type="primary", use_container_width=True):
            with st.spinner("Running 5-step CascadeFlow pipeline..."):
                try:
                    resp = requests.post(f"{API}/process-invoice",
                        files={"file": (invoice_name, invoice_bytes, mime_type)},
                        headers=HEADERS, timeout=120)
                    if resp.status_code == 200:
                        st.session_state["result"] = resp.json()
                        st.rerun()
                    else:
                        st.error(f"Backend error: {resp.text[:200]}")
                except Exception as e:
                    st.error(f"Cannot connect: {e}")
    st.divider()
    st.subheader("🧠 Hindsight Memory Panel")
    try:
        vr = requests.get(f"{API}/vendors", headers=HEADERS, timeout=5)
        vendor_list = vr.json().get("vendors", []) if vr.status_code == 200 else ["Apex Supplies Co.", "BrightMove Freight Ltd.", "CloudCore Tech Solutions"]
    except:
        vendor_list = ["Apex Supplies Co.", "BrightMove Freight Ltd.", "CloudCore Tech Solutions"]
    vendor = st.selectbox("Check vendor history:", vendor_list)
    if st.button("Load Memory", use_container_width=True):
        try:
            r = requests.get(f"{API}/vendor-memory/{vendor}", headers=HEADERS, timeout=30)
            if r.status_code == 200:
                d = r.json()
                st.markdown(f'''<div class="memory"><b>{d["vendor"]}</b><br><br>Dispute rate: <b>{int(d["dispute_rate"]*100)}%</b><br>Avg total: <b>${d["avg_total"]}</b></div>''', unsafe_allow_html=True)
                for m in d.get("memories", []):
                    if m.strip():
                        st.markdown(f"**•** {m[:200]}")
        except Exception as e:
            st.warning(f"Error: {e}")

with right:
    st.subheader("🤖 Agent Decision")
    if "result" not in st.session_state:
        st.info("Select an invoice and click Run Agent Pipeline to start.")
        st.markdown("""
**CascadeFlow Pipeline — 5 Steps:**
**Step 1** — Read invoice
**Step 2** — Check Hindsight memory
**Step 3** — Validate amounts
**Step 4** — Decide CLEAN / DISPUTED / NEEDS REVIEW
**Step 5** — Save to memory
        """)
    else:
        r        = st.session_state["result"]
        decision = r.get("decision", "")
        inv_id   = r.get("invoice_id", "")
        if decision == "CLEAN":
            st.markdown('<div class="clean"><h3 style="margin:0">✅ CLEAN INVOICE</h3><p>No anomalies — safe to pay</p></div>', unsafe_allow_html=True)
        elif decision == "DISPUTED":
            st.markdown('<div class="disputed"><h3 style="margin:0">⚠️ DISPUTED INVOICE</h3><p>Anomaly detected</p></div>', unsafe_allow_html=True)
        elif decision == "NEEDS REVIEW":
            st.markdown('<div class="review"><h3 style="margin:0">🔍 NEW VENDOR — REVIEW NEEDED</h3><p>No history — verify manually</p></div>', unsafe_allow_html=True)
        st.markdown("**Pipeline steps:**")
        step_labels = {"Step1_Read":"Step 1 — Read Invoice","Step2_Memory":"Step 2 — Check Hindsight","Step3_Validate":"Step 3 — Validate","Step4_Decide":"Step 4 — Decision","Step5_Learn":"Step 5 — Save Memory"}
        for step in r.get("steps", []):
            label = next((v for k,v in step_labels.items() if k in step["agent"]), step["agent"])
            st.markdown(f"**{label}**")
            st.markdown(f"> {step['text'][:250]}")
        st.divider()
        if decision == "CLEAN":
            st.markdown("### 💳 Approve Payment?")
            c1, c2 = st.columns(2)
            if c1.button("✅ Approve Payment", type="primary", use_container_width=True):
                requests.post(f"{API}/approve", json={"invoice_id":inv_id,"action":"approve"}, headers=HEADERS, timeout=10)
                st.success("✅ Payment approved!")
                st.balloons()
            if c2.button("⏸ Hold", use_container_width=True):
                st.warning("Held for review.")
        elif decision == "DISPUTED":
            st.markdown("### 📧 Dispute Email")
            draft  = r.get("draft_email", "No draft")
            edited = st.text_area("Edit before sending:", value=draft, height=250)
            c1, c2, c3 = st.columns(3)
            if c1.button("📤 Send Email", type="primary", use_container_width=True):
                requests.post(f"{API}/approve", json={"invoice_id":inv_id,"action":"send_email","edited_email":edited}, headers=HEADERS, timeout=10)
                st.success("✅ Email sent!")
            if c2.button("✏️ Save", use_container_width=True):
                st.info("Saved.")
            if c3.button("💰 Pay Anyway", use_container_width=True):
                requests.post(f"{API}/approve", json={"invoice_id":inv_id,"action":"pay_full"}, headers=HEADERS, timeout=10)
                st.warning("Paid.")
        elif decision == "NEEDS REVIEW":
            st.markdown("### 🔍 Manual Verification")
            st.warning("New vendor — verify all details before approving.")
            c1, c2, c3 = st.columns(3)
            if c1.button("✅ Approve After Review", type="primary", use_container_width=True):
                requests.post(f"{API}/approve", json={"invoice_id":inv_id,"action":"approve_after_review"}, headers=HEADERS, timeout=10)
                st.success("✅ Approved!")
                st.balloons()
            if c2.button("⚠️ Flag", use_container_width=True):
                st.warning("Flagged.")
            if c3.button("❌ Reject", use_container_width=True):
                requests.post(f"{API}/approve", json={"invoice_id":inv_id,"action":"reject"}, headers=HEADERS, timeout=10)
                st.error("Rejected.")
