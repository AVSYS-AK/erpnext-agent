<<paste the README from above>>
# AI Agent (Frappe/ERPNext)

Agentic console + Growth Dashboard for ERPNext:
- Ask Anything (rich tables/HTML, CSV export)
- Presets (management-ready prompts)
- Growth KPIs with explanations
- Ollama/Mistral local LLM friendly

## Dev Quickstart

```bash
# 1) Clone bench & install deps (standard Frappe steps)

# 2) Get this app into your bench:
bench get-app ai_agent https://github.com/<you>/<repo>.git

# 3) Install on your site:
bench --site <yoursite> install-app ai_agent
bench build
bench restart

# 4) (Optional) Start Ollama + Mistral
cd deploy/ollama && docker compose up -d

# 5) Open:
# Desk → Search "AI Agent Console"
