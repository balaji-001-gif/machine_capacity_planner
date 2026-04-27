"""Server-side page controller."""
import frappe


@frappe.whitelist()
def get_page_context():
    return {
        "title": "Capacity Planning Board",
        "groups": frappe.get_list(
            "Workstation",
            filters={"is_group": 1, },
            fields=["name"],
            pluck="name",
        ),
    }
