"""Machine Selection Audit — scoring breakdown per assignment."""
import frappe


def execute(filters=None):
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"fieldname": "creation",          "label": "Timestamp",        "fieldtype": "Datetime",  "width": 145},
        {"fieldname": "operation",         "label": "Operation",        "fieldtype": "Link",      "options": "Operation", "width": 130},
        {"fieldname": "selected_machine",  "label": "Assigned Machine", "fieldtype": "Link",      "options": "Work Centre", "width": 130},
        {"fieldname": "score",             "label": "Score",            "fieldtype": "Float",     "width": 70},
        {"fieldname": "utilisation_pct",   "label": "Util %",           "fieldtype": "Percent",   "width": 80},
        {"fieldname": "free_hours",        "label": "Free Hrs",         "fieldtype": "Float",     "width": 80},
        {"fieldname": "runner_up_machine", "label": "Runner-Up",        "fieldtype": "Link",      "options": "Work Centre", "width": 130},
        {"fieldname": "runner_up_score",   "label": "Runner-Up Score",  "fieldtype": "Float",     "width": 110},
        {"fieldname": "allocated_by",      "label": "Method",           "fieldtype": "Data",      "width": 130},
    ]


def get_data(filters):
    conds = {}
    if filters and filters.get("from_date"):
        conds["creation"] = [">=", filters["from_date"]]
    if filters and filters.get("machine"):
        conds["selected_machine"] = filters["machine"]

    return frappe.get_list(
        "Machine Selection Log",
        filters=conds,
        fields=[
            "creation", "operation", "selected_machine", "score",
            "utilisation_pct", "free_hours",
            "runner_up_machine", "runner_up_score", "allocated_by",
        ],
        order_by="creation desc",
        limit=500,
    )
