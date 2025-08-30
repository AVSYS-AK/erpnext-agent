import frappe

def ensure_role(role_name: str):
    if not frappe.db.exists("Role", {"role_name": role_name}):
        r = frappe.new_doc("Role")
        r.role_name = role_name
        r.insert(ignore_permissions=True)

def after_install():
    for role in ("AI Agent Admin", "AI Agent Operator", "AI Readonly"):
        ensure_role(role)
