import frappe

@frappe.whitelist()
def validate_warranty_claim(doc, method=None):
    if getattr(doc, "serial_no", None):
        exists = frappe.db.exists("Serial No", {"name": doc.serial_no})
        if not exists:
            frappe.throw(f"Serial No {doc.serial_no} does not exist")
    valid = ["Draft","Under Review","Approved","Rejected","Closed"]
    if doc.status not in valid:
        frappe.throw("Invalid status")
