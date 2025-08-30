# apps/ai_agent/ai_agent/frappe_tools.py

from __future__ import annotations
import datetime as _dt
from typing import Optional, Dict, Any, List, Tuple
import frappe

# ---------------------------------------------------------------------------
# Small, composable helpers
# ---------------------------------------------------------------------------

def _today() -> _dt.date:
    """Return today's date (site TZ handled by MariaDB; day precision is enough)."""
    return _dt.date.today()


def _normalize_dates(from_date: Optional[str], to_date: Optional[str]) -> Tuple[str, str]:
    """
    Normalize date strings. If any is missing, default to the last 365 days.
    Returns ISO strings 'YYYY-MM-DD'.
    """
    if not from_date or not to_date:
        end = _today()
        start = end - _dt.timedelta(days=365)
        return start.isoformat(), end.isoformat()
    return str(from_date), str(to_date)


def _norm_group_key(kwargs: Dict[str, Any], default: str = "month") -> str:
    """
    Accept multiple aliases that the planner/router/UI may emit:
    - Keys: fieldname | group_by | by
    - Values: normalize synonyms to: month | customer | item | supplier | region
    """
    # pick the key
    by = kwargs.get("by") or kwargs.get("fieldname") or kwargs.get("group_by") or default
    by = str(by or "").strip().lower()

    # normalize common plurals/aliases
    synonyms = {
        "months": "month", "mth": "month", "mmm": "month", "mon": "month",
        "customers": "customer", "cust": "customer", "party": "customer",
        "items": "item", "sku": "item", "product": "item",
        "vendors": "supplier", "vendor": "supplier",
        "territory": "region", "country": "region", "region": "region",
    }
    by = synonyms.get(by, by)

    if by not in {"month", "customer", "item", "supplier", "region"}:
        # safe fallback
        by = "month"
    return by


def run_sql(sql: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """
    Safe wrapper around frappe.db.sql that always returns a list of dict rows.
    NOTE: The SQL string should be templated only with whitelisted identifiers
    (we only format the label/group exprs chosen from a fixed set below).
    """
    return frappe.db.sql(sql, params or {}, as_dict=True)


# ---------------------------------------------------------------------------
# Purchases Analytics
# ---------------------------------------------------------------------------

def get_purchase_stats(
    by: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    company: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Aggregations over Purchase Invoices (docstatus = 1), taxes excluded (base_net_amount).
    by: month | supplier | item | region
        region = Supplier Address country if available (best-effort)
    Returns a normalized dict the UI can render directly:
      { "group_by", "from_date", "to_date", "rows": [{"label","total"}, ...], "highest": {...}|None }
    """
    by = _norm_group_key({"by": by, **kwargs}, default="month")
    from_date, to_date = _normalize_dates(from_date, to_date)

    conds = ["pi.docstatus = 1", "pi.posting_date BETWEEN %(from_date)s AND %(to_date)s"]
    params: Dict[str, Any] = {"from_date": from_date, "to_date": to_date}
    if company:
        conds.append("pi.company = %(company)s")
        params["company"] = company

    # Safe, whitelisted label/group expressions
    if by == "month":
        label = "DATE_FORMAT(pi.posting_date, '%%Y-%%m')"
    elif by == "supplier":
        label = "pi.supplier"
    elif by == "item":
        label = "pii.item_code"
    elif by == "region":
        # Supplier's address country if linked; empty string otherwise
        label = "COALESCE(addr.country, '')"
    else:
        label = "DATE_FORMAT(pi.posting_date, '%%Y-%%m')"  # fallback

    joins = """
        `tabPurchase Invoice` pi
        JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
        LEFT JOIN `tabAddress` addr ON addr.name = pi.supplier_address
    """

    sql = f"""
        SELECT
            {label} AS label,
            SUM(pii.base_net_amount) AS total
        FROM {joins}
        WHERE {" AND ".join(conds)}
        GROUP BY {label}
        ORDER BY total DESC
    """

    rows = run_sql(sql, params)
    return {
        "title": f"Purchases by {by.title()}",
        "group_by": by,
        "from_date": from_date,
        "to_date": to_date,
        "rows": rows,
        "highest": rows[0] if rows else None,
    }


# ---------------------------------------------------------------------------
# Sales Analytics
# ---------------------------------------------------------------------------

def get_sales_stats(
    by: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    company: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Aggregations over Sales Invoices (docstatus = 1), taxes excluded (base_net_amount).
    by: month | customer | item | region
        region = Shipping Address country if available (best-effort)
    Returns a normalized dict the UI can render directly:
      { "group_by", "from_date", "to_date", "rows": [{"label","total"}, ...], "highest": {...}|None }
    """
    by = _norm_group_key({"by": by, **kwargs}, default="month")
    from_date, to_date = _normalize_dates(from_date, to_date)

    conds = ["si.docstatus = 1", "si.posting_date BETWEEN %(from_date)s AND %(to_date)s"]
    params: Dict[str, Any] = {"from_date": from_date, "to_date": to_date}
    if company:
        conds.append("si.company = %(company)s")
        params["company"] = company

    # Safe, whitelisted label/group expressions
    if by == "month":
        label = "DATE_FORMAT(si.posting_date, '%%Y-%%m')"
    elif by == "customer":
        label = "si.customer"
    elif by == "item":
        label = "sii.item_code"
    elif by == "region":
        label = "COALESCE(addr.country, '')"
    else:
        label = "DATE_FORMAT(si.posting_date, '%%Y-%%m')"

    joins = """
        `tabSales Invoice` si
        JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        LEFT JOIN `tabAddress` addr ON addr.name = si.shipping_address_name
    """

    sql = f"""
        SELECT
            {label} AS label,
            SUM(sii.base_net_amount) AS total
        FROM {joins}
        WHERE {" AND ".join(conds)}
        GROUP BY {label}
        ORDER BY total DESC
    """

    rows = run_sql(sql, params)
    return {
        "title": f"Sales by {by.title()}",
        "group_by": by,
        "from_date": from_date,
        "to_date": to_date,
        "rows": rows,
        "highest": rows[0] if rows else None,
    }


# ---------------------------------------------------------------------------
# Report runner (Query & Script Reports) with normalized table output
# ---------------------------------------------------------------------------

def run_report(report_name: str, filters: dict | None = None) -> dict:
    """
    Execute a Frappe/ERPNext report server-side and return a normalized table.
    Works for Query Reports and Script Reports.

    Returns:
      {
        "title": <report_name>,
        "columns": [<col label 1>, <col label 2>, ...],
        "rows": [[c1, c2, ...], ...],
        "raw": <original run() payload>
      }
    """
    from frappe.desk.query_report import run as _run_query_report

    filters = filters or {}
    user = getattr(frappe, "session", None).user if getattr(frappe, "session", None) else "Administrator"

    # Execute using the same backend as Desk → Report UI
    data = _run_query_report(report_name, filters=filters, user=user)

    # Normalize columns (prefer human label; fall back to fieldname)
    columns: List[str] = []
    fieldnames: List[str] = []
    for c in data.get("columns", []):
        label = (c.get("label") or c.get("fieldname") or "").strip() or "value"
        columns.append(label)
        fieldnames.append(c.get("fieldname") or label)

    # Normalize rows: 2D array aligned with columns order
    rows: List[List[Any]] = []
    for r in data.get("result", []):
        # result rows are dicts keyed by fieldname
        rows.append([r.get(fn) for fn in fieldnames])

    return {
        "title": report_name,
        "columns": columns if columns else (list((rows[0] or {}).keys()) if rows else []),
        "rows": rows,
        "raw": data,
    }


# Alias kept because some plans/tools may emit this name
def run_query_report(report_name: str, filters: dict | None = None) -> dict:
    return run_report(report_name, filters)
