"""
rebalancer.py
=============
Scheduled task: re-evaluate all open auto-assigned Job Cards.

Re-assigns only when improvement >= rebalance_threshold points,
preventing oscillation / thrashing between close-scored machines.

Called by hooks.py cron: "*/30 6-22 * * 1-6"
"""

import frappe
from frappe.utils import now_datetime
from machine_capacity_planner.utils.machine_selector import (
    select_best_machine,
    _get_settings,
)
from machine_capacity_planner.utils.logger import mcp_logger


def auto_rebalance_machines():
    """
    Entry point — called by Frappe scheduler every 30 minutes.
    Iterates all open, auto-assigned Job Cards and reassigns where warranted.
    """
    settings  = _get_settings()
    threshold = settings.get("rebalance_threshold", 10)

    open_jcs  = _get_rebalanceable_job_cards()
    if not open_jcs:
        mcp_logger.debug("[MCP Rebalancer] No Job Cards to rebalance.")
        return

    reassigned = 0
    skipped    = 0

    for jc in open_jcs:
        try:
            wo       = frappe.get_cached_doc("Work Order", jc.work_order)
            delivery = wo.expected_delivery_date

            new_best = select_best_machine(
                operation         = jc.operation,
                start_dt          = now_datetime(),
                delivery_deadline = delivery,
                required_hours    = 1.0,
            )

            if not new_best:
                skipped += 1
                continue

            # Fetch the score stored when machine was last assigned
            current_score = (
                frappe.db.get_value("Job Card", jc.name, "custom_machine_score")
                or 999
            )
            improvement = float(current_score) - new_best["score"]

            if (
                new_best["name"] != jc.workstation
                and improvement >= threshold
            ):
                old_machine = jc.workstation
                frappe.db.set_value("Job Card", jc.name, {
                    "workstation":          new_best["name"],
                    "custom_machine_score": new_best["score"],
                    "custom_allocated_by":  "AUTO-REBALANCE",
                })
                reassigned += 1
                mcp_logger.info(
                    f"[MCP Rebalancer] JC {jc.name}: "
                    f"{old_machine} → {new_best['name']} "
                    f"(improvement: {improvement:.1f} pts)"
                )
            else:
                skipped += 1

        except Exception as e:
            mcp_logger.error(f"[MCP Rebalancer] Error on JC {jc.name}: {e}")

    frappe.db.commit()
    mcp_logger.info(
        f"[MCP Rebalancer] Complete. "
        f"Reassigned={reassigned}, Skipped={skipped}"
    )

    if reassigned > 10:
        _alert_high_rebalance_count(reassigned, settings)


def _get_rebalanceable_job_cards():
    """Fetch open, auto-assigned Job Cards that have not started yet."""
    return frappe.get_list(
        "Job Card",
        filters={
            "status":              "Open",
            "custom_allocated_by": ["in", ["AUTO", "AUTO-REBALANCE"]],
        },
        fields=[
            "name", "operation", "workstation",
            "work_order", "planned_start_time", "planned_end_time",
        ],
    )


def _alert_high_rebalance_count(count: int, settings: dict):
    """Notify manager when rebalancing activity is unusually high."""
    manager = settings.get("manager_email")
    if not manager:
        return
    frappe.sendmail(
        recipients=[manager],
        subject=f"[MCP] High rebalance activity: {count} Job Cards reassigned",
        message=f"""
<p>The Machine Capacity Planner rebalancer reassigned
<strong>{count}</strong> Job Cards in the last 30-minute cycle.</p>
<p>This may indicate machine instability or a large shift in production load.</p>
<p>Review the
<a href="/app/machine-selection-log">Machine Selection Log</a>
for details.</p>
        """,
        now=True,
    )
