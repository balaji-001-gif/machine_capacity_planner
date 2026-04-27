"""
mrp_sync.py — Daily MRP sync scheduled task.

Runs at 5:00 AM every working day (set in hooks.py).
Re-checks all open Work Orders for material readiness.
If a previously-blocked WO becomes Ready → triggers rebalancing.
Sends a morning email listing WOs still blocked on materials.
"""
import frappe
from frappe.utils import now_datetime, getdate
from machine_capacity_planner.utils.mrp_checker import get_material_readiness, write_mrp_run_log
from machine_capacity_planner.utils.machine_selector import _get_settings
from machine_capacity_planner.utils.logger import mcp_logger


def sync_material_readiness():
    """Entry point — called by Frappe scheduler at 5:00 AM Mon–Sat."""
    settings  = _get_settings()
    warehouse = settings.get("material_check_warehouse", "")
    manager   = settings.get("manager_email", "")

    if not settings.get("enable_mrp_check", True):
        mcp_logger.debug("[MCP MRP Sync] MRP check disabled in settings — skipping.")
        return

    if not warehouse:
        mcp_logger.warning("[MCP MRP Sync] No material_check_warehouse set — skipping.")
        return

    open_wos = frappe.get_list(
        "Work Order",
        filters={"status": ["in", ["Not Started", "In Process"]]},
        fields=["name", "production_item", "expected_delivery_date"],
    )

    blocked_wos  = []
    partial_wos  = []
    now_ready    = []

    for wo in open_wos:
        try:
            mat = get_material_readiness(wo.name, now_datetime(), warehouse)

            # Check previous status from last MRP Run Log
            prev_status = frappe.db.get_value(
                "MRP Run Log",
                {"work_order": wo.name},
                "status",
                order_by="run_date desc",
            )

            # Get the assigned machine from the first open Job Card
            machine = frappe.db.get_value(
                "Job Card",
                {"work_order": wo.name, "status": "Open"},
                "workstation",
            ) or ""

            write_mrp_run_log(wo.name, machine, mat)

            # Update material_status on all open Job Cards for this WO
            frappe.db.sql("""
                UPDATE `tabJob Card`
                SET    custom_material_status   = %(status)s,
                       custom_material_delay_hrs = %(delay)s
                WHERE  work_order = %(wo)s
                  AND  status IN ('Open', 'Work In Progress')
            """, {
                "status": mat["status"],
                "delay":  mat["material_delay_hrs"],
                "wo":     wo.name,
            })

            # Detect WOs that were blocked and are now ready → trigger rebalance
            if prev_status in ("Blocked", "Partial") and mat["status"] == "Ready":
                now_ready.append(wo.name)
                mcp_logger.info(f"[MCP MRP Sync] WO {wo.name} is now material-ready — queuing rebalance")

            if mat["status"] == "Blocked":
                blocked_wos.append({"wo": wo.name, "item": wo.production_item})
            elif mat["status"] == "Partial":
                partial_wos.append({"wo": wo.name, "item": wo.production_item, "delay": mat["material_delay_hrs"]})

        except Exception as e:
            mcp_logger.error(f"[MCP MRP Sync] Error on WO {wo.name}: {e}")

    frappe.db.commit()

    # Trigger rebalancer for WOs that just became ready
    if now_ready:
        from machine_capacity_planner.tasks.rebalancer import auto_rebalance_machines
        auto_rebalance_machines()

    # Send morning email summary
    if manager:
        _send_mrp_summary_email(manager, blocked_wos, partial_wos, now_ready)

    mcp_logger.info(
        f"[MCP MRP Sync] Complete. "
        f"Blocked={len(blocked_wos)}, Partial={len(partial_wos)}, NowReady={len(now_ready)}"
    )


def _send_mrp_summary_email(manager, blocked_wos, partial_wos, now_ready):
    if not blocked_wos and not partial_wos and not now_ready:
        return  # All clear — no email needed

    blocked_html = "".join(
        f"<tr><td>{r['wo']}</td><td>{r['item']}</td><td>🔴 BLOCKED — No PO</td></tr>"
        for r in blocked_wos
    )
    partial_html = "".join(
        f"<tr><td>{r['wo']}</td><td>{r['item']}</td><td>🟡 +{r['delay']:.1f}h delay</td></tr>"
        for r in partial_wos
    )
    ready_html = "".join(
        f"<tr><td>{wo}</td><td colspan='2'>🟢 Now Ready — rebalance triggered</td></tr>"
        for wo in now_ready
    )

    table = (
        "<table border='1' cellpadding='6' style='border-collapse:collapse;font-family:Arial'>"
        "<tr style='background:#0B2545;color:#fff'><th>Work Order</th><th>Item</th><th>Status</th></tr>"
        + blocked_html + partial_html + ready_html
        + "</table>"
    )

    frappe.sendmail(
        recipients=[manager],
        subject=f"MRP Morning Alert — {getdate()} | {len(blocked_wos)} Blocked, {len(partial_wos)} Partial",
        message=f"<h3>MRP Material Status — {getdate()}</h3>{table}",
        now=True,
    )
