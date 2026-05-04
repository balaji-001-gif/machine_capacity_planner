import frappe

def create_all():
    print("Creating demo data for Machine Capacity Planner...")

    # 1. Configure Machine Selection Settings
    try:
        # For Single DocTypes, we must use frappe.db.set_value directly
        # to bypass module-lookup issues during first-time initialization.
        fields = {
            "weight_load": 25,
            "weight_earliest_slot": 25,
            "weight_delivery_slack": 20,
            "weight_maintenance_risk": 10,
            "weight_material_readiness": 20,
            "enable_mrp_material_check": 1,
            "warning_threshold_hrs": 0,
            "critical_threshold_hrs": 4,
            "stopped_threshold_hrs": 8,
        }

        # Ensure the single record row exists in the DB first
        if not frappe.db.exists("Machine Selection Settings", "Machine Selection Settings"):
            frappe.db.sql("""
                INSERT IGNORE INTO `tabMachine Selection Settings`
                (name, creation, modified, docstatus, modified_by, owner)
                VALUES ('Machine Selection Settings', NOW(), NOW(), 0, 'Administrator', 'Administrator')
            """)
            frappe.db.commit()

        for field, val in fields.items():
            frappe.db.set_value("Machine Selection Settings", "Machine Selection Settings", field, val)
        frappe.db.commit()
        print("✓ Configured Machine Selection Settings.")
    except Exception as e:
        print(f"⚠️ Failed to update settings: {e}")

    # 2. Create Workstation Groups & Resources
    workstations = [
        # CNC Group
        {"name": "DEMO-CNC-GROUP", "is_group": 1, "custom_resource_type": "Machine"},
        {"name": "DEMO-CNC-01", "is_group": 0, "parent_workstation": "DEMO-CNC-GROUP", "custom_resource_type": "Machine"},
        {"name": "DEMO-CNC-02", "is_group": 0, "parent_workstation": "DEMO-CNC-GROUP", "custom_resource_type": "Machine"},
        
        # Manpower Group
        {"name": "DEMO-ASSY-GROUP", "is_group": 1, "custom_resource_type": "Manpower"},
        {"name": "DEMO-ASSY-01", "is_group": 0, "parent_workstation": "DEMO-ASSY-GROUP", "custom_resource_type": "Manpower", "custom_operators_count": 4},
        {"name": "DEMO-ASSY-02", "is_group": 0, "parent_workstation": "DEMO-ASSY-GROUP", "custom_resource_type": "Manpower", "custom_operators_count": 2},
    ]

    for ws in workstations:
        if not frappe.db.exists("Workstation", ws["name"]):
            doc = frappe.get_doc({
                "doctype": "Workstation",
                "workstation_name": ws["name"],
                "is_group": ws.get("is_group", 0),
                "parent_workstation": ws.get("parent_workstation"),
                "custom_resource_type": ws.get("custom_resource_type"),
                "custom_operators_count": ws.get("custom_operators_count", 1),
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            print(f"✓ Created Workstation: {ws['name']}")
        else:
            print(f"- Workstation {ws['name']} already exists.")

    print("Done! Demo data created successfully.")
