# Machine Capacity Planner — ERPNext Custom App

[![ERPNext](https://img.shields.io/badge/ERPNext-v15%2B-blue)](https://erpnext.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![CI](https://github.com/YOUR_ORG/machine_capacity_planner/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_ORG/machine_capacity_planner/actions)

> Intelligent machine selection engine for ERPNext v15+.
> Automatically assigns the best machine from a group of identical machines
> based on delivery date, real-time load, and multi-factor capacity scoring.

## Features

| Feature | Description |
|---------|-------------|
| Auto Machine Selection | Scores all machines; assigns the lowest scorer |
| Delivery-Date Driven | Backward-schedules from SO delivery date |
| Dynamic Re-balancing | Re-evaluates every 30 min; reassigns if better slot found |
| Capacity Alerts | Email alerts when overloaded or delivery at risk |
| Full Audit Trail | Logs every selection decision with scoring breakdown |
| Tunable Weights | 4-factor scoring weights configurable per environment |
| Live Dashboard | Real-time utilisation per machine group |

## Scoring Formula

```
Score = (util%/100 × W_load)
      + (free_slot_hrs/horizon × W_free_slot)
      + max(1 - slack/horizon, 0) × W_slack
      + has_maintenance × W_maint

Lower score = better machine
```

Default weights: W_load=30, W_free_slot=35, W_slack=25, W_maint=10 (sum=100)

## Quick Install

```bash
cd ~/frappe-bench
bench get-app https://github.com/YOUR_ORG/machine_capacity_planner
bench --site your-site.local install-app machine_capacity_planner
bench --site your-site.local migrate
bench build --app machine_capacity_planner
bench restart
```

## Architecture

```
Work Order submitted
        │
        ▼
events/work_order.py  ←─── hooks.py wires this
        │
        ▼
utils/machine_selector.py   (scoring engine)
   ├── get_candidate_machines()
   ├── get_machine_capacity()   ← utilisation, free hrs, maintenance
   ├── _calculate_score()       ← F1+F2+F3+F4
   ├── _log_selection()         ← writes Machine Selection Log
   └── _create_capacity_alert() ← emails manager if all overloaded
        │
        ▼
Job Card.workstation = winner["name"]
```

## Configuration

After install, go to **Machine Capacity Planner → Settings** and configure:

| Setting | Default | Description |
|---------|---------|-------------|
| Weight: Utilisation Load % | 30 | Penalises busy machines |
| Weight: Earliest Free Slot | 35 | Prioritises sooner-available machines |
| Weight: Delivery Slack | 25 | Penalises tight deadlines |
| Weight: Maintenance Risk | 10 | Avoids machines with upcoming maintenance |
| Overload Threshold % | 92 | Above this → capacity alert |
| Rebalance Min Improvement | 10 | Minimum score improvement to trigger reassign |
| Production Manager Email | — | Alert recipient |

## Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [Contributing](docs/CONTRIBUTING.md)

## License

MIT © YOUR_ORG
