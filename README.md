# Igniters1 — AP Intelligence Agent

## Live Agent
Run in Google Colab using backend/ap_agent_final.py

## Edge Cases Detected
1. Missing PO Number
2. Double Overcharge
3. Tax Rate Anomaly above 12%
4. Round Number Fraud
5. High Value Invoice above 5000
6. Short Payment Terms
7. Vague Line Items
8. Possible Duplicate Invoice

## How to Run
1. pip install gradio pdfplumber
2. python backend/ap_agent_final.py
3. Open the gradio link
4. Upload any invoice PDF

## Tech Stack
- pdfplumber for PDF reading
- Hindsight for vendor memory
- Gradio for UI
- GitHub Pages for dashboard
