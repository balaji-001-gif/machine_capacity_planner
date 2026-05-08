"""Custom permission logic for Machine Capacity Planner doctypes."""
import frappe


def has_permission(doc, ptype="read", user=None):
    """
    Manufacturing Manager and System Manager can read all logs.
    Other roles get read-only access.
    """
    roles = frappe.get_roles(user)
    if "System Manager" in roles or "Manufacturing Manager" in roles:
        return True
    if ptype == "read":
        return True
    return False
