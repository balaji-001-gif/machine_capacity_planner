"""Server-side page controller."""
import frappe


@frappe.whitelist()
def get_page_context():
    return {
        "title": "Capacity Planning Board",
        "groups": frappe.get_list(
            "Work Centre",
            filters={"is_group": 1, "disabled": 0},
            fields=["name"],
            pluck="name",
        ),
    }
