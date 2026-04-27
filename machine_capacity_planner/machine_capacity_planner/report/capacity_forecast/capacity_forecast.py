"""Capacity Forecast — daily machine load projection."""
import frappe
from frappe.utils import today, add_days
from machine_capacity_planner.utils.machine_selector import (
    get_machine_capacity,
    _get_candidate_machines,
)


def execute(filters=None):
    return get_columns(filters), get_data(filters)


def get_columns(filters):
    days = int((filters or {}).get("forecast_days", 7))
    cols = [
        {
            "fieldname": "machine",
            "label":     "Machine",
            "fieldtype": "Link",
            "options":   "Workstation",
            "width":     130,
        },
    ]
    for i in range(days):
        d = add_days(today(), i)
        cols.append({
            "fieldname": f"day_{i}",
            "label":     str(d)[5:],   # MM-DD format
            "fieldtype": "Percent",
            "width":     75,
        })
    return cols


def get_data(filters):
    days   = int((filters or {}).get("forecast_days", 7))
    groups = frappe.get_list(
        "Workstation",
        filters={"is_group": 1, "disabled": 0},
        fields=["name"],
    )
    rows = []

    for grp in groups:
        for m in _get_candidate_machines(grp.name):
            row = {"machine": m.name}
            for i in range(days):
                start = add_days(today(), i)
                end   = add_days(today(), i + 1)
                cap   = get_machine_capacity(m.name, start, end)
                row[f"day_{i}"] = round(cap["utilisation"], 1)
            rows.append(row)

    return rows
