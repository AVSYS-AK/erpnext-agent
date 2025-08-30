# apps/ai_agent/ai_agent/presets.py
from __future__ import annotations

# Curated “management questions” preset pack
PRESETS = [
  {"label": "Sales vs target (Today)", "prompt": "sales today vs target vs same weekday last week by hour", "cat": "Sales"},
  {"label": "Pipeline coverage (MTD)", "prompt": "pipeline coverage this month by stage; flag deals slipping >7 days", "cat": "Sales"},
  {"label": "Top customers (YTD)", "prompt": "top 10 customers by revenue and gross margin this year", "cat": "Sales"},
  {"label": "New vs returning (L12M)", "prompt": "sales by customer_type (new/returning) by month last 12 months", "cat": "Sales"},
  {"label": "Win rate & cycle", "prompt": "win rate and average cycle length by sales channel and owner last 6 months", "cat": "Sales"},

  {"label": "Vendor spend (L12M)", "prompt": "purchases by supplier last 12 months", "cat": "Purchasing"},
  {"label": "Lead time drift", "prompt": "average PO→PR lead time by supplier vs last quarter", "cat": "Purchasing"},
  {"label": "Supplier scorecard", "prompt": "supplier on-time %, price variance vs last 3 POs, and NCR count last 90 days", "cat": "Purchasing"},

  {"label": "Stockout risk (14d)", "prompt": "stockout risk next 14 days considering open Sales Orders and lead times", "cat": "Inventory"},
  {"label": "Dead stock", "prompt": "items with zero movement >120 days and current stock > 0", "cat": "Inventory"},
  {"label": "Margin by line (L12M)", "prompt": "gross margin % by item_group and region last 12 months", "cat": "Inventory"},

  {"label": "Capacity & bottlenecks", "prompt": "work center capacity utilization, WIP aging, bottlenecks this week", "cat": "Manufacturing"},
  {"label": "Returns & causes", "prompt": "returns rate and top 5 root causes by item last quarter", "cat": "Quality"},

  {"label": "AR ageing – owners", "prompt": "accounts receivable aging with top 20 overdue and assigned owners", "cat": "Finance"},
  {"label": "Cash runway (90d)", "prompt": "cash balance and 90-day runway projection from last 90 days burn", "cat": "Finance"},
  {"label": "Control exceptions", "prompt": "backdated entries, price overrides, manual JEs > 100000 last 30 days", "cat": "Finance"},

  {"label": "Project margin", "prompt": "project gross margin and variance vs estimate; list negative margin projects", "cat": "Projects"},
  {"label": "Rev/FTE & utilization", "prompt": "revenue per FTE MTD and billable utilization by team last month", "cat": "People"},

  {"label": "Support health", "prompt": "CSAT trend, SLA breaches last 30 days, churn risk accounts from tickets", "cat": "Support"},
  {"label": "4-week forecast", "prompt": "forecast next 4 weeks: sales, purchases, cash balance with 80% CI", "cat": "Forecast"},
]

PRO_TIPS = [
  "Always include company and date window when it matters: e.g. “for Acme from 2025-04-01 to 2025-06-30”.",
  "Ask for the grouping you want: “by month”, “by item_group”, “by region”, “by owner”.",
  "Use keywords like “vs target”, “YoY”, “L12M”, “MTD”, “QTD” to get comparative views.",
  "For speed, keep LLM temperature low (LLM_TEMPERATURE=0.1) and use mistral:instruct locally.",
  "Save useful queries as Script/Query Reports for 1-click re-use and scheduling.",
]
