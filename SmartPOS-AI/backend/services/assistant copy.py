"""
Real LLM-backed Business Assistant — replaces the frontend's old
keyword-matching answer() function with an actual Claude call that has
tool access to live store data.

Requires ANTHROPIC_API_KEY in the environment. Get one at
https://console.anthropic.com — this is a paid API, calls cost money.

Model: defaults to claude-sonnet-5. Swap to claude-haiku-4-5-20251001 in
the env var below for a cheaper/faster model if Sonnet-level reasoning
isn't needed for your question volume.
"""
import os
import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func

from models.product import Product
from models.transaction import Transaction
import services.products as products_service
import services.transactions as transactions_service

MODEL = os.environ.get("SMARTPOS_ASSISTANT_MODEL", "claude-sonnet-5")
MAX_TOOL_ROUNDS = 5  # safety cap so a confused loop can't run forever


class AssistantError(Exception):
    pass


# --------------------------------------------------------------------------
# Tool definitions — each maps to a real read against the database.
# Kept read-only on purpose: the assistant answers questions, it doesn't
# take actions like checkout or refunds.
# --------------------------------------------------------------------------
TOOLS = [
    {
        "name": "get_dashboard_summary",
        "description": "Get today's revenue, profit, cash/UPI/card totals, transaction count, and alert counts.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_low_stock_products",
        "description": "List products at or below their reorder level, with server-computed reorder quantity suggestions based on real sales velocity.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_expiring_products",
        "description": "List products expiring within a given number of days.",
        "input_schema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "description": "Look-ahead window in days, default 5"}},
        },
    },
    {
        "name": "get_sales_history_summary",
        "description": "Get aggregated sales history: total revenue/profit per product and per day, over the last N days. Use this for 'top product', 'why are sales down', or trend questions.",
        "input_schema": {
            "type": "object",
            "properties": {"days": {"type": "integer", "description": "How many days back, default 30"}},
        },
    },
    {
        "name": "get_fraud_alerts",
        "description": "Get current fraud/anomaly alerts (refund spikes, discount misuse) computed from real transaction patterns.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def _execute_tool(db: Session, name: str, tool_input: dict) -> dict:
    if name == "get_dashboard_summary":
        return transactions_service.get_dashboard_summary(db)

    if name == "get_low_stock_products":
        return {"items": products_service.get_reorder_suggestions(db)}

    if name == "get_expiring_products":
        days = tool_input.get("days", 5)
        cutoff = datetime.utcnow().date() + timedelta(days=days)
        products = (
            db.query(Product)
            .filter(Product.expiry_date.isnot(None), Product.expiry_date <= cutoff)
            .all()
        )
        return {"items": [{"name": p.name, "stock": p.stock, "expiry_date": str(p.expiry_date)} for p in products]}

    if name == "get_sales_history_summary":
        days = tool_input.get("days", 30)
        txns = transactions_service.get_transaction_history(db, days=days)
        by_product = {}
        by_day = {}
        for t in txns:
            by_product.setdefault(t.name, {"revenue": 0.0, "profit": 0.0, "qty": 0})
            by_product[t.name]["revenue"] += t.revenue
            by_product[t.name]["profit"] += t.profit
            by_product[t.name]["qty"] += t.qty
            day = t.timestamp.date().isoformat()
            by_day[day] = by_day.get(day, 0.0) + t.revenue
        top_by_revenue = sorted(by_product.items(), key=lambda kv: kv[1]["revenue"], reverse=True)[:10]
        top_by_profit = sorted(by_product.items(), key=lambda kv: kv[1]["profit"], reverse=True)[:10]
        return {
            "days": days,
            "top_products_by_revenue": [{"name": k, **v} for k, v in top_by_revenue],
            "top_products_by_profit": [{"name": k, **v} for k, v in top_by_profit],
            "daily_revenue": by_day,
        }

    if name == "get_fraud_alerts":
        return {"alerts": transactions_service.get_fraud_alerts(db)}

    raise AssistantError(f"Unknown tool: {name}")


SYSTEM_PROMPT = (
    "You are SmartPOS AI's business assistant for a supermarket owner. "
    "Answer questions about their store using the tools available — call "
    "whichever tools you need, possibly more than one, before answering. "
    "Always answer using the real numbers the tools return, never estimate "
    "or make up figures. Use \u20b9 for currency. Keep answers concise — a "
    "few sentences, not a report. If the tools don't have the data needed "
    "to answer (e.g. anything requiring data the store doesn't track), say "
    "so plainly instead of guessing."
)


def ask(db: Session, question: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise AssistantError(
            "ANTHROPIC_API_KEY isn't set on the backend. Get a key from "
            "https://console.anthropic.com and set it as an environment "
            "variable before starting uvicorn."
        )

    try:
        from anthropic import Anthropic
    except ImportError:
        raise AssistantError("The 'anthropic' package isn't installed — run: pip install anthropic")

    client = Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": question}]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            text_blocks = [b.text for b in response.content if b.type == "text"]
            return "\n".join(text_blocks).strip() or "I wasn't able to form an answer — try rephrasing the question."

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                result = _execute_tool(db, block.name, block.input or {})
                content = json.dumps(result, default=str)
            except Exception as e:
                content = json.dumps({"error": str(e)})
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
        messages.append({"role": "user", "content": tool_results})

    raise AssistantError("The assistant took too many steps without reaching an answer — try a simpler question.")
