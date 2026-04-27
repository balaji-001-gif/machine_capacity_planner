"""
sales_order.py
==============
Logs the Sales Order delivery date when submitted.
The delivery date becomes the scheduling horizon for all downstream WOs.
"""
import frappe
from machine_capacity_planner.utils.logger import mcp_logger


def on_submit(doc, method=None):
    mcp_logger.info(
        f"[MCP] Sales Order {doc.name} submitted. "
        f"Delivery date: {doc.delivery_date}. "
        f"This drives the machine scheduling horizon."
    )
