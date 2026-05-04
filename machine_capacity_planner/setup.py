"""
setup.py
========
Runs after `bench install-app machine_capacity_planner`.
Creates all required Custom Fields programmatically.
"""
import frappe


def after_install():
    """Create all custom fields required by Machine Capacity Planner."""
    _create_custom_fields()
    frappe.db.commit()


def _create_custom_fields():
    custom_fields = [
        # ── Job Card fields ────────────────────────────────────────────
        {
            "name": "Job Card-custom_machine_score",
            "dt": "Job Card",
            "fieldname": "custom_machine_score",
            "fieldtype": "Float",
            "label": "Machine Score",
            "insert_after": "workstation",
            "read_only": 1,
            "description": "Composite score at time of assignment (lower = better)",
            "module": "Machine Capacity Planner",
        },
        {
            "name": "Job Card-custom_allocated_by",
            "dt": "Job Card",
            "fieldname": "custom_allocated_by",
            "fieldtype": "Data",
            "label": "Allocated By",
            "insert_after": "custom_machine_score",
            "read_only": 1,
            "description": "AUTO, AUTO-REBALANCE, or MANUAL:username",
            "module": "Machine Capacity Planner",
        },
        {
            "name": "Job Card-custom_material_status",
            "dt": "Job Card",
            "fieldname": "custom_material_status",
            "fieldtype": "Select",
            "label": "Material Status",
            "options": "Ready\nPartial\nBlocked",
            "insert_after": "custom_allocated_by",
            "read_only": 1,
            "description": "MRP material readiness at time of machine assignment",
            "module": "Machine Capacity Planner",
        },
        {
            "name": "Job Card-custom_material_delay_hrs",
            "dt": "Job Card",
            "fieldname": "custom_material_delay_hrs",
            "fieldtype": "Float",
            "label": "Material Delay (hrs)",
            "insert_after": "custom_material_status",
            "read_only": 1,
            "description": "Hours machine must wait for materials (0 = no delay)",
            "module": "Machine Capacity Planner",
        },
        {
            "name": "Job Card-custom_escalation_status",
            "dt": "Job Card",
            "fieldname": "custom_escalation_status",
            "fieldtype": "Select",
            "label": "Escalation Status",
            "options": "\nWarning\nCritical\nStopped",
            "insert_after": "custom_material_delay_hrs",
            "read_only": 1,
            "description": "Set automatically when Job Card is overdue",
            "module": "Machine Capacity Planner",
        },
        # ── Workstation fields ─────────────────────────────────────────
        {
            "name": "Workstation-is_group",
            "dt": "Workstation",
            "fieldname": "is_group",
            "fieldtype": "Check",
            "label": "Is Group",
            "default": "0",
            "insert_after": "workstation_name",
            "description": "Check if this is a parent group (e.g. CNC-GROUP). Groups cannot have jobs assigned directly.",
            "module": "Machine Capacity Planner",
        },
        {
            "name": "Workstation-parent_workstation",
            "dt": "Workstation",
            "fieldname": "parent_workstation",
            "fieldtype": "Link",
            "options": "Workstation",
            "label": "Parent Workstation",
            "insert_after": "is_group",
            "description": "Select the group this machine belongs to.",
            "module": "Machine Capacity Planner",
        },
        {
            "name": "Workstation-custom_resource_type",
            "dt": "Workstation",
            "fieldname": "custom_resource_type",
            "fieldtype": "Select",
            "label": "Resource Type",
            "options": "Machine\nManpower\nExternal",
            "default": "Machine",
            "insert_after": "description",
            "description": "Machine=CNC/CMM | Manpower=Stores/Quality | External=Subcon",
            "module": "Machine Capacity Planner",
        },
        {
            "name": "Workstation-custom_operators_count",
            "dt": "Workstation",
            "fieldname": "custom_operators_count",
            "fieldtype": "Int",
            "label": "Number of Operators",
            "default": "1",
            "insert_after": "custom_resource_type",
            "description": "Man-hour capacity = shift_hrs × operators_count (Manpower type only)",
            "module": "Machine Capacity Planner",
        },
        {
            "name": "Workstation-custom_machine_group_tag",
            "dt": "Workstation",
            "fieldname": "custom_machine_group_tag",
            "fieldtype": "Data",
            "label": "Machine Group Tag",
            "insert_after": "custom_operators_count",
            "description": "Tag for capability filtering (e.g. CNC-TURN, LASER-CUT)",
            "module": "Machine Capacity Planner",
        },
    ]

    for cf in custom_fields:
        if not frappe.db.exists("Custom Field", cf["name"]):
            doc = frappe.get_doc({"doctype": "Custom Field", **cf})
            doc.insert(ignore_permissions=True)
            print(f"  ✓ Created Custom Field: {cf['name']}")
        else:
            print(f"  - Custom Field already exists: {cf['name']}")
