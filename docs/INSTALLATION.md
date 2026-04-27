# Installation Guide — Machine Capacity Planner

## Prerequisites

| Requirement | Minimum Version |
|-------------|----------------|
| ERPNext | v15.0.0 |
| Frappe Framework | v15.0.0 |
| Python | 3.10 |
| Node.js | 18 |
| bench CLI | 5.0 |

## Step 1 — Get the app

```bash
cd ~/frappe-bench
bench get-app https://github.com/YOUR_ORG/machine_capacity_planner
```

Or for development (editable install):
```bash
bench get-app machine_capacity_planner /path/to/local/clone
```

## Step 2 — Install on your site

```bash
bench --site your-site.local install-app machine_capacity_planner
```

## Step 3 — Run migrations (creates DocTypes + Custom Fields)

```bash
bench --site your-site.local migrate
```

## Step 4 — Build frontend assets

```bash
bench build --app machine_capacity_planner
```

## Step 5 — Restart bench

```bash
bench restart
```

## Step 6 — Post-install configuration

1. Go to **Machine Capacity Planner → Settings**
2. Set **Production Manager Email** — alerts will be sent here
3. Verify scoring weights sum to 100
4. Optionally adjust **Overload Threshold %** and **Rebalance Min Score Improvement**

## Step 7 — Verify Work Centre hierarchy

Ensure your machines are set up as:
```
CNC-GROUP (is_group=1)          ← Work Centre Group
├── MCH-01 (is_group=0)         ← Individual machine
├── MCH-02 (is_group=0)
└── MCH-03 (is_group=0)
```

And that your ERPNext **Operations** link to the group Work Centre (not individual machines).

## Step 8 — Load demo data (optional)

```bash
bench --site your-site.local execute \
    machine_capacity_planner.scripts.setup_demo_data.run
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| "No workstation linked to operation" | Operation not linked to WC Group | Edit Operation → set Workstation |
| "No active machines found in group" | Child WCs disabled or not created | Check Work Centre hierarchy |
| Machine score shows 0 always | Settings DocType not created | Run `bench migrate` |
| Planning board blank | API endpoint returning empty | Check no WC Groups exist |
| Email alerts not sending | No manager_email configured | Set email in Settings |

## Uninstall

```bash
bench --site your-site.local uninstall-app machine_capacity_planner
bench --site your-site.local migrate
```
