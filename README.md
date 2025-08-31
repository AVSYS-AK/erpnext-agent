# ERPNext + Frappe + `ai_agent` + Ollama (Mistral) — No-Docker, Copy-Paste Guide

This README lets you deploy **Frappe/ERPNext v15**, your **`ai_agent`** app, and a **local LLM via Ollama (`mistral:instruct`)** on a fresh Ubuntu server **without Docker**. It includes production setup (Supervisor + Nginx), rich “AI Agent Console” UI, optional RAG ingestion, and battle-tested troubleshooting.

---

## 0) Requirements

* **OS:** Ubuntu 22.04/24.04 LTS
* **Minimum:** 4 vCPU, 8–16 GB RAM, 40+ GB disk (add swap if RAM is tight)
* **Network:** Ports 22, 80, 443 open if using HTTPS

**Optional: add 8G swap**

```bash
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo swapon -a && free -h
```

---

## 1) Create user & install base packages

```bash
# as root
adduser frappe
usermod -aG sudo frappe
su - frappe

sudo apt update
sudo apt -y install git curl build-essential python3.10 python3.10-dev python3.10-venv \
  redis-server mariadb-server mariadb-client \
  libffi-dev libssl-dev libjpeg-dev zlib1g-dev libmysqlclient-dev \
  xvfb libfontconfig wkhtmltopdf jq
```

> `wkhtmltopdf` is needed for PDFs.

---

## 2) Node 18 + Yarn 1.x

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
corepack enable
corepack prepare yarn@1.22.19 --activate
```

---

## 3) Install Bench & tune MariaDB

```bash
python3.10 -m pip install --user pipx
~/.local/bin/pipx ensurepath
exec $SHELL -l
pipx install frappe-bench==5.*
```

MariaDB config (required for Frappe):

```bash
sudo tee /etc/mysql/conf.d/frappe.cnf >/dev/null <<'CNF'
[mysqld]
skip-name-resolve
sql-mode = ""
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
max_connections = 500
innodb-file-per-table = 1
CNF

sudo systemctl restart mariadb
```

---

## 4) Initialize bench & fetch apps

```bash
bench init --frappe-branch version-15 ~/frappe-bench
cd ~/frappe-bench

# ERPNext v15
bench get-app --branch version-15 https://github.com/frappe/erpnext

# Your app repo (contains ai_agent)
bench get-app https://github.com/AVSYS-AK/erpnext-agent.git
```

> If you accidentally committed nested repos inside your bench (e.g., under `knowledge/`), see **Troubleshooting → Git “embedded repository”** at the end.

---

## 5) Create site & install apps

```bash
bench new-site erp.local
# Follow prompts: DB root password, Admin password

bench --site erp.local install-app erpnext
bench --site erp.local install-app ai_agent
```

**Dev preview (optional):**

```bash
bench start
# open http://127.0.0.1:8000
```

---

## 6) Install Ollama & pull Mistral

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama pull mistral:instruct
```

Verify:

```bash
curl -s http://127.0.0.1:11434/v1/models | jq .
# should list "mistral:instruct"
```

---

## 7) Wire site to local LLM

```bash
bench --site erp.local set-config LLM_MODEL "mistral:instruct"
bench --site erp.local set-config LLM_BASE_URL "http://127.0.0.1:11434/v1"
bench --site erp.local set-config LLM_API_KEY "ollama"   # any string works for Ollama
bench restart
```

---

## 8) Production (Supervisor + Nginx + optional TLS)

```bash
sudo bench setup production frappe
```

**Optional: HTTPS via Let’s Encrypt (real domain required)**

```bash
bench config dns_multitenant on
bench --site erp.local set-config host_name https://erp.example.com
sudo bench setup lets-encrypt erp.local
```

---

## 9) AI Console assets & hooks

Your page script must live here:

```
apps/ai_agent/ai_agent/ai_agent/page/ai_agent_console/ai_agent_console.js
```

Keep `hooks.py` simple:

```python
# apps/ai_agent/ai_agent/hooks.py
app_name = "ai_agent"
app_title = "AI Agent"
app_publisher = "Proxta"
app_description = "Agentic AI for Frappe/ERPNext (planner, tools, console)"
app_email = "eng@proxta.in"
app_license = "MIT"
app_version = "0.1.0"

scheduler_events = {
    "cron": {
        "0 */3 * * *": ["ai_agent.escalations.escalate_warranty_stale"],
        "0 7 * * *":   ["ai_agent.api.daily_reports_ist"],
    }
}

doc_events = {
    "Warranty Claim": {
        "validate": "ai_agent.warranty_claim_hooks.validate_warranty_claim"
    }
}

after_install = "ai_agent.install.after_install"
```

Rebuild assets:

```bash
bench build --app ai_agent
bench clear-cache
bench restart
```

---

## 10) Sanity checks (server-side)

```bash
bench --site erp.local execute ai_agent.presets_api.list_presets
bench --site erp.local execute ai_agent.presets_api.metric_sales_mtd --kwargs '{"company":"Your Company"}'
bench --site erp.local execute ai_agent.presets_api.metric_purchases_mtd --kwargs '{"company":"Your Company"}'
bench --site erp.local execute ai_agent.presets_api.metric_ar_overdue --kwargs '{"company":"Your Company"}'
bench --site erp.local execute ai_agent.presets_api.metric_stockout_14d --kwargs '{"company":"Your Company"}'
bench --site erp.local execute ai_agent.api.run_rich --kwargs '{"command_text":"top 10 customers by revenue this year","dry_run":1}'
```

Open the console UI:

```
/app/ai_agent_console
```

---

## 11) (Optional) RAG: ingest docs & ask

```bash
bench --site erp.local execute ai_agent.api.ingest --kwargs '{"paths": "/home/frappe/frappe-bench/knowledge/frappe_docs,/home/frappe/frappe-bench/knowledge/erpnext/docs"}'
bench --site erp.local execute ai_agent.api.ask --kwargs '{"question":"How do I add a Workflow to a DocType in ERPNext?","k":6}'
```

---

## 12) Git hygiene & pushing to GitHub

Recommended to commit:

* `apps/ai_agent/**`
* `sites/common_site_config.json`
* `Procfile`, `README.md`, `.gitignore`, `patches.txt`

Do **not** commit:

* `apps/frappe`, `apps/erpnext`
* `assets/`, `node_modules/`, `logs/`, backups
* `.ollama/` and model files
* Huge `knowledge/` trees

`.gitignore` example:

```
__pycache__/
*.pyc
node_modules/
assets/
sites/*/public/**
sites/*/private/**
sites/*/logs/**
sites/*/backups/**
config/pids/
.venv/
.env
.ollama/
knowledge/*
```

Push with PAT:

```bash
git init
git add .gitignore README.md Procfile patches.txt
git add config/ knowledge/ sites/common_site_config.json apps/ai_agent
git commit -m "chore: bench config + ai_agent app (initial)"
git branch -M main
git remote add origin https://github.com/YourOrg/erpnext-agent.git
git push -u https://<YOUR_PAT>@github.com/YourOrg/erpnext-agent.git main
```

---

## 13) Updating later

```bash
cd ~/frappe-bench
bench update --reset
bench restart

ollama pull mistral:instruct
```

---

## 14) Troubleshooting

**Page is blank / 404 for `ai_agent_console.js`**

```bash
bench build --app ai_agent
bench clear-cache
bench restart
```

**Console logs show `page.set_title is not a function`**

Check your page script location.

**SocketIO `:9000` xhr poll errors**

Harmless in dev mode. Use Supervisor in production.

**LLM error: `model "... not found"`**

```bash
ollama pull mistral:instruct
bench --site erp.local set-config LLM_MODEL "mistral:instruct"
bench restart
```

**Slow responses**

Use quantized model or add RAM/swap.

**SQL `%Y-%m` format error**

Use double `%` in f-strings: `%%Y-%%m`

**“Failed to get method for command ...”**

```bash
bench build --app ai_agent
bench clear-cache
bench restart
```

**Git “embedded repository” warnings**

```bash
find knowledge -type d -name ".git" -exec rm -rf {} +
git rm -r --cached knowledge || true
echo "knowledge/*" >> .gitignore
git add . && git commit -m "chore: ignore nested repos under knowledge"
```

---

## 15) Handy scripts (optional)

`scripts/setup_ollama.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
sudo systemctl enable --now ollama
ollama pull mistral:instruct
curl -s http://127.0.0.1:11434/v1/models | jq . | grep -q "mistral:instruct" && echo "Ollama OK"
```

`scripts/wire_llm_to_site.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
SITE="${1:-erp.local}"
bench --site "$SITE" set-config LLM_MODEL "mistral:instruct"
bench --site "$SITE" set-config LLM_BASE_URL "http://127.0.0.1:11434/v1"
bench --site "$SITE" set-config LLM_API_KEY "ollama"
bench restart
```

---

### URLs to know

* ERPNext Desk: `/app`
* **AI Agent Console:** `/app/ai_agent_console`

---

That’s it. Paste-run the blocks in order on any Ubuntu 22.04/24.04 server and you’ll have a clean, reproducible, no-Docker deployment with a local Mistral model powering your `ai_agent`.
