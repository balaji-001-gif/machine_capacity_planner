"""
REST API endpoints for the Capacity Planning Board.

All methods require authenticated ERPNext session.
Accessible at:
  /api/method/machine_capacity_planner.api.capacity.<function_name>
"""

import frappe
from frappe.utils import now_datetime, add_days
from machine_capacity_planner.utils.machine_selector import (
    get_machine_capacity,
    _get_candidate_machines,
    _get_settings,
)


@frappe.whitelist()
def get_group_capacity(wc_group: str, horizon_days: int = 1) -> dict:
    """
    Return capacity metrics for all machines in a Workstation Group.

    GET /api/method/machine_capacity_planner.api.capacity.get_group_capacity
        ?wc_group=CNC-GROUP&horizon_days=2

    Response:
    {
      "group": "CNC-GROUP",
      "machines": [
        { "name": "MCH-01", "utilisation": 78.5, "free_hrs": 3.5, ... },
        ...
      ],
      "summary": { "avg_utilisation": 65.2, "total_free_hrs": 9.0, "machine_count": 3 }
    }
    """
    frappe.has_permission("Workstation", throw=True)

    machines  = _get_candidate_machines(wc_group)
    start_dt  = now_datetime()
    end_dt    = add_days(start_dt, int(horizon_days))
    results   = []

    for m in machines:
        cap = get_machine_capacity(m.name, start_dt, end_dt)
        results.append({"name": m.name, **cap})

    avg_util   = sum(r["utilisation"] for r in results) / len(results) if results else 0
    total_free = sum(r["free_hrs"] for r in results)

    return {
        "group":    wc_group,
        "machines": results,
        "summary": {
            "avg_utilisation": round(avg_util, 2),
            "total_free_hrs":  round(total_free, 2),
            "machine_count":   len(results),
        },
    }


@frappe.whitelist()
def get_all_groups_capacity(horizon_days: int = 1) -> list:
    """Return capacity for ALL Workstation Groups in one call."""
    frappe.has_permission("Workstation", throw=True)

    groups = frappe.get_list(
        "Workstation",
        filters={"is_group": 1, },
        fields=["name"],
    )
    return [get_group_capacity(g.name, horizon_days) for g in groups]


@frappe.whitelist()
def get_job_card_queue(workstation: str) -> list:
    """Return all pending/in-progress Job Cards for a specific machine."""
    frappe.has_permission("Job Card", throw=True)

    return frappe.get_list(
        "Job Card",
        filters={
            "workstation": workstation,
            "status": ["in", ["Open", "Work In Progress"]],
        },
        fields=[
            "name", "operation", "work_order", "for_quantity",
            "expected_start_date", "expected_end_date",
            "status", "custom_machine_score",
        ],
        order_by="expected_start_date asc",
    )


@frappe.whitelist()
def trigger_rebalance() -> dict:
    """Manually trigger the machine rebalancing job. Manager only."""
    frappe.has_permission("Machine Selection Settings", throw=True)

    from machine_capacity_planner.tasks.rebalancer import auto_rebalance_machines
    auto_rebalance_machines()

    return {
        "status":  "ok",
        "message": "Rebalancing complete. Check Machine Selection Log for results.",
    }
