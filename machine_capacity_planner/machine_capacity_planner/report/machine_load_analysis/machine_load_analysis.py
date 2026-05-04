"""Machine Load Analysis — utilisation per machine over a date range."""
import frappe
from machine_capacity_planner.utils.machine_selector import (
    get_machine_capacity,
    _get_candidate_machines,
)


def execute(filters=None):
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"fieldname": "wc_group",       "label": "Group",         "fieldtype": "Data",    "width": 130},
        {"fieldname": "machine",        "label": "Machine",       "fieldtype": "Link",    "options": "Workstation", "width": 120},
        {"fieldname": "gross_hrs",      "label": "Gross Hrs",     "fieldtype": "Float",   "width": 100},
        {"fieldname": "committed_hrs",  "label": "Booked Hrs",    "fieldtype": "Float",   "width": 100},
        {"fieldname": "free_hrs",       "label": "Free Hrs",      "fieldtype": "Float",   "width": 90},
        {"fieldname": "utilisation",    "label": "Utilisation %", "fieldtype": "Percent", "width": 110},
        {"fieldname": "job_card_count", "label": "Job Cards",     "fieldtype": "Int",     "width": 90},
        {"fieldname": "status",         "label": "Status",        "fieldtype": "Data",    "width": 110},
    ]


def get_data(filters):
    from_date = (filters or {}).get("from_date") or frappe.utils.today()
    to_date   = (filters or {}).get("to_date")   or frappe.utils.add_days(from_date, 7)

    groups = frappe.get_list(
        "Workstation",
        filters={"is_group": 1, },
        fields=["name"],
    )
    rows = []

    for grp in groups:
        for m in _get_candidate_machines(grp.name):
            cap      = get_machine_capacity(m.name, from_date, to_date)
            jc_count = frappe.db.count("Job Card", {
                "workstation": m.name,
                "status": ["in", ["Open", "Work In Progress"]],
            })
            status = (
                "Overloaded" if cap["utilisation"] >= 92 else
                "High Load"  if cap["utilisation"] >= 75 else
                "OK"
            )
            rows.append({
                "wc_group":       grp.name,
                "machine":        m.name,
                "gross_hrs":      cap["gross_hrs"],
                "committed_hrs":  cap["committed_hrs"],
                "free_hrs":       cap["free_hrs"],
                "utilisation":    cap["utilisation"],
                "job_card_count": jc_count,
                "status":         status,
            })

    return sorted(rows, key=lambda x: x["utilisation"], reverse=True)
