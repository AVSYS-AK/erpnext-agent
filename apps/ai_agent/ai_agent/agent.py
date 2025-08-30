from __future__ import annotations
import json, uuid, re
from datetime import date
from typing import Dict, Any, List, Optional
from .llm_client import LLMClient, LLMConfig, PLANNER_SYSTEM
from . import frappe_tools as ft

# Read-only tools we can safely execute even when dry_run=True
READ_ONLY_TOOLS = {
    "get_sales_stats",
    "get_purchase_stats",
    "get_inventory_snapshot",
    "run_sql",
    "run_report",
}

# ----- date helpers -----
def _add_months(d: date, months: int) -> date:
    y = d.year + ((d.month - 1 + months) // 12)
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, min(d.day, 28))

def _last_n_month_range(n: int = 12):
    today = date.today()
    start = _add_months(today.replace(day=1), -(n - 1))
    return start.isoformat(), today.isoformat()

# ----- fast paths for common analytics -----
def _fastpath(command: str) -> Optional[Dict[str, Any]]:
    lc = command.lower().strip()
    if re.search(r"(best|top|highest).*(selling|sales).*(month)", lc) or "best selling month" in lc:
        f, t = _last_n_month_range(12)
        return {
            "intent": "analytics",
            "steps": [{"tool": "get_sales_stats", "args": {"by": "month", "from_date": f, "to_date": t}}],
            "confirm_required": False,
            "risks": ["Assumes last 12 months; adjust if needed."]
        }
    if "top customers" in lc:
        f, t = _last_n_month_range(12)
        return {
            "intent": "analytics",
            "steps": [{"tool": "get_sales_stats", "args": {"by": "customer", "from_date": f, "to_date": t}}],
            "confirm_required": False, "risks": []
        }
    if "top items" in lc or "best sellers" in lc:
        f, t = _last_n_month_range(12)
        return {
            "intent": "analytics",
            "steps": [{"tool": "get_sales_stats", "args": {"by": "item", "from_date": f, "to_date": t}}],
            "confirm_required": False, "risks": []
        }
    return None

# Ensure tool steps have safe default args
def _normalize_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    f, t = _last_n_month_range(12)
    norm = []
    for s in steps:
        tool = s.get("tool")
        args = (s.get("args") or {}).copy()
        if tool == "get_sales_stats":
            args.setdefault("by", "month")
            args.setdefault("from_date", f)
            args.setdefault("to_date", t)
        if tool == "get_purchase_stats":
            args.setdefault("by", "month")
            args.setdefault("from_date", f)
            args.setdefault("to_date", t)
        if tool == "get_inventory_snapshot":
            # no defaults needed
            pass
        norm.append({"tool": tool, "args": args})
    return norm

def classify_and_plan(llm: LLMClient, command: str) -> Dict[str,Any]:
    fast = _fastpath(command)
    if fast:
        return fast
    plan_raw = llm.complete(system=PLANNER_SYSTEM, user=command, streaming=False)
    try:
        plan = json.loads(plan_raw)
        assert isinstance(plan, dict) and "steps" in plan
        plan["steps"] = [s for s in plan.get("steps", []) if isinstance(s, dict) and s.get("tool")]
        plan["steps"] = _normalize_steps(plan["steps"])
        return plan
    except Exception:
        f, t = _last_n_month_range(12)
        return {
            "intent":"analytics",
            "steps":[{"tool":"get_sales_stats","args":{"by":"month","from_date":f,"to_date":t}}],
            "confirm_required": False,
            "risks":["planner_fallback"]
        }

def execute(command_text: str, user: str, dry_run: bool=False, confirm_token: Optional[str]=None) -> Dict[str,Any]:
    corr_id = str(uuid.uuid4())
    idem = str(uuid.uuid4())
    llm = LLMClient(LLMConfig())
    plan = classify_and_plan(llm, command_text)
    intent = plan.get("intent","analytics")
    steps = plan.get("steps",[])[:8]
    results: List[Dict[str,Any]] = []
    confirm_needed = bool(plan.get("confirm_required")) or (intent in {"structural_change"})
    if confirm_needed and not confirm_token and not dry_run:
        return {"status":"awaiting_confirmation","correlation_id":corr_id,"plan":plan}

    for idx, step in enumerate(steps, start=1):
        tool = step.get("tool")
        args = step.get("args",{}) or {}

        # In dry_run, execute read-only tools; skip writes.
        if dry_run and tool not in READ_ONLY_TOOLS:
            results.append({"step":idx,"tool":tool,"dry_run":True,"args":args})
            continue

        # Execute tools
        if tool == "create_doctype":
            res = ft.create_doctype(**args, idempotency_key=idem)
        elif tool == "update_doctype":
            res = ft.update_doctype(**args, idempotency_key=idem)
        elif tool == "create_workflow":
            res = ft.create_workflow(**args, idempotency_key=idem)
        elif tool == "create_query_report":
            res = ft.create_query_report(**args, idempotency_key=idem)
        elif tool == "create_script_report":
            res = ft.create_script_report(**args, idempotency_key=idem)
        elif tool == "run_report":
            res = ft.run_report(**args)
        elif tool == "run_sql":
            res = {"rows": ft.run_sql(**args)}
        elif tool == "get_sales_stats":
            res = ft.get_sales_stats(**args)
        elif tool == "get_purchase_stats":
            res = ft.get_purchase_stats(**args)
        elif tool == "get_inventory_snapshot":
            res = {"rows": ft.get_inventory_snapshot(**args)}
        elif tool == "create_task":
            res = ft.create_task(**args, idempotency_key=idem)
        elif tool == "enqueue_background_job":
            res = ft.enqueue_background_job(**args)
        else:
            res = {"error": f"unknown tool {tool}"}
        results.append({"step":idx,"tool":tool,"result":res})

    # Human summary for common analytics
    summary = None
    for r in results:
        if r.get("tool") == "get_sales_stats":
            data = r.get("result") or {}
            rows = data.get("rows") or []
            # handle both dict rows and tuples if necessary
            if rows and isinstance(rows[0], dict) and "period" in rows[0] and "revenue" in rows[0]:
                best = max(rows, key=lambda x: float(x.get("revenue") or 0))
                summary = f"Best selling month (last 12 months): {best['period']} • Revenue={best['revenue']}"
                break

    out = {"status":"completed","correlation_id":corr_id,"plan":plan,"results":results}
    if summary:
        out["summary"] = summary
    return out

def smart_execute(command_text: str, user: str, dry_run: bool = True, confirm_token: str = "") -> dict:
    """
    1) Try deterministic router (fast, robust for most business questions)
    2) If that returns something empty AND not a docs question, try LLM plan
    3) Else fallback to RAG
    """
    from .router import route_and_execute
    routed = route_and_execute(command_text)  # already returns a normalized dict

    # If we got rows or a text answer, return immediately
    if isinstance(routed, dict):
        rows = routed.get("rows")
        if rows or routed.get("raw"):
            return {"status":"completed","plan":{"intent":"auto","steps":[],"risks":[],"confirm_required":False}, "results":[{"step":1,"tool":"router","result":routed}]}

    # Fall back to original LLM-driven plan (existing flow)
    return execute(command_text, user, dry_run=dry_run, confirm_token=confirm_token)
