"""
notifications.py
================
Daily and weekly email notification tasks.

Schedule (set in hooks.py):
  - Daily capacity summary at 6:00 AM Mon–Sat
  - Weekly utilisation report every Monday 7:00 AM
"""

import frappe
from frappe.utils import now_datetime, add_days, getdate
from machine_capacity_planner.utils.machine_selector import (
    get_machine_capacity,
    _get_candidate_machines,
    _get_settings,
)
from machine_capacity_planner.utils.logger import mcp_logger


def send_daily_capacity_summary():
    """
    Sends a daily email at 6 AM showing current utilisation for all machines.
    Called by scheduler cron: "0 6 * * 1-6"
    """
    settings = _get_settings()
    manager  = settings.get("manager_email")
    if not manager:
        mcp_logger.warning("[MCP] No manager_email set — skipping daily summary.")
        return

    groups = frappe.get_list(
        "Workstation",
        filters={"is_group": 1, "disabled": 0},
        fields=["name"],
    )

    rows = []
    for grp in groups:
        machines = _get_candidate_machines(grp.name)
        for m in machines:
            cap    = get_machine_capacity(m.name, now_datetime(), add_days(now_datetime(), 1))
            status = (
                "🔴 OVERLOADED" if cap["utilisation"] >= 92
                else "🟡 HIGH"   if cap["utilisation"] >= 75
                else "🟢 OK"
            )
            rows.append(
                f"<tr>"
                f"<td>{grp.name}</td>"
                f"<td>{m.name}</td>"
                f"<td>{cap['utilisation']:.1f}%</td>"
                f"<td>{cap['free_hrs']:.1f} hrs</td>"
                f"<td>{status}</td>"
                f"</tr>"
            )

    table = (
        "<table border='1' cellpadding='6' style='border-collapse:collapse;font-family:Arial'>"
        "<tr style='background:#0B2545;color:#fff'>"
        "<th>Group</th><th>Machine</th><th>Utilisation</th>"
        "<th>Free Hours</th><th>Status</th></tr>"
        + "".join(rows)
        + "</table>"
    )

    frappe.sendmail(
        recipients=[manager],
        subject=f"Daily Capacity Summary — {getdate()}",
        message=f"<h3>Machine Capacity Status for {getdate()}</h3>{table}",
        now=True,
    )
    mcp_logger.info("[MCP] Daily capacity summary sent.")


def send_weekly_utilisation_report():
    """
    Sends weekly utilisation report every Monday at 7 AM.
    Called by scheduler cron: "0 7 * * 1"
    """
    mcp_logger.info("[MCP] Weekly utilisation report triggered.")
    send_daily_capacity_summary()   # reuse daily for now; extend as needed
