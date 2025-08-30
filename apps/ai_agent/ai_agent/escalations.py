import frappe, datetime as dt

def escalate_warranty_stale():
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=72)
    rows = frappe.db.sql("""
        SELECT name FROM `tabWarranty Claim`
        WHERE status='Under Review' AND modified < %s
    """, (cutoff,), as_dict=True)
    if not rows:
        return
    managers = [d.parent for d in frappe.get_all("Has Role", filters={"role":"Support Manager"}, fields=["parent"])]
    for r in rows:
        doc = frappe.get_doc("Warranty Claim", r["name"])
        if managers:
            frappe.sendmail(recipients=managers,
                            subject=f"Warranty Claim {doc.name} pending > 72h",
                            message="Please review and act.")
