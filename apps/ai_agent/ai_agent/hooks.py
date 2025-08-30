from __future__ import annotations

app_name = "ai_agent"
app_title = "AI Agent"
app_publisher = "Proxta"
app_description = "Agentic AI for Frappe/ERPNext (planner, tools, console)"
app_email = "eng@proxta.in"
app_license = "MIT"
app_version = "0.1.0"

# Keep hooks lean. The Console page JS is auto-loaded from:
# ai_agent/page/ai_agent_console/ai_agent_console.js
# Do NOT include it via app_include_js/web_include_js/page_js to avoid /assets 404s.

page_js = {
    "ai_agent_console": "ai_agent/page/ai_agent_console/ai_agent_console.js"
}

scheduler_events = {
    "cron": {
        "0 */3 * * *": ["ai_agent.escalations.escalate_warranty_stale"],
        "0 7 * * *": ["ai_agent.api.daily_reports_ist"],
    }
}

doc_events = {
    "Warranty Claim": {
        "validate": "ai_agent.warranty_claim_hooks.validate_warranty_claim"
    }
}

after_install = "ai_agent.install.after_install"


# Intentionally no:
# - app_include_js
# - web_include_js
# - page_js
