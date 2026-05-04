"""
work_order.py
=============
Fires when a Work Order is submitted or cancelled.

on_submit  →  auto-assign best machine to every open Job Card
on_cancel  →  release all auto-assigned machines
"""

import frappe
from frappe.utils import now_datetime, time_diff_in_hours
from machine_capacity_planner.utils.machine_selector import select_best_machine
from machine_capacity_planner.utils.logger import mcp_logger


def on_submit(doc, method=None):
    """
    Triggered: Work Order → on_submit

    For every Job Card belonging to this Work Order:
      1. Estimate required hours from planned times (or BOM routing)
      2. Call select_best_machine() with operation + delivery deadline
      3. Write the assigned machine + score back to the Job Card
      4. Show a summary alert to the user
    """
    if doc.docstatus != 1:
        return

    job_cards = frappe.get_list(
        "Job Card",
        filters={"work_order": doc.name, "status": "Open"},
        fields=[
            "name",
            "operation",
            "expected_start_date",
            "expected_end_date",
            "for_quantity",
        ],
    )

    if not job_cards:
        mcp_logger.warning(f"[MCP] No Job Cards found for WO {doc.name}")
        return

    assigned_count = 0

    for jc in job_cards:
        required_hrs = _estimate_required_hours(jc, doc)

        result = select_best_machine(
            operation         = jc.operation,
            start_dt          = jc.expected_start_date or now_datetime(),
            delivery_deadline = doc.expected_delivery_date,
            required_hours    = required_hrs,
            work_order        = doc.name,       # enables MRP material check
        )

        if result:
            frappe.db.set_value("Job Card", jc.name, {
                "workstation":               result["name"],
                "custom_machine_score":       result["score"],
                "custom_allocated_by":        "AUTO",
                "custom_material_status":     result.get("material_status", "Ready"),
                "custom_material_delay_hrs":  result.get("material_delay_hrs", 0),
            })
            assigned_count += 1
            mcp_logger.info(
                f"[MCP] WO {doc.name} | JC {jc.name} → {result['name']} "
                f"(score={result['score']}, mat={result.get('material_status','Ready')})"
            )
        else:
            mcp_logger.error(
                f"[MCP] Could not assign machine to JC {jc.name} "
                f"(op={jc.operation})"
            )

    # Show summary to the ERPNext user
    total     = len(job_cards)
    indicator = "green" if assigned_count == total else "orange"
    frappe.msgprint(
        f"Machine Capacity Planner: {assigned_count}/{total} "
        f"Job Cards auto-assigned.",
        alert=True,
        indicator=indicator,
    )


def on_cancel(doc, method=None):
    """Release machine assignments when a Work Order is cancelled."""
    frappe.db.sql("""
        UPDATE `tabJob Card`
        SET    workstation         = NULL,
               custom_allocated_by = 'CANCELLED'
        WHERE  work_order          = %(wo)s
          AND  custom_allocated_by = 'AUTO'
    """, {"wo": doc.name})

    mcp_logger.info(
        f"[MCP] Released machine assignments for cancelled WO {doc.name}"
    )


def _estimate_required_hours(jc, wo) -> float:
    """
    Estimate hours needed for this Job Card.
    Priority: planned times > BOM operation time > default 1 hr.
    """
    if jc.expected_start_date and jc.expected_end_date:
        hrs = time_diff_in_hours(jc.expected_end_date, jc.expected_start_date)
        return max(hrs, 0.5)

    # Fallback: look up operation time from the BOM
    op_time = frappe.db.get_value(
        "BOM Operation",
        {"parent": wo.bom_no, "operation": jc.operation},
        "time_in_mins",
    )
    if op_time:
        return round(float(op_time) * float(jc.for_quantity or 1) / 60, 2)

    return 1.0  # default
