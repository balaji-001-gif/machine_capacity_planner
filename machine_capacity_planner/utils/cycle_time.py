"""
cycle_time.py
=============
Full part cycle time calculator — sums machine hours + man-hours across
all operations in a Work Order's routing.

Used by:
  - Planning Board "Cycle Time per FG Part" panel
  - api/capacity.py  get_work_order_cycle_times()
"""

import frappe
from frappe.utils import now_datetime, time_diff_in_hours
from machine_capacity_planner.utils.logger import mcp_logger


def get_full_cycle_time(work_order: str) -> dict:
    """
    Returns machine + man-hour breakdown for a Work Order.

    Returns
    -------
    {
        work_order        : str
        total_machine_hrs : float
        total_man_hrs     : float
        total_cycle_hrs   : float
        total_ops         : int
        completed_ops     : int
        pct_complete      : float
        current_op        : dict or None   {operation, workstation, resource_type}
        overdue_ops       : list[dict]     [{operation, workstation, delay_hrs}]
        has_overdue       : bool
        operations        : list[dict]     full per-op breakdown
    }
    """
    jcs = frappe.get_list(
        "Job Card",
        filters={"work_order": work_order},
        fields=[
            "name", "operation", "workstation", "status",
            "expected_start_date", "expected_end_date",
            "time_in_mins", "sequence_id",
        ],
        order_by="sequence_id asc",
    )

    total_machine_hrs = 0.0
    total_man_hrs     = 0.0
    completed         = 0
    current_op        = None
    overdue_ops       = []
    operations        = []
    now               = now_datetime()

    for jc in jcs:
        rtype  = frappe.db.get_value(
            "Workstation", jc.workstation, "custom_resource_type"
        ) or "Machine"
        op_hrs = float(jc.time_in_mins or 0) / 60.0

        if rtype == "Manpower":
            total_man_hrs += op_hrs
        else:
            total_machine_hrs += op_hrs

        if jc.status == "Submitted":
            completed += 1
        elif jc.status in ("Open", "Work In Progress") and current_op is None:
            current_op = {
                "operation":     jc.operation,
                "workstation":   jc.workstation,
                "resource_type": rtype,
            }

        # Detect overdue
        if (
            jc.status in ("Open", "Work In Progress")
            and jc.expected_end_date
            and jc.expected_end_date < now
        ):
            delay = time_diff_in_hours(now, jc.expected_end_date)
            overdue_ops.append({
                "operation":   jc.operation,
                "workstation": jc.workstation,
                "delay_hrs":   round(delay, 1),
            })

        operations.append({
            "operation":     jc.operation,
            "workstation":   jc.workstation,
            "resource_type": rtype,
            "status":        jc.status,
            "hours":         round(op_hrs, 2),
        })

    total_ops    = len(jcs)
    pct_complete = round(completed / total_ops * 100, 1) if total_ops else 0.0

    return {
        "work_order":        work_order,
        "total_machine_hrs": round(total_machine_hrs, 2),
        "total_man_hrs":     round(total_man_hrs, 2),
        "total_cycle_hrs":   round(total_machine_hrs + total_man_hrs, 2),
        "total_ops":         total_ops,
        "completed_ops":     completed,
        "pct_complete":      pct_complete,
        "current_op":        current_op,
        "overdue_ops":       overdue_ops,
        "has_overdue":       len(overdue_ops) > 0,
        "operations":        operations,
    }


def get_all_active_cycle_times() -> list:
    """Returns cycle time summary for all open Work Orders (Planning Board)."""
    open_wos = frappe.get_list(
        "Work Order",
        filters={"status": ["in", ["Not Started", "In Process"]]},
        fields=["name", "production_item", "expected_delivery_date", "qty"],
    )

    results = []
    for wo in open_wos:
        try:
            ct = get_full_cycle_time(wo.name)
            results.append({
                **ct,
                "production_item":        wo.production_item,
                "expected_delivery_date": wo.expected_delivery_date,
                "qty":                    wo.qty,
            })
        except Exception as e:
            mcp_logger.error(f"[MCP CT] Error computing cycle time for {wo.name}: {e}")

    # Sort: overdue WOs first, then lowest % complete first
    results.sort(key=lambda x: (-len(x["overdue_ops"]), x["pct_complete"]))
    return results
