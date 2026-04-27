"""
machine_selector.py
====================
Core scoring engine for automatic machine selection.

Usage:
    from machine_capacity_planner.utils.machine_selector import select_best_machine

    result = select_best_machine(
        operation="CNC Turning",
        start_dt=frappe.utils.now_datetime(),
        delivery_deadline=wo.expected_delivery_date,
        required_hours=5.0,
    )
    if result:
        frappe.db.set_value("Job Card", jc_name, "workstation", result["name"])

Scoring formula (lower = better):
    F1 = (utilisation% / 100) × W_load
    F2 = min(hours_until_free / horizon, 1) × W_free_slot
    F3 = max(1 - free_hours / horizon, 0) × W_slack
    F4 = has_maintenance (0 or 1) × W_maint
    Total = F1 + F2 + F3 + F4
"""

from typing import Dict, List, Optional

import frappe
from frappe.utils import (
    now_datetime,
    time_diff_in_hours,
    getdate,
    add_to_date,
)
from machine_capacity_planner.utils.logger import mcp_logger


# Lazy import to avoid circular dependency
def _get_manpower_capacity(work_centre, start_dt, delivery_deadline):
    from machine_capacity_planner.utils.manpower_capacity import get_manpower_capacity
    return get_manpower_capacity(work_centre, start_dt, delivery_deadline)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — call these from outside this module
# ─────────────────────────────────────────────────────────────────────────────

def select_best_machine(
    operation: str,
    start_dt,
    delivery_deadline,
    required_hours: float = 1.0,
    work_order: str = None,
) -> Optional[Dict]:
    """
    Entry point: score all candidate machines and return the winner.

    Parameters
    ----------
    operation          : str      — ERPNext Operation name (e.g. "CNC Turning")
    start_dt           : datetime — earliest possible start (usually now)
    delivery_deadline  : date/datetime — hard deadline for job completion
    required_hours     : float    — estimated hours needed for this job

    Returns
    -------
    dict with keys: name, score, free_hrs, utilisation, ...
    None if no candidate found or all machines are overloaded.
    """
    settings = _get_settings()

    # 1. Resolve the Workstation Group for this operation
    wc_group = frappe.db.get_value("Operation", operation, "workstation")
    if not wc_group:
        mcp_logger.warning(
            f"[MCP] No workstation linked to operation '{operation}'"
        )
        return None

    # 2. Fetch all active child machines/stations in the group
    candidates = _get_candidate_machines(wc_group)
    if not candidates:
        mcp_logger.warning(f"[MCP] No active resources found in group '{wc_group}'")
        return None

    # Determine resource type of the group
    resource_type = frappe.db.get_value(
        "Workstation", wc_group, "custom_resource_type"
    ) or "Machine"

    # Skip External (Subcontracting) — handled by ERPNext Subcon module
    if resource_type == "External":
        mcp_logger.info(f"[MCP] Skipping External op '{operation}' — subcontracting")
        return None

    # 3. Score each candidate (machine or manpower, with MRP for machine ops)
    enable_mrp = settings.get("enable_mrp_check", True)
    warehouse  = settings.get("material_check_warehouse", "")

    scored = []
    for resource in candidates:
        if resource_type == "Manpower":
            cap = _get_manpower_capacity(resource["name"], start_dt, delivery_deadline)
            # Manpower ops skip MRP — materials handled before or after by stores
            cap["material_delay_hrs"] = 0.0
            cap["material_status"]    = "Ready"
        else:
            cap = get_machine_capacity(resource["name"], start_dt, delivery_deadline)
            # F5: MRP — material delay relative to THIS machine's free slot
            material_delay_hrs = 0.0
            material_status    = "Ready"
            if enable_mrp and work_order and warehouse:
                from machine_capacity_planner.utils.mrp_checker import get_material_readiness
                from frappe.utils import add_to_date
                machine_free_at    = add_to_date(start_dt, hours=cap["earliest_free"])
                mat                = get_material_readiness(work_order, machine_free_at, warehouse)
                material_delay_hrs = mat["material_delay_hrs"]
                material_status    = mat["status"]
            cap["material_delay_hrs"] = material_delay_hrs
            cap["material_status"]    = material_status

        score = _calculate_score(cap, settings)
        scored.append({**resource, **cap, "score": score, "resource_type": resource_type})
        mcp_logger.debug(
            f"[MCP] {resource['name']} ({resource_type}) → "
            f"util={cap['utilisation']:.1f}% "
            f"free={cap['free_hrs']:.1f}h "
            f"mat={cap.get('material_status','N/A')}(+{cap.get('material_delay_hrs',0):.1f}h) "
            f"score={score}"
        )

    # 4. Sort ascending — lowest score wins
    scored.sort(key=lambda x: x["score"])
    winner = scored[0]

    # 5. Reject if even the best machine is overloaded
    overload_pct = settings.get("overload_threshold_pct", 92)
    if winner["utilisation"] >= overload_pct:
        mcp_logger.error(
            f"[MCP] All machines in '{wc_group}' overloaded "
            f"(threshold={overload_pct}%). "
            f"Best: {winner['name']} at {winner['utilisation']:.1f}%"
        )
        _create_capacity_alert(wc_group, operation, scored, settings)
        return None

    # 6. Write audit log
    _log_selection(winner, scored, operation, delivery_deadline, required_hours)

    mcp_logger.info(
        f"[MCP] Selected {winner['name']} "
        f"(score={winner['score']}) "
        f"from group '{wc_group}'"
    )
    return winner


def get_machine_capacity(
    machine_name: str,
    start_dt,
    delivery_deadline,
) -> dict:
    """
    Calculate capacity metrics for a single machine within the time horizon
    [start_dt → delivery_deadline].

    Returns
    -------
    {
        gross_hrs       : float  — total available shift hours in horizon
        committed_hrs   : float  — hours already booked (open Job Cards)
        free_hrs        : float  — gross - committed
        utilisation     : float  — committed / gross * 100  (percentage)
        earliest_free   : float  — hours from now until first free block
        has_maint       : int    — 1 if maintenance scheduled in horizon
        horizon_hrs     : float  — planning window in hours
    }
    """
    horizon_hrs = max(time_diff_in_hours(delivery_deadline, start_dt), 0.5)

    gross_hrs     = _get_gross_available_hours(machine_name, start_dt, delivery_deadline)
    committed_hrs = _get_committed_hours(machine_name, start_dt, delivery_deadline)
    has_maint     = _has_maintenance_in_horizon(machine_name, start_dt, delivery_deadline)
    earliest_free = _get_earliest_free_slot(machine_name, start_dt)

    free_hrs    = max(gross_hrs - committed_hrs, 0.0)
    utilisation = (committed_hrs / gross_hrs * 100) if gross_hrs > 0 else 100.0

    return {
        "gross_hrs":     round(gross_hrs, 2),
        "committed_hrs": round(committed_hrs, 2),
        "free_hrs":      round(free_hrs, 2),
        "utilisation":   round(utilisation, 2),
        "earliest_free": round(earliest_free, 2),
        "has_maint":     has_maint,
        "horizon_hrs":   round(horizon_hrs, 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS — used only within this module
# ─────────────────────────────────────────────────────────────────────────────

def _get_settings() -> dict:
    """Load weights and thresholds from Machine Selection Settings (Single DocType)."""
    try:
        s = frappe.get_single("Machine Selection Settings")
        return {
            "w_load":                    s.weight_load or 25,
            "w_free":                    s.weight_free_slot or 25,
            "w_slack":                   s.weight_delivery_slack or 20,
            "w_maint":                   s.weight_maintenance_risk or 10,
            "w_material":                s.weight_material_readiness or 20,
            "overload_threshold_pct":    s.overload_threshold_pct or 92,
            "rebalance_threshold":       s.rebalance_threshold or 10,
            "manager_email":             s.manager_email or "",
            "supervisor_email":          s.supervisor_email or "",
            "plant_head_email":          s.plant_head_email or "",
            "enable_mrp_check":          bool(s.enable_mrp_check if s.enable_mrp_check is not None else 1),
            "material_check_warehouse":  s.material_check_warehouse or "",
            "escalation_warning_hrs":    float(s.escalation_warning_hrs or 0),
            "escalation_critical_hrs":   float(s.escalation_critical_hrs or 4),
            "escalation_stopped_hrs":    float(s.escalation_stopped_hrs or 8),
        }
    except Exception:
        return {
            "w_load": 25, "w_free": 25, "w_slack": 20, "w_maint": 10, "w_material": 20,
            "overload_threshold_pct": 92,
            "rebalance_threshold": 10,
            "manager_email": "", "supervisor_email": "", "plant_head_email": "",
            "enable_mrp_check": True, "material_check_warehouse": "",
            "escalation_warning_hrs": 0, "escalation_critical_hrs": 4, "escalation_stopped_hrs": 8,
        }


def _get_candidate_machines(wc_group: str) -> List[Dict]:
    """Return all enabled, non-group Workstations that are children of wc_group."""
    return frappe.get_list(
        "Workstation",
        filters={
            "parent_workstation": wc_group,
            "disabled":           0,
            "is_group":           0,
        },
        fields=["name", "capacity_planning_factor", "description"],
    )


def _get_gross_available_hours(machine: str, start_dt, end_dt) -> float:
    """
    Calculate total available shift hours for the machine in the date range.
    Uses the Workstation's total_working_hrs field and subtracts holiday days.
    """
    horizon_days = max(time_diff_in_hours(end_dt, start_dt) / 24, 1)

    wc = frappe.db.get_value(
        "Workstation", machine,
        ["total_working_hrs", "holiday_list"],
        as_dict=True,
    )
    daily_hrs = float(wc.get("total_working_hrs") or 8)

    holiday_days = _count_holidays(wc.get("holiday_list"), start_dt, end_dt)
    working_days = max(horizon_days - holiday_days, 0)

    return working_days * daily_hrs


def _get_committed_hours(machine: str, start_dt, end_dt) -> float:
    """
    Sum planned hours of all open/WIP Job Cards on this machine within the horizon.
    Uses TIMESTAMPDIFF for precision; returns 0.0 if no booked cards.
    """
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(
            TIMESTAMPDIFF(SECOND, planned_start_time, planned_end_time) / 3600
        ), 0) AS booked_hrs
        FROM `tabJob Card`
        WHERE workstation        = %(machine)s
          AND status             IN ('Open', 'Work In Progress')
          AND planned_start_time >= %(start)s
          AND planned_end_time   <= %(end)s
    """, {
        "machine": machine,
        "start":   start_dt,
        "end":     end_dt,
    }, as_dict=True)

    return float(result[0].get("booked_hrs") or 0)


def _get_earliest_free_slot(machine: str, from_dt) -> float:
    """
    Returns hours from from_dt until the machine is next available.
    Looks at the MAX planned_end_time of consecutive booked Job Cards.
    Returns 0.0 if machine is already free.
    """
    last_booked = frappe.db.sql("""
        SELECT MAX(planned_end_time) AS last_end
        FROM `tabJob Card`
        WHERE workstation        = %(machine)s
          AND status             IN ('Open', 'Work In Progress')
          AND planned_start_time >= %(from_dt)s
    """, {"machine": machine, "from_dt": from_dt}, as_dict=True)

    last_end = last_booked[0].get("last_end") if last_booked else None
    if not last_end:
        return 0.0  # machine is free right now

    return max(time_diff_in_hours(last_end, from_dt), 0.0)


def _has_maintenance_in_horizon(machine: str, start_dt, end_dt) -> int:
    """
    Returns 1 if a submitted Maintenance Schedule Detail exists for this
    machine (matched by asset_name) within the planning horizon.
    """
    count = frappe.db.sql("""
        SELECT COUNT(*) AS cnt
        FROM   `tabMaintenance Schedule Detail` msd
        JOIN   `tabMaintenance Schedule` ms ON ms.name = msd.parent
        WHERE  ms.asset_name      = %(machine)s
          AND  msd.scheduled_date BETWEEN %(start)s AND %(end)s
          AND  ms.docstatus       = 1
    """, {
        "machine": machine,
        "start":   start_dt,
        "end":     end_dt,
    }, as_dict=True)

    return 1 if (count and count[0].get("cnt", 0) > 0) else 0


def _count_holidays(holiday_list: str, start_dt, end_dt) -> int:
    """Count the number of holidays in the given date range for a Holiday List."""
    if not holiday_list:
        return 0
    count = frappe.db.sql("""
        SELECT COUNT(*) AS cnt
        FROM   `tabHoliday`
        WHERE  parent       = %(hl)s
          AND  holiday_date BETWEEN %(start)s AND %(end)s
    """, {
        "hl":    holiday_list,
        "start": getdate(start_dt),
        "end":   getdate(end_dt),
    }, as_dict=True)

    return int(count[0].get("cnt") or 0) if count else 0


def _calculate_score(cap: dict, settings: dict) -> float:
    """
    Compute the composite weighted score. LOWER = BETTER.

    F1  Utilisation penalty   — busy machine/station loses
    F2  Free-slot delay       — resource free later loses
    F3  Delivery slack        — less buffer before deadline loses
    F4  Maintenance risk      — maintenance window loses (machines only)
    F5  Material readiness    — machine must wait for materials loses (machines only)
    """
    horizon = cap["horizon_hrs"] or 1.0

    # F1: utilisation (0–100%) → normalised 0–1 × weight
    f1 = (cap["utilisation"] / 100.0) * settings["w_load"]

    # F2: hours until free → normalised 0–1 × weight
    f2 = min(cap["earliest_free"] / horizon, 1.0) * settings["w_free"]

    # F3: delivery slack penalty (less free hours relative to horizon = worse)
    f3 = max(1.0 - cap["free_hrs"] / horizon, 0.0) * settings["w_slack"]

    # F4: binary maintenance risk (0 for manpower resources)
    f4 = cap["has_maint"] * settings["w_maint"]

    # F5: material readiness — how long machine must wait for materials
    material_delay = cap.get("material_delay_hrs", 0.0)
    f5 = min(material_delay / horizon, 1.0) * settings.get("w_material", 0)

    return round(f1 + f2 + f3 + f4 + f5, 3)



def _log_selection(
    winner: dict,
    all_scored: list,
    operation: str,
    delivery_deadline,
    required_hours: float,
):
    """Write a Machine Selection Log entry for full auditability."""
    try:
        runner_up = all_scored[1] if len(all_scored) > 1 else {}

        log = frappe.new_doc("Machine Selection Log")
        log.update({
            "operation":         operation,
            "selected_machine":  winner["name"],
            "score":             winner["score"],
            "utilisation_pct":   winner.get("utilisation", 0),
            "free_hours":        winner.get("free_hrs", 0),
            "horizon_hours":     winner.get("horizon_hrs", 0),
            "delivery_deadline": delivery_deadline,
            "required_hours":    required_hours,
            "runner_up_machine": runner_up.get("name", ""),
            "runner_up_score":   runner_up.get("score", 0),
            "all_scores":        str([
                {"machine": s["name"], "score": s["score"]}
                for s in all_scored
            ]),
            "allocated_by": "AUTO",
        })
        log.insert(ignore_permissions=True)
        frappe.db.commit()

    except Exception as e:
        mcp_logger.error(f"[MCP] Failed to write selection log: {e}")


def _create_capacity_alert(
    wc_group: str,
    operation: str,
    all_scored: list,
    settings: dict,
):
    """Send email alert to production manager when all machines are overloaded."""
    manager_email = settings.get("manager_email")
    if not manager_email:
        return

    machine_summary = "\n".join(
        f"  - {s['name']}: {s['utilisation']:.1f}% utilised, score={s['score']}"
        for s in all_scored
    )

    frappe.sendmail(
        recipients=[manager_email],
        subject=f"CAPACITY ALERT: All machines overloaded — Group '{wc_group}'",
        message=f"""
<h3>Machine Capacity Alert</h3>
<p>All machines in group <strong>{wc_group}</strong> are at or above
the overload threshold for operation <strong>{operation}</strong>.</p>
<pre>{machine_summary}</pre>
<h4>Recommended Actions</h4>
<ol>
  <li>Approve overtime on the least-loaded machine</li>
  <li>Subcontract this operation</li>
  <li>Negotiate delivery date with the customer</li>
</ol>
        """,
        now=True,
    )
