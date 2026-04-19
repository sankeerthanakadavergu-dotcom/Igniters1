# AP Intelligence Agent

An intelligent Accounts Payable agent that learns vendor patterns.

## Tech Stack
- Google ADK — CascadeFlow 5-step agent pipeline
- Hindsight — Persistent vendor memory
- Groq — LLM inference
- FastAPI — Backend API
- Streamlit — Frontend UI

## How it works
1. Upload any invoice PDF
2. Agent checks Hindsight memory for vendor history
3. Validates amounts against historical averages
4. Decides: CLEAN / DISPUTED / NEEDS REVIEW
5. Approves payment or drafts dispute email
6. Saves outcome to memory for next time
