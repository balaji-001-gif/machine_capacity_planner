app_name        = "machine_capacity_planner"
app_title       = "Machine Capacity Planner"
app_publisher   = "YOUR_ORG"
app_description = "Intelligent machine capacity selection engine for ERPNext v15+"
app_email       = "dev@yourorg.com"
app_license     = "MIT"
app_version     = "3.0.0"

# ── Required apps ─────────────────────────────────────────────────────────────
required_apps = ["erpnext"]

# ── Doc Events ────────────────────────────────────────────────────────────────
# Format: "DocType": { "event": "module.path.function" }
doc_events = {
    "Work Order": {
        "on_submit": "machine_capacity_planner.events.work_order.on_submit",
        "on_cancel": "machine_capacity_planner.events.work_order.on_cancel",
    },
    "Job Card": {
        "on_submit": "machine_capacity_planner.events.job_card.on_submit",
    },
    "Work Center": {
        "after_save": "machine_capacity_planner.events.work_centre.after_save",
        "on_update":  "machine_capacity_planner.events.work_centre.on_update",
    },
    "Sales Order": {
        "on_submit": "machine_capacity_planner.events.sales_order.on_submit",
    },
}

# ── Scheduled Tasks ───────────────────────────────────────────────────────────
scheduler_events = {
    "cron": {
        # MRP material readiness sync — 5:00 AM every working day
        "0 5 * * 1-6": [
            "machine_capacity_planner.tasks.mrp_sync.sync_material_readiness"
        ],
        # Overdue Job Card escalation — every 15 minutes
        "*/15 * * * *": [
            "machine_capacity_planner.tasks.escalation.check_overdue_job_cards"
        ],
        # Machine rebalancer — every 30 minutes
        "*/30 * * * *": [
            "machine_capacity_planner.tasks.rebalancer.auto_rebalance_machines"
        ],
        # Weekly utilisation report every Monday 7:00 AM
        "0 7 * * 1": [
            "machine_capacity_planner.tasks.notifications.send_weekly_utilisation_report"
        ],
    },
}

# ── Fixtures ──────────────────────────────────────────────────────────────────
# Fixtures are exported/imported with: bench export-fixtures / bench migrate
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [["module", "=", "Machine Capacity Planner"]],
    },
    {
        "doctype": "Machine Selection Settings",
    },
]

# ── Permissions ───────────────────────────────────────────────────────────────
has_permission = {
    "Machine Selection Log": "machine_capacity_planner.permissions.has_permission",
}

