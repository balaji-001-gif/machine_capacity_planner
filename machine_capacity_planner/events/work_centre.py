"""
work_centre.py
==============
Invalidates the capacity cache whenever a Workstation is updated.
This ensures the next scoring run reads fresh data.
"""
import frappe
from machine_capacity_planner.utils.logger import mcp_logger


def after_save(doc, method=None):
    _invalidate_cache(doc.name)


def on_update(doc, method=None):
    _invalidate_cache(doc.name)


def _invalidate_cache(machine_name: str):
    frappe.cache().delete_key(f"mcp_capacity_{machine_name}")
    mcp_logger.debug(f"[MCP] Capacity cache cleared for {machine_name}")
