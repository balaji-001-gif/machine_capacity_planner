"""Centralised logger for Machine Capacity Planner."""
import frappe

mcp_logger = frappe.logger(
    "machine_capacity_planner",
    allow_site=True,
    file_count=5,
)
