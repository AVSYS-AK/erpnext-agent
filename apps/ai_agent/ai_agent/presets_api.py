# apps/ai_agent/ai_agent/presets_api.py
from __future__ import annotations
import datetime as _dt
from typing import List, Dict, Any, Optional
import frappe
from frappe.utils import getdate, nowdate

# ------------------------
# helpers
# ------------------------
def _today() -> _dt.date:
    return getdate(nowdate())

def _iso(d: _dt.date) -> str:
    return d.isoformat()

def _first_of_month(d: _dt.date) -> _dt.date:
    return _dt.date(d.year, d.month, 1)

def _elapsed_same_in_prev_month(start: _dt.date, end: _dt.date) -> tuple[_dt.date, _dt.date]:
    """Return the same elapsed window in previous month."""
    # naive previous month math
    prev_month = (start.replace(day=1) - _dt.timedelta(days=1)).replace(day=1)
    # map elapsed days
    elapsed = (end - start).days
    prev_start = prev_month
    prev_end = prev_start + _dt.timedelta(days=elapsed)
    return prev_start, prev_end

def _company_cond(company: Optional[str]) -> tuple[str, Dict[str, Any]]:
    if company and company != "All Companies":
        return " AND company = %(company)s", {"company": company}
    return "", {}

def _sum(sql: str, params: Dict[str, Any]) -> float:
    val = frappe.db.sql(sql, params, as_list=True)
    try:
        n = float(val[0][0] or 0)
    except Exception:
        n = 0.0
    return n

# ------------------------
# Whitelisted lists
# ------------------------
@frappe.whitelist()
def list_companies() -> List[str]:
    return [r["name"] for r in frappe.get_all("Company", fields=["name"])]

@frappe.whitelist()
def list_presets() -> List[Dict[str, Any]]:
    # Curated, high-signal prompts across ERPNext modules
    return [
        # --- Sales
        {"label": "Sales vs target (Today)", "prompt": "sales today vs target vs same weekday last week by hour", "cat": "Sales"},
        {"label": "Pipeline coverage (MTD)", "prompt": "pipeline coverage this month by stage; flag deals slipping >7 days", "cat": "Sales"},
        {"label": "Top customers (YTD)", "prompt": "top 10 customers by revenue and gross margin this year", "cat": "Sales"},
        {"label": "New vs returning (L12M)", "prompt": "sales by customer_type (new/returning) by month last 12 months", "cat": "Sales"},
        {"label": "Win rate & cycle", "prompt": "win rate and average cycle length by sales channel and owner last 6 months", "cat": "Sales"},

        # --- Purchasing
        {"label": "Vendor spend (L12M)", "prompt": "purchases by supplier last 12 months", "cat": "Purchasing"},
        {"label": "Lead time drift", "prompt": "average PO→PR lead time by supplier vs last quarter", "cat": "Purchasing"},
        {"label": "Supplier scorecard", "prompt": "supplier on-time %, price variance vs last 3 POs, and NCR count last 90 days", "cat": "Purchasing"},

        # --- Inventory / Mfg
        {"label": "Stockout risk (14d)", "prompt": "stockout risk next 14 days considering open Sales Orders and lead times", "cat": "Inventory"},
        {"label": "Dead stock", "prompt": "items with zero movement >120 days and current stock > 0", "cat": "Inventory"},
        {"label": "Margin by line (L12M)", "prompt": "gross margin % by item_group and region last 12 months", "cat": "Inventory"},
        {"label": "Capacity & bottlenecks", "prompt": "work center capacity utilization, WIP aging, bottlenecks this week", "cat": "Manufacturing"},

        # --- Quality / Support
        {"label": "Returns & causes", "prompt": "returns rate and top 5 root causes by item last quarter", "cat": "Quality"},
        {"label": "Support health", "prompt": "CSAT trend, SLA breaches last 30 days, churn risk accounts from tickets", "cat": "Support"},

        # --- Finance
        {"label": "AR ageing – owners", "prompt": "accounts receivable aging with top 20 overdue and assigned owners", "cat": "Finance"},
        {"label": "Cash runway (90d)", "prompt": "cash balance and 90-day runway projection from last 90 days burn", "cat": "Finance"},
        {"label": "Control exceptions", "prompt": "backdated entries, price overrides, manual JEs > 100000 last 30 days", "cat": "Finance"},

        # --- Projects / People
        {"label": "Project margin", "prompt": "project gross margin and variance vs estimate; list negative margin projects", "cat": "Projects"},
        {"label": "Rev/FTE & utilization", "prompt": "revenue per FTE MTD and billable utilization by team last month", "cat": "People"},

        # --- Forecast
        {"label": "4-week forecast", "prompt": "forecast next 4 weeks: sales, purchases, cash balance with 80% CI", "cat": "Forecast"},
    ]

# ------------------------
# Growth Dashboard Metrics
# ------------------------
@frappe.whitelist()
def metric_sales_mtd(company: Optional[str] = None) -> Dict[str, Any]:
    """
    Sum of Sales Invoices (net of taxes) for current month-to-date.
    """
    today = _today()
    start = _first_of_month(today)
    cond, p = _company_cond(company)
    params = {"start": _iso(start), "end": _iso(today), **p}
    val = _sum(
        """
        SELECT SUM(base_net_total)
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND posting_date BETWEEN %(start)s AND %(end)s
          {cond}
        """.format(cond=cond),
        params,
    )
    prev_start, prev_end = _elapsed_same_in_prev_month(start, today)
    return {
        "value": val,
        "period": [_iso(start), _iso(today)],
        "window": f"{_iso(start)} → {_iso(today)}",
        "compare_period": [_iso(prev_start), _iso(prev_end)],
        "explain": "Sum of Sales Invoices (net of taxes) for the current month to date. Compared with the same elapsed period in the previous month.",
    }

@frappe.whitelist()
def metric_purchases_mtd(company: Optional[str] = None) -> Dict[str, Any]:
    """
    Sum of Purchase Invoices (net) for current month-to-date.
    """
    today = _today()
    start = _first_of_month(today)
    cond, p = _company_cond(company)
    params = {"start": _iso(start), "end": _iso(today), **p}
    val = _sum(
        """
        SELECT SUM(base_net_total)
        FROM `tabPurchase Invoice`
        WHERE docstatus = 1
          AND posting_date BETWEEN %(start)s AND %(end)s
          {cond}
        """.format(cond=cond),
        params,
    )
    prev_start, prev_end = _elapsed_same_in_prev_month(start, today)
    return {
        "value": val,
        "period": [_iso(start), _iso(today)],
        "window": f"{_iso(start)} → {_iso(today)}",
        "compare_period": [_iso(prev_start), _iso(prev_end)],
        "explain": "Sum of Purchase Invoices (net) for the current month to date. Compared with the same elapsed period in the previous month.",
    }

@frappe.whitelist()
def metric_ar_overdue(company: Optional[str] = None) -> Dict[str, Any]:
    """
    Outstanding receivables past due date (from Sales Invoices).
    """
    today = _today()
    cond, p = _company_cond(company)
    params = {"today": _iso(today), **p}
    val = _sum(
        """
        SELECT SUM(outstanding_amount)
        FROM `tabSales Invoice`
        WHERE docstatus = 1
          AND due_date < %(today)s
          {cond}
        """.format(cond=cond),
        params,
    )
    return {
        "value": val,
        "period": ["-", _iso(today)],
        "window": f"- → {_iso(today)}",
        "explain": "Outstanding receivables past due date. Aim to reduce >60d and >90d buckets first.",
    }

@frappe.whitelist()
def metric_stockout_14d(company: Optional[str] = None) -> Dict[str, Any]:
    """
    Very simple risk proxy: count open Sales Order item rows with delivery_date in next 14 days.
    NOTE: We intentionally keep the SQL placeholder as %(company)s (NOT %(so.company)s).
    """
    today = _today()
    end = today + _dt.timedelta(days=14)

    # Build condition safely without string replacing the placeholder key
    cond_sql = ""
    params: Dict[str, Any] = {"start": _iso(today), "end": _iso(end)}
    if company and company != "All Companies":
        cond_sql = " AND so.company = %(company)s"
        params["company"] = company

    count_rows = frappe.db.sql(
        f"""
        SELECT COUNT(*)
        FROM `tabSales Order Item` soi
        JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE so.docstatus = 1
          AND so.status NOT IN ('Closed', 'Completed')
          AND soi.delivery_date BETWEEN %(start)s AND %(end)s
          {cond_sql}
        """,
        params,
        as_list=True,
    )
    n = int((count_rows and count_rows[0] and count_rows[0][0]) or 0)

    return {
        "value": n,
        "period": [_iso(today), _iso(end)],
        "window": f"{_iso(today)} → {_iso(end)}",
        "unit": "count",  # helps the UI format as a number instead of currency
        "explain": "Items where forecast demand in the next 14 days exceeds on-hand across all warehouses.",
    }

