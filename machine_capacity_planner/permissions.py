"""Custom permission logic for Machine Capacity Planner doctypes."""
import frappe


def has_permission(doc, ptype="read", user=None):
    """
    Manufacturing Manager and System Manager can read all logs.
    Other roles get read-only access.
    """
    if frappe.has_role("System Manager") or frappe.has_role("Manufacturing Manager"):
        return True
    if ptype == "read":
        return True
    return False
