"""
mrp_checker.py — Material Requirements Planning checker.

Reads Production Plan Item (Q4: YES) → checks Bin stock → checks open POs
for expected arrival → returns material delay vs. machine free slot.

Usage (internal):
    from machine_capacity_planner.utils.mrp_checker import get_material_readiness
    mat = get_material_readiness("WO-2025-00042", machine_free_at, "Stores - ABC")
"""

import frappe
from frappe.utils import now_datetime, time_diff_in_hours
from machine_capacity_planner.utils.logger import mcp_logger


def get_material_readiness(work_order: str, machine_free_at, warehouse: str) -> dict:
    """
    Returns
    -------
    {
        status             : "Ready" / "Partial" / "Blocked"
        all_available      : bool
        shortfall_items    : list[dict]
        expected_arrival   : datetime or None
        material_delay_hrs : float  (0 = no delay, >0 = machine must wait)
        readiness_pct      : float
        total_items        : int
        available_items    : int
    }
    """
    if not work_order or not warehouse:
        return _ready_result()

    # Override check — manager confirmed materials manually
    if _has_override(work_order):
        return _ready_result()

    required_items = _get_required_items(work_order)
    if not required_items:
        return _ready_result()

    total_items     = len(required_items)
    shortfall_list  = []
    available_count = 0

    for item in required_items:
        available_qty = _get_bin_qty(item["item_code"], warehouse)
        shortfall     = max(item["required_qty"] - available_qty, 0)
        if shortfall <= 0:
            available_count += 1
        else:
            shortfall_list.append({
                "item_code":    item["item_code"],
                "required_qty": item["required_qty"],
                "available_qty": round(available_qty, 3),
                "shortfall":    round(shortfall, 3),
            })

    if not shortfall_list:
        return {
            "status": "Ready", "all_available": True,
            "shortfall_items": [], "expected_arrival": None,
            "material_delay_hrs": 0.0,
            "readiness_pct": 100.0,
            "total_items": total_items, "available_items": total_items,
        }

    # Check POs for shortfall items
    latest_arrival   = None
    blocked_count    = 0

    for sf in shortfall_list:
        arrival = _get_po_expected_arrival(sf["item_code"])
        sf["expected_po_arrival"] = arrival
        if arrival is None:
            blocked_count += 1
        elif latest_arrival is None or arrival > latest_arrival:
            latest_arrival = arrival

    if blocked_count > 0 and available_count == 0:
        status = "Blocked"
    else:
        status = "Partial"

    material_delay_hrs = 0.0
    if latest_arrival:
        delay = time_diff_in_hours(latest_arrival, machine_free_at)
        material_delay_hrs = max(delay, 0.0)

    readiness_pct = round(available_count / total_items * 100, 1) if total_items else 100.0

    mcp_logger.debug(
        f"[MCP MRP] WO {work_order} | status={status} "
        f"| delay={material_delay_hrs:.1f}h | shortfall={len(shortfall_list)} items"
    )
    return {
        "status":             status,
        "all_available":      False,
        "shortfall_items":    shortfall_list,
        "expected_arrival":   latest_arrival,
        "material_delay_hrs": round(material_delay_hrs, 2),
        "readiness_pct":      readiness_pct,
        "total_items":        total_items,
        "available_items":    available_count,
    }


def _get_required_items(work_order: str) -> list:
    """Read from Production Plan (preferred) or BOM (fallback)."""
    pp_name = frappe.db.get_value("Work Order", work_order, "production_plan")
    if pp_name:
        items = frappe.get_list(
            "Production Plan Item",
            filters={"parent": pp_name},
            fields=["item_code", "qty as required_qty", "stock_uom"],
        )
        if items:
            return items

    bom_no = frappe.db.get_value("Work Order", work_order, "bom_no")
    qty    = frappe.db.get_value("Work Order", work_order, "qty") or 1
    if not bom_no:
        return []

    bom_items = frappe.get_list(
        "BOM Item",
        filters={"parent": bom_no},
        fields=["item_code", "qty", "stock_uom"],
    )
    return [
        {"item_code": i["item_code"], "required_qty": float(i["qty"] or 0) * float(qty)}
        for i in bom_items
    ]


def _get_bin_qty(item_code: str, warehouse: str) -> float:
    qty = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty")
    return float(qty or 0)


def _get_po_expected_arrival(item_code: str):
    result = frappe.db.sql("""
        SELECT MIN(poi.schedule_date) AS expected_date
        FROM   `tabPurchase Order Item` poi
        JOIN   `tabPurchase Order` po ON po.name = poi.parent
        WHERE  poi.item_code    = %(item)s
          AND  po.docstatus     = 1
          AND  po.status        NOT IN ('Closed', 'Cancelled')
          AND  poi.received_qty < poi.qty
    """, {"item": item_code}, as_dict=True)
    if result and result[0].get("expected_date"):
        return result[0]["expected_date"]
    return None


def _has_override(work_order: str) -> bool:
    return bool(frappe.db.exists("Material Readiness Override", {"work_order": work_order}))


def _ready_result() -> dict:
    return {
        "status": "Ready", "all_available": True,
        "shortfall_items": [], "expected_arrival": None,
        "material_delay_hrs": 0.0, "readiness_pct": 100.0,
        "total_items": 0, "available_items": 0,
    }


def write_mrp_run_log(work_order: str, machine_assigned: str, mat_result: dict) -> None:
    """Persist MRP Run Log for auditability."""
    try:
        log = frappe.new_doc("MRP Run Log")
        log.update({
            "work_order":         work_order,
            "run_date":           now_datetime(),
            "total_items":        mat_result.get("total_items", 0),
            "available_items":    mat_result.get("available_items", 0),
            "shortfall_items":    len(mat_result.get("shortfall_items", [])),
            "expected_readiness": mat_result.get("expected_arrival"),
            "machine_assigned":   machine_assigned,
            "material_delay_hrs": mat_result.get("material_delay_hrs", 0),
            "status":             mat_result.get("status", "Ready"),
        })
        log.insert(ignore_permissions=True)
    except Exception as e:
        mcp_logger.error(f"[MCP MRP] Failed to write MRP Run Log: {e}")
