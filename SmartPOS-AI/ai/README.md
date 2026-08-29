# AI

- forecasting/      — demand prediction, sales trend models
  (production version of the "Smart Reorder Suggestions" logic in the MVP)
- fraud_detection/  — cash mismatch, refund pattern, discount misuse models
  (production version of the mock alerts in the MVP's Fraud & Alerts page)

The MVP's AI Business Assistant is currently rule-based keyword matching
(see frontend/streamlit_mvp/app.py -> answer()). This folder is where an
LLM-backed or ML-backed replacement would live, likely exposed to the
frontend via backend/api/.
