from __future__ import annotations
import re, datetime as dt
from typing import Any, Dict, Optional, Tuple, List

try:
    import frappe
except Exception:
    frappe = None

from . import frappe_tools as ft

# -------- utilities --------

_SYNONYMS_DOMAIN = {
    "sales": ["sale", "sell", "revenue", "turnover", "customers", "invoice", "si", "sales invoice"],
    "purchase": ["buy", "bought", "vendor", "supplier", "po", "purchase", "spend", "ap"],
    "inventory": ["stock", "inventory", "warehouse", "qty", "available"],
}

_SYNONYMS_DIM = {
    "month": ["month", "monthly"],
    "customer": ["customer", "customers", "party"],
    "item": ["item", "sku", "product"],
    "region": ["region", "territory", "country", "state"],
    "supplier": ["supplier", "vendor"],
}

def _now_date() -> dt.date:
    # Frappe site TZ is Asia/Kolkata; dates are fine in local date granularity.
    return dt.date.today()

def _first_day_of_year(d: dt.date) -> dt.date:
    return dt.date(d.year, 1, 1)

def _first_day_of_month(d: dt.date) -> dt.date:
    return dt.date(d.year, d.month, 1)

def _last_day_of_month(d: dt.date) -> dt.date:
    if d.month == 12:
        return dt.date(d.year, 12, 31)
    nxt = dt.date(d.year, d.month+1, 1)
    return nxt - dt.timedelta(days=1)

def _parse_date_range(text: str) -> Tuple[str, str, str]:
    """
    Return ISO from_date, to_date, and a human label.
    Defaults to last 12 months if nothing matched.
    """
    t = text.lower()
    today = _now_date()
    if re.search(r"\b(ytd|this year|year to date)\b", t):
        return (_first_day_of_year(today).isoformat(), today.isoformat(), "this year")
    if re.search(r"\b(last\s+12\s+months|l12m)\b", t):
        start = today - dt.timedelta(days=365)
        return (start.isoformat(), today.isoformat(), "last 12 months")
    if re.search(r"\b(last\s+30\s+days)\b", t):
        start = today - dt.timedelta(days=30)
        return (start.isoformat(), today.isoformat(), "last 30 days")
    if re.search(r"\b(this month|mtd|month to date)\b", t):
        return (_first_day_of_month(today).isoformat(), today.isoformat(), "this month")
    if re.search(r"\b(last month)\b", t):
        lm = today.replace(day=1) - dt.timedelta(days=1)
        return (_first_day_of_month(lm).isoformat(), _last_day_of_month(lm).isoformat(), "last month")
    if re.search(r"\b(today)\b", t):
        return (today.isoformat(), today.isoformat(), "today")
    if re.search(r"\b(yesterday)\b", t):
        y = today - dt.timedelta(days=1)
        return (y.isoformat(), y.isoformat(), "yesterday")
    # default
    start = today - dt.timedelta(days=365)
    return (start.isoformat(), today.isoformat(), "last 12 months")

def _detect_top_n(text: str) -> Optional[int]:
    m = re.search(r"\btop\s+(\d{1,3})\b", text.lower())
    if m:
        try: return max(1, min(200, int(m.group(1))))
        except: return None
    return None

def _match_any(text: str, words: List[str]) -> bool:
    t = text.lower()
    return any(re.search(rf"\b{re.escape(w)}\b", t) for w in words)

def _detect_domain(text: str) -> str:
    t = text.lower()
    if _match_any(t, _SYNONYMS_DOMAIN["purchase"]): return "purchase"
    if _match_any(t, _SYNONYMS_DOMAIN["inventory"]): return "inventory"
    # default to sales for business analytics
    if _match_any(t, _SYNONYMS_DOMAIN["sales"]): return "sales"
    return "sales"

def _detect_dimension(text: str, domain: str) -> str:
    t = text.lower()
    for dim, alts in _SYNONYMS_DIM.items():
        if _match_any(t, alts):
            # if supplier mentioned and domain is purchase, prefer supplier
            if dim == "supplier" and domain == "purchase":
                return "supplier"
            if dim != "supplier":
                return dim
    # defaults
    if domain == "sales": return "customer"
    if domain == "purchase": return "supplier"
    return "month"

def _is_docs_question(text: str) -> bool:
    return bool(re.match(r"^\s*(how|what|why|when|where|explain|guide|docs?)\b", text.strip().lower()))

# -------- router --------

def route(query: str) -> Dict[str, Any]:
    q = query.strip()
    # doc help questions go to RAG
    if _is_docs_question(q):
        return {"intent":"doc_help", "action":"rag", "query": q}

    domain = _detect_domain(q)
    (from_date, to_date, label) = _parse_date_range(q)
    top_n = _detect_top_n(q)
    dim = _detect_dimension(q, domain)

    # explicit "run report ..."
    if re.search(r"\brun\s+report\b", q.lower()):
        # choose analytics report based on domain
        report_name = "Sales Analytics" if domain=="sales" else "Purchase Analytics"
        group_ui = {"month":"Month","customer":"Customer","item":"Item Code","region":"Territory","supplier":"Supplier"}.get(dim, "Month")
        filters = {"from_date": from_date, "to_date": to_date, "group_by": group_ui}
        return {"intent":"reporting","action":"run_report","report_name":report_name,"filters":filters}

    if domain == "inventory":
        return {"intent":"analytics","action":"inventory_snapshot","args":{"warehouse": None}}

    if domain == "purchase":
        return {"intent":"analytics","action":"purchase_stats","args":{"by":dim,"from_date":from_date,"to_date":to_date,"top_n": top_n}}

    # sales default
    return {"intent":"analytics","action":"sales_stats","args":{"by":dim,"from_date":from_date,"to_date":to_date,"top_n": top_n}}

# -------- executor with graceful fallbacks --------

def execute_routed(r: Dict[str, Any]) -> Dict[str, Any]:
    intent = r.get("intent")
    action = r.get("action")

    # 1) Docs (RAG)
    if action == "rag":
        from .knowledge.qa import answer_question
        ans = answer_question(r["query"], top_k=6)
        return {
            "title": "Documentation Answer",
            "columns": ["answer"],
            "rows": [[ans.get("answer") or ""]],
            "raw": ans,
        }

    # 2) Inventory
    if action == "inventory_snapshot":
        snap = ft.get_inventory_snapshot(r["args"].get("warehouse"))
        return { "title": "Inventory Snapshot", "columns": ["Warehouse","Item","Qty"], "rows": snap.get("rows",[]), "raw": snap }

    # 3) Sales/Purchase analytics (preferred)
    if action in ("sales_stats","purchase_stats"):
        args = r["args"].copy()
        dim = args.pop("by")
        top_n = args.pop("top_n", None)
        getter = ft.get_sales_stats if action=="sales_stats" else ft.get_purchase_stats
        data = getter(by=dim, **args)  # returns rows with dicts {label,total,...}
        rows = data.get("rows", [])

        # widen automatically if no rows
        if not rows:
            # try 3 years
            f, t = args["from_date"], args["to_date"]
            t_dt = dt.date.fromisoformat(t)
            f2 = (t_dt - dt.timedelta(days=365*3)).isoformat()
            data = getter(by=dim, from_date=f2, to_date=t)
            rows = data.get("rows", [])

        # top N
        if rows and top_n:
            try:
                rows = sorted(rows, key=lambda r: float(r.get("total") or 0), reverse=True)[:top_n]
                data["rows"] = rows
            except Exception:
                pass

        data.setdefault("title", f"{'Sales' if action=='sales_stats' else 'Purchases'} by {dim.title()}")
        data.setdefault("group_by", dim)
        return data

    # 4) Reports as fallback
    if action == "run_report":
        rep = ft.run_report(r["report_name"], r.get("filters") or {})
        # try to locate label/total-ish columns to feed the pretty view better
        cols = [c.lower() for c in rep.get("columns",[])]
        rows = rep.get("rows", [])
        if cols and rows and isinstance(rows[0], list):
            lab_idx = next((i for i,c in enumerate(cols) if c in ("customer","supplier","item","month","territory","region","label","name")), 0)
            num_idx = next((i for i,c in enumerate(cols) if c in ("grand total","total","amount","value","net total")), None)
            if num_idx is not None:
                shaped = [{"label": r[lab_idx], "total": r[num_idx]} for r in rows if len(r)>max(lab_idx,num_idx)]
                return {"title": rep.get("title"), "group_by": cols[lab_idx], "from_date": r.get("filters",{}).get("from_date"), "to_date": r.get("filters",{}).get("to_date"), "rows": shaped, "raw": rep}
        return rep

    # Unknown → RAG as last resort
    from .knowledge.qa import answer_question
    ans = answer_question(r.get("query",""), top_k=6)
    return {"title":"Answer", "columns":["answer"], "rows":[[ans.get("answer") or ""]], "raw": ans}

def route_and_execute(query: str) -> Dict[str, Any]:
    r = route(query)
    out = execute_routed(r)
    # annotate minimal meta for the pretty renderer
    if isinstance(out, dict):
        out.setdefault("from_date", r.get("args",{}).get("from_date") if r.get("args") else r.get("filters",{}).get("from_date"))
        out.setdefault("to_date", r.get("args",{}).get("to_date") if r.get("args") else r.get("filters",{}).get("to_date"))
        gb = (r.get("args",{}).get("by") or r.get("filters",{}).get("group_by"))
        if gb: out.setdefault("group_by", gb)
    return out
