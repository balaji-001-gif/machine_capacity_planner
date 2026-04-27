"""
manpower_capacity.py
====================
Capacity scoring for human-staffed Workstations (Stores, Quality, Verify, Assembly).

Instead of machine run-hours, tracks:
  Available man-hours = shift_hours × operators_count
  Committed man-hours = Σ (time_in_mins / 60) across open Job Cards at this station
  Utilisation        = committed / available × 100

Returns the same dict shape as get_machine_capacity() for compatibility.
"""

import frappe
from frappe.utils import now_datetime, time_diff_in_hours
from machine_capacity_planner.utils.logger import mcp_logger


def get_manpower_capacity(work_centre: str, start_dt, delivery_deadline) -> dict:
    """
    Returns capacity dict for a human-staffed Workstation.
    Same keys as get_machine_capacity() for scoring compatibility.
    """
    try:
        operators = float(
            frappe.db.get_value("Workstation", work_centre, "custom_operators_count") or 1
        )
        shift_hrs = float(
            frappe.db.get_value("Workstation", work_centre, "total_working_hrs") or 8
        )
    except Exception:
        operators = 1.0
        shift_hrs = 8.0

    available = shift_hrs * operators

    # Sum time_in_mins from open Job Cards at this station
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(time_in_mins / 60.0), 0) AS committed_hrs
        FROM   `tabJob Card`
        WHERE  workstation = %(wc)s
          AND  status IN ('Open', 'Work In Progress')
    """, {"wc": work_centre}, as_dict=True)

    committed = float((result[0]["committed_hrs"] if result else 0) or 0)
    free_hrs  = max(available - committed, 0)
    utilisation = min(committed / available * 100, 100) if available > 0 else 100.0

    try:
        horizon_hrs = max(time_diff_in_hours(delivery_deadline, start_dt), 1.0)
    except Exception:
        horizon_hrs = shift_hrs

    earliest_free = max(committed - available, 0) if committed > available else 0.0

    mcp_logger.debug(
        f"[MCP MAN] {work_centre} | ops={operators} shift={shift_hrs}h "
        f"committed={committed:.2f}h free={free_hrs:.2f}h util={utilisation:.1f}%"
    )

    return {
        "utilisation":        round(utilisation, 2),
        "free_hrs":           round(free_hrs, 2),
        "committed_hrs":      round(committed, 2),
        "gross_hrs":          round(available, 2),
        "earliest_free":      round(earliest_free, 2),
        "horizon_hrs":        round(horizon_hrs, 2),
        "has_maint":          0,      # no maintenance concept for manpower
        "material_delay_hrs": 0.0,    # materials checked before this point
        "resource_type":      "Manpower",
    }


def get_all_manpower_station_loads() -> list:
    """
    Returns man-hour utilisation for every active Manpower Workstation.
    Called by the Planning Board Manpower Panel API.
    """
    stations = frappe.get_list(
        "Workstation",
        filters={"custom_resource_type": "Manpower", "disabled": 0, "is_group": 0},
        fields=["name", "custom_operators_count", "total_working_hrs"],
    )

    results = []
    for s in stations:
        cap = get_manpower_capacity(s.name, now_datetime(), now_datetime())
        queue_depth = frappe.db.count(
            "Job Card",
            {"workstation": s.name, "status": ["in", ["Open", "Work In Progress"]]},
        )
        results.append({
            "name":          s.name,
            "operators":     s.custom_operators_count or 1,
            "gross_hrs":     cap["gross_hrs"],
            "committed_hrs": cap["committed_hrs"],
            "free_hrs":      cap["free_hrs"],
            "utilisation":   cap["utilisation"],
            "queue_depth":   queue_depth,
            "resource_type": "Manpower",
        })

    return sorted(results, key=lambda x: x["utilisation"], reverse=True)
