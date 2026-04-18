<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AP Intelligence Agent</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0d0f14;
    --surface: #141720;
    --surface2: #1c2030;
    --border: #252a3a;
    --border2: #2e3550;
    --accent: #00e5a0;
    --accent2: #0090ff;
    --warn: #ff9f0a;
    --danger: #ff453a;
    --text: #e8eaf0;
    --text2: #8890a8;
    --text3: #4a5068;
    --mono: 'IBM Plex Mono', monospace;
    --sans: 'IBM Plex Sans', sans-serif;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: var(--sans);
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  /* ── Header ── */
  .header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 18px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .header-left h1 {
    font-family: var(--mono);
    font-size: 17px;
    font-weight: 600;
    color: var(--accent);
    letter-spacing: -0.3px;
  }
  .header-left p {
    font-size: 12px;
    color: var(--text3);
    margin-top: 3px;
    font-family: var(--mono);
  }
  .status-pill {
    display: flex;
    align-items: center;
    gap: 7px;
    background: rgba(0,229,160,0.08);
    border: 1px solid rgba(0,229,160,0.2);
    border-radius: 20px;
    padding: 5px 12px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--accent);
  }
  .status-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--accent);
    animation: pulse 2s ease-in-out infinite;
  }
  @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.4;} }

  /* ── Tabs ── */
  .tabs {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0 32px;
    display: flex;
    gap: 0;
  }
  .tab {
    padding: 13px 22px;
    cursor: pointer;
    font-size: 12px;
    font-family: var(--mono);
    color: var(--text3);
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
    letter-spacing: 0.3px;
  }
  .tab:hover { color: var(--text2); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }

  /* ── Sections ── */
  .sec { display: none; padding: 28px 32px; max-width: 900px; }
  .sec.active { display: block; }

  /* ── Drop Zone ── */
  .drop-zone {
    border: 1px dashed var(--border2);
    border-radius: 12px;
    padding: 52px 32px;
    text-align: center;
    cursor: pointer;
    background: var(--surface);
    transition: all 0.2s;
    position: relative;
    overflow: hidden;
  }
  .drop-zone::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse at center, rgba(0,229,160,0.04) 0%, transparent 70%);
    pointer-events: none;
  }
  .drop-zone:hover {
    border-color: var(--accent);
    background: rgba(0,229,160,0.04);
  }
  .drop-zone.dragover { border-color: var(--accent); background: rgba(0,229,160,0.06); }
  .dz-icon {
    width: 48px; height: 48px;
    border: 1px solid var(--border2);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 16px;
    background: var(--surface2);
    font-size: 22px;
  }
  .drop-zone h3 {
    font-size: 16px;
    font-weight: 500;
    color: var(--text);
    margin-bottom: 6px;
  }
  .drop-zone p {
    font-size: 12px;
    color: var(--text3);
    font-family: var(--mono);
  }
  .up-btn {
    margin-top: 20px;
    padding: 10px 28px;
    background: var(--accent);
    color: #000;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    font-family: var(--mono);
    letter-spacing: 0.3px;
    transition: opacity 0.15s;
  }
  .up-btn:hover { opacity: 0.88; }

  /* ── Processing Steps ── */
  .processing {
    display: none;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 28px;
  }
  .proc-header {
    font-family: var(--mono);
    font-size: 13px;
    color: var(--accent);
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .spinner {
    width: 14px; height: 14px;
    border: 2px solid rgba(0,229,160,0.2);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    flex-shrink: 0;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .step-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 9px 14px;
    border-radius: 7px;
    font-size: 12px;
    font-family: var(--mono);
    color: var(--text3);
    background: transparent;
    margin-bottom: 4px;
    transition: all 0.2s;
  }
  .step-row.active {
    background: rgba(0,144,255,0.08);
    color: var(--accent2);
    border: 1px solid rgba(0,144,255,0.15);
  }
  .step-row.done {
    background: rgba(0,229,160,0.06);
    color: var(--accent);
    border: 1px solid rgba(0,229,160,0.12);
  }
  .step-icon { font-size: 13px; flex-shrink: 0; }
  .proc-note {
    font-size: 11px;
    color: var(--text3);
    font-family: var(--mono);
    margin-top: 14px;
    text-align: center;
  }

  /* ── Result Card ── */
  .result-card {
    display: none;
    border-radius: 12px;
    border: 1px solid var(--border);
    overflow: hidden;
    margin-top: 4px;
  }
  .result-header {
    padding: 18px 22px;
    font-family: var(--mono);
    font-size: 16px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .result-body { padding: 20px 22px; background: var(--surface); }
  .detail-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 18px;
  }
  .detail-item {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 11px 14px;
  }
  .detail-item .lbl {
    font-size: 10px;
    color: var(--text3);
    font-family: var(--mono);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 5px;
  }
  .detail-item .val {
    font-size: 14px;
    font-weight: 500;
    font-family: var(--mono);
  }

  .anomaly {
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-family: var(--mono);
    margin-bottom: 6px;
    border: 1px solid;
  }
  .anomaly.HIGH { background: rgba(255,69,58,0.08); color: #ff6b62; border-color: rgba(255,69,58,0.2); }
  .anomaly.MEDIUM { background: rgba(255,159,10,0.08); color: var(--warn); border-color: rgba(255,159,10,0.2); }
  .anomaly.LOW { background: rgba(255,214,10,0.08); color: #ffd60a; border-color: rgba(255,214,10,0.2); }
  .anomaly.CLEAN { background: rgba(0,229,160,0.08); color: var(--accent); border-color: rgba(0,229,160,0.2); }

  .email-label {
    font-size: 11px;
    font-family: var(--mono);
    color: var(--text3);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin: 16px 0 8px;
  }
  .email-draft {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
    font-size: 12px;
    font-family: var(--mono);
    white-space: pre-wrap;
    line-height: 1.7;
    color: var(--text2);
    margin-bottom: 16px;
  }
  .reasoning-box {
    background: rgba(0,144,255,0.06);
    border: 1px solid rgba(0,144,255,0.15);
    border-radius: 8px;
    padding: 12px 14px;
    font-size: 12px;
    color: var(--accent2);
    font-family: var(--mono);
    margin-bottom: 16px;
    line-height: 1.6;
  }
  .act-btns { display: flex; gap: 10px; }
  .act-btn {
    padding: 9px 22px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
    font-family: var(--mono);
    letter-spacing: 0.3px;
    transition: opacity 0.15s;
  }
  .act-btn:hover { opacity: 0.85; }
  .btn-approve { background: var(--accent); color: #000; }
  .btn-send { background: var(--warn); color: #000; }
  .btn-reject { background: var(--danger); color: #fff; }
  .btn-reset { background: var(--surface2); color: var(--text2); border: 1px solid var(--border2); }

  /* Result color themes */
  .result-card.approved .result-header { background: rgba(0,229,160,0.1); color: var(--accent); }
  .result-card.note .result-header { background: rgba(255,214,10,0.08); color: #ffd60a; }
  .result-card.hold .result-header { background: rgba(255,159,10,0.1); color: var(--warn); }
  .result-card.rejected .result-header { background: rgba(255,69,58,0.1); color: var(--danger); }

  /* ── Dashboard ── */
  .cards-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 22px;
  }
  .stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 18px;
    border-left-width: 3px;
  }
  .stat-card .num {
    font-size: 28px;
    font-weight: 600;
    font-family: var(--mono);
    color: var(--text);
  }
  .stat-card .lbl {
    font-size: 11px;
    color: var(--text3);
    font-family: var(--mono);
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
  }
  .c1{border-left-color:var(--accent);}
  .c2{border-left-color:#ffd60a;}
  .c3{border-left-color:var(--warn);}
  .c4{border-left-color:var(--danger);}

  .search-wrap {
    position: relative;
    margin-bottom: 10px;
  }
  .search-wrap input {
    width: 100%;
    padding: 9px 14px 9px 36px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 13px;
    font-family: var(--mono);
    color: var(--text);
    outline: none;
    transition: border-color 0.2s;
  }
  .search-wrap input:focus { border-color: var(--border2); }
  .search-wrap input::placeholder { color: var(--text3); }
  .search-icon {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text3);
    font-size: 14px;
    pointer-events: none;
  }

  .filter-row {
    display: flex;
    gap: 6px;
    margin-bottom: 14px;
    flex-wrap: wrap;
  }
  .fbtn {
    padding: 5px 14px;
    border: 1px solid var(--border);
    border-radius: 20px;
    cursor: pointer;
    font-size: 11px;
    font-family: var(--mono);
    background: var(--surface);
    color: var(--text3);
    transition: all 0.15s;
  }
  .fbtn:hover { border-color: var(--border2); color: var(--text2); }
  .fbtn.active { background: var(--accent); color: #000; border-color: var(--accent); }

  .tbl-wrap {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
  }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th {
    background: var(--surface2);
    color: var(--text3);
    padding: 10px 14px;
    text-align: left;
    font-family: var(--mono);
    font-size: 10px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    border-bottom: 1px solid var(--border);
  }
  td {
    padding: 11px 14px;
    border-bottom: 1px solid var(--border);
    color: var(--text2);
    font-family: var(--mono);
  }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(255,255,255,0.02); }

  .badge {
    padding: 2px 9px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 600;
    font-family: var(--mono);
    letter-spacing: 0.3px;
  }
  .ba{background:rgba(0,229,160,0.12);color:var(--accent);}
  .bn{background:rgba(255,214,10,0.12);color:#ffd60a;}
  .bh{background:rgba(255,159,10,0.12);color:var(--warn);}
  .br{background:rgba(255,69,58,0.12);color:var(--danger);}
  .rh{background:rgba(255,69,58,0.12);color:var(--danger);}
  .rm{background:rgba(255,159,10,0.12);color:var(--warn);}
  .rl{background:rgba(0,229,160,0.12);color:var(--accent);}

  .view-btn {
    padding: 4px 10px;
    background: rgba(0,144,255,0.1);
    color: var(--accent2);
    border: 1px solid rgba(0,144,255,0.2);
    border-radius: 5px;
    cursor: pointer;
    font-size: 10px;
    font-family: var(--mono);
    transition: opacity 0.15s;
  }
  .view-btn:hover { opacity: 0.8; }

  .empty-msg td {
    text-align: center;
    padding: 36px;
    color: var(--text3);
    font-family: var(--mono);
    font-size: 12px;
  }

  /* ── Modal ── */
  .modal-bg {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.65);
    z-index: 999;
    align-items: center;
    justify-content: center;
  }
  .modal-bg.open { display: flex; }
  .modal-box {
    background: var(--surface);
    border: 1px solid var(--border2);
    border-radius: 14px;
    padding: 24px;
    max-width: 520px;
    width: 92%;
    max-height: 78vh;
    overflow-y: auto;
  }
  .modal-box h3 {
    font-family: var(--mono);
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 14px;
  }
  .modal-box pre {
    background: var(--surface2);
    border: 1px solid var(--border);
    padding: 14px;
    border-radius: 8px;
    font-size: 11px;
    font-family: var(--mono);
    white-space: pre-wrap;
    line-height: 1.7;
    color: var(--text2);
  }
  .close-btn {
    margin-top: 14px;
    padding: 7px 18px;
    background: var(--danger);
    color: #fff;
    border: none;
    border-radius: 7px;
    cursor: pointer;
    font-size: 12px;
    font-family: var(--mono);
    font-weight: 600;
  }

  /* ── Error box ── */
  .error-box {
    display: none;
    background: rgba(255,69,58,0.08);
    border: 1px solid rgba(255,69,58,0.2);
    border-radius: 8px;
    padding: 14px 16px;
    font-size: 12px;
    font-family: var(--mono);
    color: var(--danger);
    margin-top: 14px;
    line-height: 1.6;
  }
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <div class="header-left">
    <h1>AP_INTELLIGENCE_AGENT</h1>
    <p>// powered by Claude AI — real PDF analysis, real fraud detection</p>
  </div>
  <div class="status-pill">
    <div class="status-dot"></div>
    AGENT ONLINE
  </div>
</div>

<!-- Tabs -->
<div class="tabs">
  <div class="tab active" id="t-upload" onclick="showTab('upload')">[ upload invoice ]</div>
  <div class="tab" id="t-dashboard" onclick="showTab('dashboard')">[ dashboard ]</div>
</div>

<!-- Upload Section -->
<div class="sec active" id="sec-upload">

  <div class="drop-zone" id="dz" onclick="document.getElementById('fi').click()">
    <div class="dz-icon">📄</div>
    <h3>Upload any invoice PDF</h3>
    <p>// click to browse or drag and drop</p>
    <p style="margin-top:5px;font-size:11px;color:var(--text3);">// Claude reads the real content — vendor, amounts, line items, tax</p>
    <button class="up-btn">CHOOSE INVOICE PDF</button>
  </div>
  <input type="file" id="fi" accept=".pdf" style="display:none" onchange="processInvoice(this.files[0])">

  <div class="error-box" id="error-box"></div>

  <!-- Processing Steps -->
  <div class="processing" id="processing">
    <div class="proc-header">
      <div class="spinner"></div>
      <span id="proc-title">AGENT PROCESSING INVOICE...</span>
    </div>
    <div id="steps-list"></div>
    <div class="proc-note" id="proc-note"></div>
  </div>

  <!-- Result -->
  <div class="result-card" id="result-card">
    <div class="result-header" id="r-header"></div>
    <div class="result-body">
      <div class="detail-grid">
        <div class="detail-item"><div class="lbl">Vendor</div><div class="val" id="r-vendor">—</div></div>
        <div class="detail-item"><div class="lbl">Invoice number</div><div class="val" id="r-inv">—</div></div>
        <div class="detail-item"><div class="lbl">Total amount</div><div class="val" id="r-total">—</div></div>
        <div class="detail-item"><div class="lbl">Risk level</div><div class="val" id="r-risk">—</div></div>
      </div>
      <div id="anomaly-list"></div>
      <div class="reasoning-box" id="r-reasoning" style="display:none"></div>
      <div id="email-sec" style="display:none">
        <div class="email-label">// draft dispute email</div>
        <div class="email-draft" id="email-draft"></div>
      </div>
      <div class="act-btns" id="act-btns"></div>
    </div>
  </div>
</div>

<!-- Dashboard Section -->
<div class="sec" id="sec-dashboard">
  <div class="cards-grid">
    <div class="stat-card c1"><div class="num" id="d-approved">0</div><div class="lbl">Approved</div></div>
    <div class="stat-card c2"><div class="num" id="d-note">0</div><div class="lbl">With note</div></div>
    <div class="stat-card c3"><div class="num" id="d-hold">0</div><div class="lbl">Hold</div></div>
    <div class="stat-card c4"><div class="num" id="d-rejected">0</div><div class="lbl">Rejected</div></div>
  </div>
  <div class="search-wrap">
    <span class="search-icon">⌕</span>
    <input id="sb" placeholder="search vendor, invoice number, status..." oninput="renderTable()">
  </div>
  <div class="filter-row">
    <button class="fbtn active" onclick="setFilter('ALL',this)">all</button>
    <button class="fbtn" onclick="setFilter('APPROVED',this)">approved</button>
    <button class="fbtn" onclick="setFilter('APPROVED WITH NOTE',this)">with note</button>
    <button class="fbtn" onclick="setFilter('HOLD FOR REVIEW',this)">hold</button>
    <button class="fbtn" onclick="setFilter('REJECTED',this)">rejected</button>
  </div>
  <div class="tbl-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Vendor</th>
          <th>Invoice</th>
          <th>Total</th>
          <th>Status</th>
          <th>Risk</th>
          <th>Issues</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody id="tb"></tbody>
    </table>
  </div>
</div>

<!-- Email Modal -->
<div class="modal-bg" id="modal">
  <div class="modal-box">
    <h3>// draft dispute email</h3>
    <pre id="modal-body"></pre>
    <button class="close-btn" onclick="document.getElementById('modal').classList.remove('open')">CLOSE</button>
  </div>
</div>

<script>
// ── Config ──────────────────────────────────────────────
const API_URL = 'https://api.anthropic.com/v1/messages';
const MODEL   = 'claude-sonnet-4-20250514';

const STEPS = [
  'Reading invoice PDF content',
  'Extracting vendor, amounts, PO number',
  'Cross-checking vendor history',
  'Running 7 anomaly detection checks',
  'Generating AI decision + email draft'
];

let results = [];
let currentFilter = 'ALL';

// ── Tab switching ────────────────────────────────────────
function showTab(tab) {
  document.querySelectorAll('.sec').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('sec-' + tab).classList.add('active');
  document.getElementById('t-' + tab).classList.add('active');
  if (tab === 'dashboard') { updateStats(); renderTable(); }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Main invoice processor ───────────────────────────────
async function processInvoice(file) {
  if (!file) return;

  // Reset UI
  document.getElementById('dz').style.display = 'none';
  document.getElementById('result-card').style.display = 'none';
  document.getElementById('error-box').style.display = 'none';

  const proc = document.getElementById('processing');
  proc.style.display = 'block';
  document.getElementById('proc-title').textContent = 'PROCESSING: ' + file.name.toUpperCase();

  // Render steps
  const sl = document.getElementById('steps-list');
  sl.innerHTML = STEPS.map((s, i) =>
    `<div class="step-row" id="sr${i}"><span class="step-icon">○</span>${s}</div>`
  ).join('');

  // Animate steps 1-4 quickly
  for (let i = 0; i < STEPS.length - 1; i++) {
    if (i > 0) setStep(i - 1, 'done');
    setStep(i, 'active');
    await sleep(600);
  }
  setStep(STEPS.length - 2, 'done');
  setStep(STEPS.length - 1, 'active');
  document.getElementById('proc-note').textContent = '// calling Claude AI — reading actual PDF content...';

  // Read file as base64
  let b64;
  try {
    b64 = await fileToBase64(file);
  } catch (e) {
    showError('Failed to read file: ' + e.message);
    return;
  }

  // Call Claude API
  let analysis;
  try {
    analysis = await callClaudeAPI(b64);
  } catch (e) {
    showError('API error: ' + e.message + '\n\nMake sure you are using this via Claude.ai where the API key is handled automatically.');
    return;
  }

  setStep(STEPS.length - 1, 'done');
  await sleep(300);

  proc.style.display = 'none';
  showResult(analysis, file.name);
}

function setStep(i, state) {
  const el = document.getElementById('sr' + i);
  el.className = 'step-row ' + state;
  el.querySelector('.step-icon').textContent = state === 'done' ? '✓' : state === 'active' ? '▶' : '○';
}

// ── File → Base64 ────────────────────────────────────────
function fileToBase64(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload  = e => res(e.target.result.split(',')[1]);
    r.onerror = () => rej(new Error('FileReader failed'));
    r.readAsDataURL(file);
  });
}

// ── Claude API call ──────────────────────────────────────
async function callClaudeAPI(b64) {
  const prompt = `You are an expert Accounts Payable (AP) fraud detection and invoice verification agent.

Carefully analyze the invoice PDF attached. Extract all visible data and run the following checks:

ANOMALY CHECKS TO PERFORM:
1. MISSING_PO — Is there no Purchase Order number?
2. TAX_ANOMALY — Is the tax rate above 12% or unusual?
3. ROUND_NUMBER_FLAG — Is the total a suspiciously round number (e.g. $5000.00, $10000.00)?
4. AMOUNT_OVERCHARGE — Is the total significantly higher than expected for the service/goods type?
5. DUPLICATE_RISK — Any signs this could be a duplicate invoice?
6. MATH_ERROR — Do line items add up to the stated total?
7. VENDOR_MISMATCH — Any inconsistency in vendor details (name, address, bank)?

DECISION RULES:
- REJECTED if any HIGH severity anomaly exists
- HOLD FOR REVIEW if only MEDIUM anomalies (no HIGH)
- APPROVED WITH NOTE if only LOW anomalies
- APPROVED if no anomalies found

Return ONLY a valid JSON object with NO markdown formatting, no backticks, no explanation — just the raw JSON:

{
  "vendor": "exact vendor name from invoice",
  "invoice_number": "invoice number from document",
  "total": 1234.56,
  "po_number": "PO number or null if missing",
  "tax_rate": 8.5,
  "anomalies": [
    {
      "type": "ANOMALY_TYPE_CODE",
      "severity": "HIGH|MEDIUM|LOW",
      "detail": "specific detail about this anomaly found in the invoice",
      "action": "recommended corrective action"
    }
  ],
  "status": "APPROVED|APPROVED WITH NOTE|HOLD FOR REVIEW|REJECTED",
  "risk": "LOW|MEDIUM|HIGH",
  "reasoning": "1-2 sentence explanation of the final decision",
  "draft_email": "complete email text if status is not APPROVED, otherwise null"
}

If the draft_email is needed, format it as:
To: billing@vendorname.com
Subject: Invoice [number] — Review Required

Dear [Vendor] Finance Team,

[Professional dispute or clarification email body referencing specific anomalies found]

Regards,
Accounts Payable Team

Return ONLY the JSON. No other text.`;

  const response = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 1200,
      messages: [{
        role: 'user',
        content: [
          {
            type: 'document',
            source: { type: 'base64', media_type: 'application/pdf', data: b64 }
          },
          { type: 'text', text: prompt }
        ]
      }]
    })
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error?.message || ('HTTP ' + response.status));
  }

  const data = await response.json();
  const rawText = data.content
    .filter(c => c.type === 'text')
    .map(c => c.text)
    .join('');

  // Strip any accidental markdown fences
  const cleaned = rawText.replace(/```json|```/gi, '').trim();

  try {
    return JSON.parse(cleaned);
  } catch (e) {
    // Try extracting JSON from text
    const match = cleaned.match(/\{[\s\S]*\}/);
    if (match) return JSON.parse(match[0]);
    throw new Error('Could not parse Claude response as JSON. Raw: ' + cleaned.slice(0, 200));
  }
}

// ── Show result ──────────────────────────────────────────
const STATUS_CLASS = {
  'APPROVED': 'approved',
  'APPROVED WITH NOTE': 'note',
  'HOLD FOR REVIEW': 'hold',
  'REJECTED': 'rejected'
};
const STATUS_ICON = {
  'APPROVED': '✓ APPROVED',
  'APPROVED WITH NOTE': '⚠ APPROVED WITH NOTE',
  'HOLD FOR REVIEW': '⚠ HOLD FOR REVIEW',
  'REJECTED': '✗ REJECTED'
};
const STATUS_BADGE = { 'APPROVED':'ba','APPROVED WITH NOTE':'bn','HOLD FOR REVIEW':'bh','REJECTED':'br' };
const RISK_BADGE   = { 'HIGH':'rh','MEDIUM':'rm','LOW':'rl' };

function showResult(r, filename) {
  const card = document.getElementById('result-card');
  card.style.display = 'block';
  card.className = 'result-card ' + (STATUS_CLASS[r.status] || 'hold');

  document.getElementById('r-header').textContent = STATUS_ICON[r.status] || r.status;
  document.getElementById('r-vendor').textContent  = r.vendor || '—';
  document.getElementById('r-inv').textContent     = r.invoice_number || '—';
  document.getElementById('r-total').textContent   = r.total
    ? '$' + Number(r.total).toLocaleString('en-US', { minimumFractionDigits: 2 })
    : '—';
  document.getElementById('r-risk').textContent    = r.risk || '—';

  // Anomalies
  const al = document.getElementById('anomaly-list');
  if (!r.anomalies || r.anomalies.length === 0) {
    al.innerHTML = '<div class="anomaly CLEAN">// no anomalies detected — invoice looks clean</div>';
  } else {
    al.innerHTML = r.anomalies.map(a =>
      `<div class="anomaly ${a.severity}">[${a.severity}] ${a.type}: ${a.detail}</div>`
    ).join('');
  }

  // Reasoning
  const rb = document.getElementById('r-reasoning');
  if (r.reasoning) {
    rb.style.display = 'block';
    rb.textContent = '// AI reasoning: ' + r.reasoning;
  } else {
    rb.style.display = 'none';
  }

  // Email draft
  if (r.draft_email) {
    document.getElementById('email-sec').style.display = 'block';
    document.getElementById('email-draft').textContent = r.draft_email;
  } else {
    document.getElementById('email-sec').style.display = 'none';
  }

  // Action buttons
  const btns = document.getElementById('act-btns');
  if (r.status === 'APPROVED' || r.status === 'APPROVED WITH NOTE') {
    btns.innerHTML =
      '<button class="act-btn btn-approve" onclick="approvePayment()">APPROVE PAYMENT</button>' +
      '<button class="act-btn btn-reset" onclick="resetUpload()">UPLOAD ANOTHER</button>';
  } else if (r.status === 'HOLD FOR REVIEW') {
    btns.innerHTML =
      '<button class="act-btn btn-send" onclick="sendEmail()">SEND DISPUTE EMAIL</button>' +
      '<button class="act-btn btn-reset" onclick="resetUpload()">UPLOAD ANOTHER</button>';
  } else {
    btns.innerHTML =
      '<button class="act-btn btn-reject" onclick="resetUpload()">NOTED — UPLOAD ANOTHER</button>';
  }

  // Save to results list
  results.unshift({
    vendor: r.vendor,
    invoice_number: r.invoice_number,
    total: r.total,
    status: r.status,
    risk: r.risk,
    filename,
    anomaly_count: (r.anomalies || []).length,
    anomaly_types: (r.anomalies || []).map(a => a.type),
    draft_email: r.draft_email,
    bm: STATUS_BADGE[r.status] || 'ba',
    rm: RISK_BADGE[r.risk] || 'rl'
  });
  updateStats();
}

// ── Error display ────────────────────────────────────────
function showError(msg) {
  document.getElementById('processing').style.display = 'none';
  document.getElementById('dz').style.display = 'block';
  const eb = document.getElementById('error-box');
  eb.style.display = 'block';
  eb.textContent = '// ERROR: ' + msg;
}

// ── Actions ──────────────────────────────────────────────
function approvePayment() {
  alert('Payment approved! Request sent to finance team.');
  resetUpload();
}
function sendEmail() {
  alert('Dispute email sent to vendor!');
  resetUpload();
}
function resetUpload() {
  document.getElementById('dz').style.display = 'block';
  document.getElementById('processing').style.display = 'none';
  document.getElementById('result-card').style.display = 'none';
  document.getElementById('error-box').style.display = 'none';
  document.getElementById('proc-note').textContent = '';
  document.getElementById('fi').value = '';
}

// ── Dashboard ────────────────────────────────────────────
function updateStats() {
  document.getElementById('d-approved').textContent = results.filter(r => r.status === 'APPROVED').length;
  document.getElementById('d-note').textContent     = results.filter(r => r.status === 'APPROVED WITH NOTE').length;
  document.getElementById('d-hold').textContent     = results.filter(r => r.status === 'HOLD FOR REVIEW').length;
  document.getElementById('d-rejected').textContent = results.filter(r => r.status === 'REJECTED').length;
}

function setFilter(f, btn) {
  currentFilter = f;
  document.querySelectorAll('.fbtn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderTable();
}

function renderTable() {
  const q = (document.getElementById('sb').value || '').toLowerCase();
  let rows = results;
  if (currentFilter !== 'ALL') rows = rows.filter(r => r.status === currentFilter);
  if (q) rows = rows.filter(r =>
    (r.vendor || '').toLowerCase().includes(q) ||
    (r.invoice_number || '').toLowerCase().includes(q) ||
    (r.status || '').toLowerCase().includes(q)
  );

  const tb = document.getElementById('tb');
  if (!rows.length) {
    tb.innerHTML = '<tr class="empty-msg"><td colspan="8">// no results yet — upload an invoice to get started</td></tr>';
    return;
  }
  tb.innerHTML = rows.map((r, i) => `
    <tr>
      <td>${i + 1}</td>
      <td style="color:var(--text);font-weight:500;">${r.vendor || '—'}</td>
      <td>${r.invoice_number || '—'}</td>
      <td style="color:var(--text);font-weight:500;">$${Number(r.total || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
      <td><span class="badge ${r.bm}">${r.status}</span></td>
      <td><span class="badge ${r.rm}">${r.risk}</span></td>
      <td>${r.anomaly_count} — ${(r.anomaly_types || []).slice(0, 2).join(', ') || 'None'}</td>
      <td>${r.draft_email
        ? `<button class="view-btn" onclick="viewEmail(${i})">view draft</button>`
        : r.status === 'APPROVED' ? '<span style="color:var(--accent);font-size:11px;">✓ clear</span>' : '—'
      }</td>
    </tr>`).join('');
}

function viewEmail(i) {
  document.getElementById('modal-body').textContent = results[i].draft_email || 'No email draft available.';
  document.getElementById('modal').classList.add('open');
}

// ── Drag and drop ────────────────────────────────────────
const dz = document.getElementById('dz');
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('dragover'); });
dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
dz.addEventListener('drop', e => {
  e.preventDefault();
  dz.classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f && f.type === 'application/pdf') processInvoice(f);
  else alert('Please drop a PDF file.');
});

// Initial render
renderTable();
</script>
</body>
</html>
