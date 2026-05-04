"""MRP REST API endpoints."""
import frappe
from frappe.utils import now_datetime, add_days
from machine_capacity_planner.utils.mrp_checker import get_material_readiness
from machine_capacity_planner.utils.machine_selector import _get_settings


@frappe.whitelist()
def get_work_order_material_status(work_order: str) -> dict:
    """Return material readiness for a single Work Order (used by planning board)."""
    frappe.has_permission("Work Order", throw=True)
    settings  = _get_settings()
    warehouse = settings.get("material_check_warehouse", "")
    return get_material_readiness(work_order, now_datetime(), warehouse)


@frappe.whitelist()
def get_all_open_wo_material_status() -> list:
    """Return material status for ALL open Work Orders in one call."""
    frappe.has_permission("Work Order", throw=True)
    settings  = _get_settings()
    warehouse = settings.get("material_check_warehouse", "")

    open_wos = frappe.get_list(
        "Work Order",
        filters={"status": ["in", ["Not Started", "In Process"]]},
        fields=["name", "production_item", "expected_delivery_date"],
    )
    results = []
    for wo in open_wos:
        mat = get_material_readiness(wo.name, now_datetime(), warehouse)
        results.append({
            "work_order": wo.name,
            "item":       wo.production_item,
            "delivery":   wo.expected_delivery_date,
            **mat,
        })
    return results


@frappe.whitelist()
def run_mrp_for_all_open_work_orders() -> dict:
    """Batch MRP check — manual trigger from planning board."""
    frappe.has_permission("Machine Selection Settings", throw=True)
    from machine_capacity_planner.tasks.mrp_sync import sync_material_readiness
    sync_material_readiness()
    return {"status": "ok", "message": "MRP sync complete. Check MRP Run Log."}
