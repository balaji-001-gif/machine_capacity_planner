"""
escalation.py
=============
Overdue Job Card detection and tiered alert system.

Runs every 15 minutes via Frappe scheduler.

Escalation levels:
  Warning  (delay >= warning_hrs,  default 0h)  → email Production Manager
  Critical (delay >= critical_hrs, default 4h)  → email + Supervisor
  Stopped  (delay >= stopped_hrs,  default 8h)  → email + Plant Head
"""

import frappe
from frappe.utils import now_datetime, time_diff_in_hours, getdate
from machine_capacity_planner.utils.machine_selector import _get_settings
from machine_capacity_planner.utils.logger import mcp_logger


def check_overdue_job_cards():
    """Entry point — called by Frappe scheduler every 15 minutes."""
    settings = _get_settings()

    warn_hrs     = float(settings.get("escalation_warning_hrs",  0))
    crit_hrs     = float(settings.get("escalation_critical_hrs", 4))
    stop_hrs     = float(settings.get("escalation_stopped_hrs",  8))
    manager      = settings.get("manager_email", "")
    supervisor   = settings.get("supervisor_email", "")
    plant_head   = settings.get("plant_head_email", "")

    now = now_datetime()

    overdue_jcs = frappe.get_list(
        "Job Card",
        filters={
            "status":           ["in", ["Open", "Work In Progress"]],
            "expected_end_date": ["<",   now],
        },
        fields=[
            "name", "work_order", "operation", "workstation",
            "expected_end_date", "custom_escalation_status",
        ],
    )

    if not overdue_jcs:
        mcp_logger.debug("[MCP ESC] No overdue Job Cards.")
        return

    for jc in overdue_jcs:
        delay_hrs = time_diff_in_hours(now, jc.expected_end_date)
        level     = _get_level(delay_hrs, warn_hrs, crit_hrs, stop_hrs)
        current   = jc.custom_escalation_status or ""

        # Don't downgrade — only escalate upward
        if current == "Stopped":
            continue
        if current == "Critical" and level == "Warning":
            continue
        if current == level:
            continue

        _write_escalation_log(jc, delay_hrs, level)
        frappe.db.set_value("Job Card", jc.name, "custom_escalation_status", level)
        _send_alert(jc, delay_hrs, level, manager, supervisor, plant_head)

        mcp_logger.info(
            f"[MCP ESC] {jc.name} | {jc.operation} @ {jc.workstation} "
            f"| delay={delay_hrs:.1f}h | {current or 'None'} → {level}"
        )

    frappe.db.commit()


def _get_level(delay_hrs, warn_hrs, crit_hrs, stop_hrs) -> str:
    if delay_hrs >= stop_hrs:
        return "Stopped"
    elif delay_hrs >= crit_hrs:
        return "Critical"
    else:
        return "Warning"


def _write_escalation_log(jc: dict, delay_hrs: float, level: str) -> None:
    try:
        log = frappe.new_doc("Escalation Log")
        log.update({
            "job_card":         jc.name,
            "work_order":       jc.work_order,
            "operation":        jc.operation,
            "workstation":      jc.workstation,
            "expected_end_date": jc.expected_end_date,
            "delay_hrs":        round(delay_hrs, 2),
            "escalation_level": level,
            "notified_at":      now_datetime(),
        })
        log.insert(ignore_permissions=True)
    except Exception as e:
        mcp_logger.error(f"[MCP ESC] Escalation Log write failed: {e}")


def _send_alert(jc, delay_hrs, level, manager, supervisor, plant_head):
    icons    = {"Warning": "🟡", "Critical": "🔴", "Stopped": "🛑"}
    icon     = icons.get(level, "⚠️")
    bg_color = {"Warning": "#FFF3CD", "Critical": "#F8D7DA", "Stopped": "#D1ECF1"}.get(level, "#fff")

    recipients = []
    if manager:
        recipients.append(manager)
    if level in ("Critical", "Stopped") and supervisor:
        recipients.append(supervisor)
    if level == "Stopped" and plant_head:
        recipients.append(plant_head)

    if not recipients:
        mcp_logger.warning(f"[MCP ESC] No recipients configured for escalation level {level}")
        return

    body = f"""
    <div style="font-family:Arial;max-width:600px">
      <h2 style="background:{bg_color};padding:12px;border-radius:4px">
        {icon} Job Card Overdue — {level}
      </h2>
      <table border="1" cellpadding="8" style="border-collapse:collapse;width:100%">
        <tr><th style="background:#f4f4f4;text-align:left">Job Card</th>
            <td><a href="/app/job-card/{jc.name}">{jc.name}</a></td></tr>
        <tr><th style="background:#f4f4f4;text-align:left">Work Order</th>
            <td><a href="/app/work-order/{jc.work_order}">{jc.work_order}</a></td></tr>
        <tr><th style="background:#f4f4f4;text-align:left">Operation</th>
            <td>{jc.operation}</td></tr>
        <tr><th style="background:#f4f4f4;text-align:left">Station / Machine</th>
            <td>{jc.workstation}</td></tr>
        <tr><th style="background:#f4f4f4;text-align:left">Was Due</th>
            <td>{jc.expected_end_date}</td></tr>
        <tr><th style="background:#f4f4f4;text-align:left">Overdue By</th>
            <td style="color:red;font-weight:bold">{delay_hrs:.1f} hours</td></tr>
      </table>
      <p style="margin-top:16px">
        Please take action immediately in ERPNext or create a Manual Override.
      </p>
    </div>
    """

    try:
        frappe.sendmail(
            recipients=recipients,
            subject=f"{icon} [{level}] Overdue: {jc.name} — {jc.operation} ({delay_hrs:.1f}h late)",
            message=body,
            now=True,
        )
    except Exception as e:
        mcp_logger.error(f"[MCP ESC] Email send failed: {e}")
