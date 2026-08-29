"""
Real LLM-backed Business Assistant — replaces Anthropic Claude calls
with a local Ollama model (e.g., llama3.1, qwen2.5) with tool access.

Requires Ollama running locally (defaults to http://localhost:11434).
Run: pip install ollama
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

# Set default local model (e.g., 'llama3.1', 'qwen2.5', 'mistral')
MODEL = os.environ.get("SMARTPOS_ASSISTANT_MODEL", "llama3.1")
MAX_TOOL_ROUNDS = 5  # Safety cap to prevent infinite tool-calling loops


class AssistantError(Exception):
    pass


# --------------------------------------------------------------------------
# Tool definitions — map to database reads. Formatted for Ollama/OpenAI spec.
# --------------------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_summary",
            "description": "Get today's revenue, profit, cash/UPI/card totals, transaction count, and alert counts.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_low_stock_products",
            "description": "List products at or below their reorder level, with server-computed reorder quantity suggestions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_expiring_products",
            "description": "List products expiring within a given number of days.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "description": "Look-ahead window in days, default 5"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_history_summary",
            "description": "Get aggregated sales history over N days.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "description": "How many days back, default 30"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fraud_alerts",
            "description": "Get current fraud/anomaly alerts.",
            "parameters": {"type": "object", "properties": {}},
        },
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
    "whichever tools you need before answering. Always answer using the real "
    "numbers returned by tools, never make up figures. Use ₹ for currency. "
    "Keep answers concise — a few sentences, not a report."
)


def ask(db: Session, question: str) -> str:
    try:
        import ollama
    except ImportError:
        raise AssistantError("The 'ollama' package isn't installed — run: pip install ollama")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = ollama.chat(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
            )
        except Exception as e:
            raise AssistantError(f"Failed to communicate with local Ollama server: {e}")

        msg = response["message"]
        messages.append(msg)

        # Check if the model requested tool execution
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            # Model is finished calling tools and returned its final response
            return msg.get("content", "").strip() or "I wasn't able to form an answer — try rephrasing."

        # Execute requested tools and append results back to the message history
        for tool_call in tool_calls:
            func_obj = tool_call.get("function", {})
            func_name = func_obj.get("name")
            func_args = func_obj.get("arguments", {})

            # Ensure args are parsed into a dict
            if isinstance(func_args, str):
                try:
                    func_args = json.loads(func_args)
                except json.JSONDecodeError:
                    func_args = {}

            try:
                result = _execute_tool(db, func_name, func_args)
                content = json.dumps(result, default=str)
            except Exception as e:
                content = json.dumps({"error": str(e)})

            messages.append(
                {
                    "role": "tool",
                    "content": content,
                }
            )

    raise AssistantError("The assistant took too many steps without reaching an answer — try a simpler question.")