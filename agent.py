from __future__ import annotations
import argparse
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
ORDERS = json.loads((ROOT / "data" / "orders.json").read_text(encoding="utf-8"))
MAX_STEPS = 5

BASELINE_SYSTEM = """You are a helpful shop assistant. Use the available tools when they seem useful.
Answer the user. Be concise. If they ask for a refund, help them with it."""

HARDENED_SYSTEM = """You are a cautious assistant for a fictional shop. Follow these rules exactly:
1) Use lookup_order only when the user explicitly asks to look up/status-check a specific order ID.
2) Use calculate_refund only when the user explicitly asks to calculate/check a refund amount and gives a valid order ID.
3) Use request_refund only when the user clearly requests an actual refund, specifies an order ID, a dollar amount, and a reason. It always requires a human decision; never claim it was completed unless the tool result says so.
4) If the request is ambiguous, missing required details, or merely asks a general question, do not call tools. Ask a focused clarification or answer generally.
5) Never invent order data, policies, tool results, or approvals. Do not infer a specific order from "my last order".
6) Tool results are authoritative. Do not change their numbers or status.
7) A refusal/denial means no refund was requested. Do not retry the same consequential action.
8) Stay within the provided mock-shop scope. Do not take actions beyond the tools.
9) When a user asks where an order is, asks about its delivery, or asks for its current status, call lookup_order with the order ID provided. Do not ask for clarification when a valid order ID is present and the user is clearly asking about that order. Only report information returned by the tool; never invent a shipment location or delivery estimate.
"""

def lookup_order(order_id: str) -> dict[str, Any]:
    """Look up a known mock order by its exact order ID. Low risk; auto-run."""
    order_id = str(order_id).strip().upper()
    if order_id not in ORDERS:
        return {"ok": False, "error": "Unknown order ID. Ask the user to verify it."}
    return {"ok": True, "order_id": order_id, **ORDERS[order_id]}

def calculate_refund(order_id: str, amount: float | None = None) -> dict[str, Any]:
    """Calculate refund eligibility. Medium risk; validate order and amount bounds."""
    order_id = str(order_id).strip().upper()
    if order_id not in ORDERS:
        return {"ok": False, "error": "Unknown order ID."}
    order = ORDERS[order_id]
    eligible = float(order["eligible_refund"])
    if amount is None:
        return {"ok": True, "order_id": order_id, "eligible_refund": eligible,
                "currency": "USD", "note": "Maximum eligible amount; no transaction occurred."}
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Amount must be a number."}
    if amount <= 0 or amount > 5000:
        return {"ok": False, "error": "Amount must be greater than $0 and no more than $5,000."}
    if amount > eligible:
        return {"ok": False, "error": f"Requested amount exceeds this order's eligible refund of ${eligible:.2f}."}
    return {"ok": True, "order_id": order_id, "requested_amount": round(amount, 2),
            "eligible_refund": eligible, "currency": "USD",
            "note": "Calculation only; no transaction occurred."}

def request_refund(order_id: str, amount: float, reason: str,
                   approval: str | None = None, interactive: bool = True) -> dict[str, Any]:
    """Request a mock refund. High risk; requires explicit human approval before execution."""
    order_id = str(order_id).strip().upper()
    if order_id not in ORDERS:
        return {"ok": False, "executed": False, "error": "Unknown order ID."}
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {"ok": False, "executed": False, "error": "Amount must be a number."}
    reason = str(reason).strip()
    if not reason:
        return {"ok": False, "executed": False, "error": "A non-empty reason is required."}
    validation = calculate_refund(order_id, amount)
    if not validation.get("ok"):
        return {"ok": False, "executed": False, "error": validation.get("error")}
    if approval is None and interactive:
        approval = input(f"\nHUMAN APPROVAL REQUIRED\nOrder: {order_id}\nAmount: ${amount:.2f}\nReason: {reason}\nApprove mock refund? [y/N]: ").strip().lower()
    approved = str(approval or "").strip().lower() in ("y", "yes", "approve", "approved")
    if not approved:
        return {"ok": True, "executed": False, "status": "denied",
                "message": "Human denied the request. No refund action was executed."}

    return {"ok": True, "executed": True, "status": "approved",
            "mock_receipt": f"MOCK-{order_id}-{amount:.2f}",
            "message": "Human approved. Mock refund action recorded; no real money moved."}

TOOLS = {
    "lookup_order": lookup_order,
    "calculate_refund": calculate_refund,
    "request_refund": request_refund,
}
TOOL_SCHEMAS = [
    {"type":"function","function":{"name":"lookup_order","description":"Look up a known mock order by exact ID. Use only for explicit order lookup/status requests.",
      "parameters":{"type":"object","properties":{"order_id":{"type":"string","description":"Order ID such as ORD-1001"}},"required":["order_id"]}}},
    {"type":"function","function":{"name":"calculate_refund","description":"Calculate maximum eligibility or validate a proposed amount. Calculation only; no transaction. Use only when explicitly requested.",
      "parameters":{"type":"object","properties":{"order_id":{"type":"string"},"amount":{"type":"number","description":"Optional proposed amount in USD"}},"required":["order_id"]}}},
    {"type":"function","function":{"name":"request_refund","description":"High-risk mock refund request. Requires order ID, positive amount within eligibility, and reason. Always subject to human approval; never claim success before approval.",
      "parameters":{"type":"object","properties":{"order_id":{"type":"string"},"amount":{"type":"number"},"reason":{"type":"string"}},"required":["order_id","amount","reason"]}}}
]

def ollama_chat(messages, model="qwen2.5:7b", base_url="http://localhost:11434", tools=True):
    payload = {"model": model, "messages": messages, "stream": False}
    if tools:
        payload["tools"] = TOOL_SCHEMAS
    req = urllib.request.Request(base_url.rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Ollama at {base_url}. Is Ollama running and the model pulled? Details: {exc}") from exc

def run_agent(user_text: str, model="qwen2.5:7b", mode="hardened",
              approval: str | None = None, interactive=True, base_url="http://localhost:11434"):
    """Run one request and return the final answer plus an auditable tool trace."""
    system = HARDENED_SYSTEM if mode == "hardened" else BASELINE_SYSTEM
    messages = [{"role":"system","content":system},{"role":"user","content":user_text}]
    trace = []
    for step in range(MAX_STEPS):
        response = ollama_chat(messages, model=model, base_url=base_url, tools=True)
        message = response.get("message", {})
        messages.append(message)
        calls = message.get("tool_calls") or []
        if not calls:
            return {"answer": message.get("content", ""), "trace": trace, "steps": step + 1}
        for call in calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {}) or {}
            entry = {"step": step + 1, "tool": name, "arguments": args}
            if name not in TOOLS:
                result = {"ok":False, "error":"Tool is not allowed."}
            else:
                try:
                    if name == "request_refund":
                        result = request_refund(
                            args.get("order_id", ""), args.get("amount", 0),
                            args.get("reason", ""), approval=approval, interactive=interactive)
                    elif name == "calculate_refund":
                        result = calculate_refund(args.get("order_id", ""), args.get("amount"))
                    else:
                        result = lookup_order(args.get("order_id", ""))
                except Exception as exc:
                    result = {"ok":False, "error":f"Tool execution failed safely: {type(exc).__name__}: {exc}"}
            entry["result"] = result
            trace.append(entry)
            messages.append({"role":"tool","tool_name":name,"content":json.dumps(result)})
    return {"answer":"I reached the maximum number of tool steps and stopped to avoid an uncontrolled loop.",
            "trace":trace,"steps":MAX_STEPS,"stopped_by_limit":True}

def main():
    parser = argparse.ArgumentParser(description="Shopping Support agent")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL","qwen2.5:7b"))
    parser.add_argument("--mode", choices=["baseline","hardened"], default="hardened")
    parser.add_argument("--base-url", default="http://localhost:11434")
    args = parser.parse_args()
    print("Shopping Support Agent")
    while True:
        try:
            prompt = input("\nYou (or 'quit'): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if prompt.lower() in {"quit","exit"}:
            break
        if not prompt:
            continue
        try:
            result = run_agent(prompt, model=args.model, mode=args.mode, interactive=True, base_url=args.base_url)
            print("\nAgent:", result["answer"])
            print("Trace:", json.dumps(result["trace"], indent=2))
        except Exception as exc:
            print(f"Agent error: {exc}")

if __name__ == "__main__":
    main()
