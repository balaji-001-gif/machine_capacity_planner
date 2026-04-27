"""
Material Machine Alignment — shows gap between material arrival and machine free slot.

Positive gap_hrs = machine is free but waiting for materials (waste).
Negative gap_hrs = materials arrive before machine is free (ideal buffer).
"""
import frappe
from frappe.utils import now_datetime, time_diff_in_hours
from machine_capacity_planner.utils.mrp_checker import get_material_readiness, _ready_result
from machine_capacity_planner.utils.machine_selector import _get_settings


def execute(filters=None):
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"fieldname": "work_order",        "label": "Work Order",       "fieldtype": "Link",   "options": "Work Order",   "width": 140},
        {"fieldname": "item",              "label": "Item",             "fieldtype": "Link",   "options": "Item",         "width": 120},
        {"fieldname": "workstation",       "label": "Machine Assigned", "fieldtype": "Link",   "options": "Workstation",  "width": 130},
        {"fieldname": "machine_free_at",   "label": "Machine Free At",  "fieldtype": "Datetime","width": 140},
        {"fieldname": "material_ready_at", "label": "Material Ready At","fieldtype": "Datetime","width": 140},
        {"fieldname": "gap_hrs",           "label": "Gap (hrs)",        "fieldtype": "Float",  "width": 90,
         "description": "+ve = machine waits for material; -ve = ideal buffer"},
        {"fieldname": "material_status",   "label": "Material Status",  "fieldtype": "Data",   "width": 100},
        {"fieldname": "alignment_status",  "label": "Alignment",        "fieldtype": "Data",   "width": 130},
        {"fieldname": "readiness_pct",     "label": "Material Ready %", "fieldtype": "Percent","width": 110},
    ]


def get_data(filters):
    settings  = _get_settings()
    warehouse = settings.get("material_check_warehouse", "")
    status_filter = (filters or {}).get("status", "All")

    open_jcs = frappe.get_list(
        "Job Card",
        filters={"status": ["in", ["Open", "Work In Progress"]]},
        fields=["name", "work_order", "workstation", "planned_start_time", "planned_end_time"],
    )

    rows = []
    seen_wo = set()

    for jc in open_jcs:
        wo = jc.work_order
        if not wo or wo in seen_wo:
            continue
        seen_wo.add(wo)

        item = frappe.db.get_value("Work Order", wo, "production_item")

        # machine free at = planned end of current last job on workstation
        machine_free_at = jc.planned_end_time or now_datetime()

        mat = get_material_readiness(wo, machine_free_at, warehouse) if warehouse else _ready_result()

        material_ready_at = mat.get("expected_arrival")
        gap_hrs = 0.0
        if material_ready_at:
            gap_hrs = round(time_diff_in_hours(material_ready_at, machine_free_at), 2)

        if gap_hrs > 0.5:
            alignment = "Machine Waits"
        elif gap_hrs < -1:
            alignment = "Aligned"
        elif mat["status"] == "Blocked":
            alignment = "Blocked"
        else:
            alignment = "Aligned"

        if status_filter not in ("", "All") and alignment != status_filter:
            continue

        rows.append({
            "work_order":        wo,
            "item":              item,
            "workstation":       jc.workstation,
            "machine_free_at":   machine_free_at,
            "material_ready_at": material_ready_at,
            "gap_hrs":           gap_hrs,
            "material_status":   mat["status"],
            "alignment_status":  alignment,
            "readiness_pct":     mat["readiness_pct"],
        })

    # Sort: worst misalignment first
    rows.sort(key=lambda r: r["gap_hrs"], reverse=True)
    return rows
