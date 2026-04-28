import frappe

def create_all():
    print("Creating demo data for Machine Capacity Planner...")

    # 1. Configure Machine Selection Settings
    try:
        settings = frappe.get_doc("Machine Selection Settings")
        settings.utilisation_weight = 25
        settings.earliest_free_slot_weight = 25
        settings.delivery_slack_weight = 20
        settings.maintenance_risk_weight = 10
        settings.material_readiness_weight = 20
        settings.enable_mrp_material_check = 1
        settings.warning_threshold_hrs = 0
        settings.critical_threshold_hrs = 4
        settings.stopped_threshold_hrs = 8
        settings.save()
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
