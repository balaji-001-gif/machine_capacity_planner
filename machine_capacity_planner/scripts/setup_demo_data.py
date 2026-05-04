"""
setup_demo_data.py
==================
Creates demo Workstations, Operations, Items, and Work Orders for testing.

Run inside bench:
    bench --site your-site.local execute machine_capacity_planner.scripts.setup_demo_data.create_demo_data
"""
import frappe
from frappe.utils import add_days, nowdate

def create_demo_data():
    """Main entry point to create all demo data."""
    company = frappe.defaults.get_global_default("company") or "Testing Company"
    
    # 1. Create Workstation Groups and Machines
    groups = [
        ("CNC-GROUP", "CNC Turning Operations", ["MCH-CNC-01", "MCH-CNC-02"], "CNC-TURN"),
        ("WELD-GROUP", "Welding Operations", ["MCH-WELD-01", "MCH-WELD-02"], "WELDING"),
    ]
    
    for group_name, description, machines, tag in groups:
        _create_workstation_group(group_name, description, company)
        for m_name in machines:
            _create_machine(m_name, group_name, company, tag)
            
    # 2. Create Operations
    _create_operations()
    
    # 3. Configure Settings
    _configure_settings()
    
    # 4. Create Demo Items & BOMs
    item_code = "DEMO-SHAFT-001"
    _create_item(item_code, "Demo Engine Shaft", company)
    _create_bom(item_code, company)
    
    # 5. Create a Work Order
    _create_work_order(item_code, company)

    frappe.db.commit()
    print("✅ Demo data created successfully.")

def _create_workstation_group(name, description, company):
    if not frappe.db.exists("Workstation", name):
        doc = frappe.get_doc({
            "doctype": "Workstation",
            "workstation_name": name,
            "is_group": 1,
            "description": description,
            "company": company
        })
        doc.insert(ignore_permissions=True)
        print(f"  ✅ Created Workstation Group: {name}")

def _create_machine(name, parent, company, tag):
    if not frappe.db.exists("Workstation", name):
        doc = frappe.get_doc({
            "doctype": "Workstation",
            "workstation_name": name,
            "parent_workstation": parent,
            "is_group": 0,
            "company": company,
            "custom_resource_type": "Machine",
            "custom_machine_group_tag": tag,
            "custom_operators_count": 1,
            "hour_rate": 500
        })
        doc.insert(ignore_permissions=True)
        print(f"  ✅ Created Machine: {name}")

def _create_operations():
    ops = [
        ("CNC Turning", "CNC-GROUP"),
        ("Welding", "WELD-GROUP")
    ]
    for op_name, ws in ops:
        if not frappe.db.exists("Operation", op_name):
            doc = frappe.get_doc({
                "doctype": "Operation",
                "name": op_name,
                "workstation": ws
            })
            doc.insert(ignore_permissions=True)
            print(f"  ✅ Created Operation: {op_name}")

def _configure_settings():
    try:
        s = frappe.get_single("Machine Selection Settings")
        s.weight_load = 40
        s.weight_free_slot = 40
        s.weight_delivery_slack = 20
        s.save(ignore_permissions=True)
        print("  ✅ Settings configured.")
    except Exception:
        pass

def _create_item(item_code, item_name, company):
    if not frappe.db.exists("Item", item_code):
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_name,
            "item_group": "Products",
            "is_stock_item": 1,
            "stock_uom": "Nos",
            "opening_stock": 0
        })
        item.insert(ignore_permissions=True)
        print(f"  ✅ Created Item: {item_code}")

def _create_bom(item_code, company):
    bom_name = f"BOM-{item_code}-001"
    if not frappe.db.exists("BOM", {"item": item_code}):
        bom = frappe.get_doc({
            "doctype": "BOM",
            "item": item_code,
            "quantity": 1,
            "company": company,
            "is_active": 1,
            "is_default": 1,
            "operations": [
                {"operation": "CNC Turning", "workstation": "CNC-GROUP", "time_in_mins": 30},
                {"operation": "Welding", "workstation": "WELD-GROUP", "time_in_mins": 15}
            ]
        })
        bom.insert(ignore_permissions=True)
        bom.submit()
        print(f"  ✅ Created BOM for {item_code}")

def _create_work_order(item_code, company):
    wo = frappe.get_doc({
        "doctype": "Work Order",
        "item_code": item_code,
        "qty": 10,
        "company": company,
        "wip_warehouse": "Work In Progress - PA",
        "fg_warehouse": "Finished Goods - PA",
        "planned_start_date": nowdate()
    })
    # Set default warehouses if they don't exist
    if not frappe.db.exists("Warehouse", wo.wip_warehouse):
        wo.wip_warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")
    if not frappe.db.exists("Warehouse", wo.fg_warehouse):
        wo.fg_warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")
        
    wo.insert(ignore_permissions=True)
    # wo.submit() # Submission triggers the machine selection logic if hooks are active
    print(f"  ✅ Created Work Order: {wo.name}")
