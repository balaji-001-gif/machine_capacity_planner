"""
setup_demo_data.py
==================
Creates demo Work Centre Groups and machines for testing.

Run inside bench:
    bench --site your-site.local execute \
        machine_capacity_planner.scripts.setup_demo_data.create_demo_data

Or from bench console:
    bench --site your-site.local console
    >>> from machine_capacity_planner.scripts.setup_demo_data import create_demo_data
    >>> create_demo_data()
"""
import frappe


def create_demo_data():
    """Create 3 machine groups, each with 3 machines."""
    groups = [
        (
            "CNC-GROUP",
            "CNC Turning Operations",
            ["MCH-CNC-01", "MCH-CNC-02", "MCH-CNC-03"],
        ),
        (
            "WELD-GROUP",
            "Welding Operations",
            ["MCH-WELD-01", "MCH-WELD-02", "MCH-WELD-03"],
        ),
        (
            "LASER-GROUP",
            "Laser Cutting Operations",
            ["MCH-LASER-01", "MCH-LASER-02", "MCH-LASER-03"],
        ),
    ]

    company = frappe.defaults.get_global_default("company")

    for group_name, description, machines in groups:
        _create_wc_group(group_name, description, company)
        for machine in machines:
            _create_machine(machine, group_name, company)

    _create_operations()
    _configure_settings()

    frappe.db.commit()
    print("✅ Demo data created successfully.")
    print("   Next: Create a Work Order for any of the demo operations and submit it.")


def _create_wc_group(name, description, company):
    if frappe.db.exists("Work Centre", name):
        print(f"  ⏭  Skipping existing group: {name}")
        return
    wc = frappe.new_doc("Work Centre")
    wc.work_centre_name = name
    wc.is_group         = 1
    wc.description      = description
    wc.company          = company
    wc.insert(ignore_permissions=True)
    print(f"  ✅ Created group: {name}")


def _create_machine(name, parent_group, company):
    if frappe.db.exists("Work Centre", name):
        print(f"  ⏭  Skipping existing machine: {name}")
        return
    wc = frappe.new_doc("Work Centre")
    wc.work_centre_name         = name
    wc.is_group                 = 0
    wc.parent_work_centre       = parent_group
    wc.company                  = company
    wc.capacity_planning_factor = 1
    wc.total_working_hrs        = 16    # 2 shifts
    wc.insert(ignore_permissions=True)
    print(f"  ✅ Created machine: {name} (parent: {parent_group})")


def _create_operations():
    """Create demo operations linked to each Work Centre Group."""
    ops = [
        ("CNC Turning",   "CNC-GROUP"),
        ("Welding",       "WELD-GROUP"),
        ("Laser Cutting", "LASER-GROUP"),
    ]
    for op_name, wc_group in ops:
        if not frappe.db.exists("Operation", op_name):
            op = frappe.new_doc("Operation")
            op.name        = op_name
            op.workstation = wc_group
            op.insert(ignore_permissions=True)
            print(f"  ✅ Created Operation: {op_name} → {wc_group}")
        else:
            frappe.db.set_value("Operation", op_name, "workstation", wc_group)
            print(f"  ✅ Linked Operation: {op_name} → {wc_group}")


def _configure_settings():
    """Set default scoring weights in Machine Selection Settings."""
    try:
        s = frappe.get_single("Machine Selection Settings")
        s.weight_load               = 30
        s.weight_free_slot          = 35
        s.weight_delivery_slack     = 25
        s.weight_maintenance_risk   = 10
        s.overload_threshold_pct    = 92
        s.rebalance_threshold       = 10
        s.rebalance_interval_mins   = 30
        s.save(ignore_permissions=True)
        print("  ✅ Machine Selection Settings configured (weights: 30/35/25/10)")
    except Exception as e:
        print(f"  ⚠️  Could not configure settings: {e}")
