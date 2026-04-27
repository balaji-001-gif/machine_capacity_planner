"""
job_card.py
===========
Fires when a Job Card is submitted (completed).
Unlocks the next sequential Job Card for the same Work Order.
"""

import frappe
from machine_capacity_planner.utils.logger import mcp_logger


def on_submit(doc, method=None):
    """When a Job Card completes, unlock the next one in sequence."""
    _unlock_next_job_card(doc)
    mcp_logger.info(
        f"[MCP] Job Card {doc.name} completed on {doc.workstation}"
    )


def _unlock_next_job_card(completed_jc):
    """
    Find the next Job Card for the same Work Order (ordered by creation time)
    and move its status from 'Pending' to 'Open' so operators can start it.
    """
    wo_name = completed_jc.work_order
    if not wo_name:
        return

    all_jcs = frappe.get_list(
        "Job Card",
        filters={"work_order": wo_name},
        fields=["name", "operation", "status", "creation"],
        order_by="creation asc",
    )

    completed_idx = next(
        (i for i, jc in enumerate(all_jcs) if jc.name == completed_jc.name),
        None,
    )

    if completed_idx is not None and completed_idx + 1 < len(all_jcs):
        next_jc = all_jcs[completed_idx + 1]
        if next_jc.status == "Pending":
            frappe.db.set_value("Job Card", next_jc.name, "status", "Open")
            mcp_logger.info(
                f"[MCP] Unlocked next JC {next_jc.name} "
                f"(op={next_jc.operation}) for WO {wo_name}"
            )
