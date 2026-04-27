# Standard Operating Procedure (SOP)
# Machine Capacity Planner — ERPNext Custom App
**Version:** 2.0.0 | **Effective Date:** 2026-04-27 | **Owner:** Production Manager

---

## 1. Purpose
This SOP defines the end-to-end procedures for installing, configuring, operating, and maintaining the Machine Capacity Planner (MCP) app on ERPNext v15+. It ensures machines are automatically assigned to Job Cards using a 5-factor scoring engine and that material availability is validated before assignment.

---

## 2. Scope
| Role | Responsibility |
|---|---|
| IT Administrator | Installation, migration, bench restart |
| Production Manager | Configuration, daily board review, overrides |
| Manufacturing User | Submit Work Orders, view Job Cards |
| System Manager | Settings, user access, troubleshooting |

---

## 3. Prerequisites Checklist (Before Installation)

- [ ] ERPNext v15.0+ running on frappe-bench
- [ ] Python 3.10+ on server
- [ ] At least one Company configured in ERPNext
- [ ] Manufacturing module enabled
- [ ] Work Centre hierarchy planned (Groups + individual machines)
- [ ] BOMs with Operations created for manufactured items
- [ ] GitHub access to: `https://github.com/balaji-001-gif/machine_capacity_planner`

---

## 4. PHASE 1 — Installation (IT Administrator)

### 4.1 Install the App

```bash
# SSH into your server
cd ~/frappe-bench

# Download app (v1.0.0 stable) or MRP branch (v2.0.0)
bench get-app https://github.com/balaji-001-gif/machine_capacity_planner

# Install on your site
bench --site YOUR-SITE.local install-app machine_capacity_planner

# Create database tables for all 5 DocTypes + custom fields
bench --site YOUR-SITE.local migrate

# Build JS/CSS assets for Planning Board
bench build --app machine_capacity_planner

# Restart all services
bench restart
```

### 4.2 Verify Installation

```bash
# Check app is listed
bench --site YOUR-SITE.local list-apps
# Expected: machine_capacity_planner appears

# Validate scheduler is running
bench --site YOUR-SITE.local doctor
# Expected: scheduler: online
```

Log into ERPNext → search `Machine Capacity Planner` → Workspace should appear.

---

## 5. PHASE 2 — Master Data Setup (Production Manager)

**Perform in this exact order. Skipping steps causes failures.**

### Step 1 — Create Work Centre Groups

`Manufacturing → Work Centres → New`

| Field | Value |
|---|---|
| Work Centre Name | `CNC-GROUP` |
| Is Group | ✅ YES |
| Company | Your company |

Repeat for each machine type: `WELD-GROUP`, `LASER-GROUP`, etc.

> ⚠️ **CRITICAL:** `Is Group = YES`. Do not set hours here.

---

### Step 2 — Create Individual Machines

`Manufacturing → Work Centres → New` (one per physical machine)

| Field | Value |
|---|---|
| Work Centre Name | `MCH-CNC-01` |
| Is Group | ❌ NO |
| **Parent Work Centre** | `CNC-GROUP` |
| Total Working Hours | `8` (1-shift) or `16` (2-shift) |
| Capacity Planning | ✅ Enable |
| Holiday List | Your factory holiday list |

Repeat for `MCH-CNC-02`, `MCH-CNC-03`, etc.

**Verify tree looks like:**
```
CNC-GROUP (is_group=1)
├── MCH-CNC-01 (is_group=0)
├── MCH-CNC-02 (is_group=0)
└── MCH-CNC-03 (is_group=0)
```

---

### Step 3 — Create Operations

`Manufacturing → Operations → New`

| Field | Value |
|---|---|
| Operation Name | `CNC Turning` |
| **Workstation** | `CNC-GROUP` ← the GROUP, NOT MCH-CNC-01 |

> ⚠️ **#1 most common mistake:** linking Operation to an individual machine instead of the Group. If wrong, the engine never runs.

---

### Step 4 — Update BOMs

`Manufacturing → BOM → (each BOM) → Operations tab`

For every operation row:
- **Workstation** = `CNC-GROUP` (the group, not an individual machine)

Save and re-submit affected BOMs.

---

## 6. PHASE 3 — Configure Machine Selection Settings

`Search bar → Machine Selection Settings`

### 6.1 Scoring Weights (must sum to 100)

**v1.0 (4-factor):**

| Weight | Default | Meaning |
|---|---|---|
| Utilisation Load % | 30 | Penalises busy machines |
| Earliest Free Slot | 35 | Prefers machines free sooner |
| Delivery Slack | 25 | Penalises tight deadlines |
| Maintenance Risk | 10 | Avoids maintenance windows |

**v2.0 (5-factor — MRP branch):**

| Weight | Default | Meaning |
|---|---|---|
| Utilisation Load % | 25 | Same |
| Earliest Free Slot | 25 | Same |
| Delivery Slack | 20 | Same |
| Maintenance Risk | 10 | Same |
| **Material Readiness** | **20** | Penalises machines whose free slot is before materials arrive |

### 6.2 Thresholds

| Field | Recommended Value | Meaning |
|---|---|---|
| Overload Threshold % | 92 | Above this → capacity alert email |
| Rebalance Min Score Improvement | 10 | Minimum gain before reassigning |
| Rebalance Interval (minutes) | 30 | How often rebalancer runs |

### 6.3 Notifications

| Field | Value |
|---|---|
| Production Manager Email | `manager@yourcompany.com` |

### 6.4 MRP Settings (v2.0 only)

| Field | Value |
|---|---|
| Enable MRP Material Check | ✅ ON |
| Global Stock Check Warehouse | `Stores - YOUR_COMPANY` |

**Save.** System validates weights = 100. Fix if error shown.

---

## 7. PHASE 4 — Load Demo Data (Optional, for Testing)

```bash
bench --site YOUR-SITE.local execute \
    machine_capacity_planner.scripts.setup_demo_data.create_demo_data
```

Creates: CNC-GROUP, WELD-GROUP, LASER-GROUP + 9 machines + 3 Operations + Settings defaults.

---

## 8. PHASE 5 — First Live Test

### 8.1 Create and Submit a Work Order

1. `Sales Order → New` → add item with a BOM that has operations
2. From Sales Order → `Create → Work Order`
3. Select BOM, set planned dates, click **Save**
4. Click **Submit**

**Expected result:**
- Green alert: `"Machine Capacity Planner: 3/3 Job Cards auto-assigned"`
- Open any Job Card — `Workstation` shows a machine (e.g., `MCH-CNC-02`)
- `Machine Score` field has a value (e.g., `18.5`)
- `Allocated By` = `AUTO`
- (v2.0) `Material Status` = `Ready` / `Partial` / `Blocked`

### 8.2 Check the Audit Log

`Machine Capacity Planner → Selection Log`

One row per Job Card. Shows:
- Winner machine + score
- Runner-up machine + score
- All machine scores (JSON)

---

## 9. PHASE 6 — Daily Operations

### 9.1 Morning Routine (Production Manager)

| Time | Action |
|---|---|
| 5:00 AM (auto) | MRP sync runs — re-checks all open WO materials |
| 6:00 AM (auto) | Daily utilisation email arrives |
| Start of shift | Open **Capacity Planning Board** |

**Capacity Planning Board** (`Machine Capacity Planner → Capacity Planning Board`):
- 🟢 Green tile = OK (utilisation < 75%)
- 🟡 Yellow tile = High Load (75–91%)
- 🔴 Red tile = Overloaded (≥ 92%)
- (v2.0) Material badge on each tile: Ready / Partial / Blocked

### 9.2 Submit Work Orders

- Submit Work Orders as usual — machine assignment is fully automatic
- No manual selection required
- Review Planning Board after each batch of submissions

### 9.3 Handle Exceptions — Manual Override

When a machine breaks down or special tooling is needed:

`Machine Capacity Planner → Manual Overrides → New`

| Field | Action |
|---|---|
| Job Card | Select the affected Job Card |
| Override To Machine | Select the replacement machine |
| Reason | Select from dropdown (Machine Breakdown, etc.) |
| Notes | Add supplier / shift supervisor confirmation ref |

**Save.** Job Card is updated immediately and logged.

### 9.4 MRP Material Override (v2.0 only)

When supplier verbally confirms delivery (not yet in PO system):

`Machine Capacity Planner → Material Overrides → New`

| Field | Value |
|---|---|
| Work Order | Select WO |
| Confirmed Arrival Date | Date supplier confirmed |
| Notes | "Supplier ref #XYZ confirmed by phone — Ramesh 27-Apr" |

**Save.** MRP check is bypassed for this WO — machine assigned normally.

---

## 10. Automated Processes (No Action Required)

| Time | Process | What it does |
|---|---|---|
| Every 30 min | **Rebalancer** | Re-scores all open Job Cards. Reassigns if improvement ≥ 10 pts. Logs reason. |
| 5:00 AM (Mon–Sat) | **MRP Sync** | Re-checks all WO material readiness. If blocked WO is now ready → triggers rebalancer. Sends blocked/partial list email. |
| 6:00 AM (Mon–Sat) | **Daily Report Email** | Utilisation table for all machines — sent to Production Manager |
| 7:00 AM (Monday) | **Weekly Summary Email** | Week-in-review utilisation summary |

---

## 11. Reports

| Report | Path | Use |
|---|---|---|
| Machine Load Analysis | MCP → Machine Load Analysis | Daily: see booked vs free hours per machine |
| Machine Selection Audit | MCP → Machine Selection Audit | Traceability: why was machine X chosen? |
| Capacity Forecast | MCP → Capacity Forecast | Weekly planning: see load for next 7 days |
| Material Machine Alignment *(v2.0)* | MCP → Material-Machine Alignment | Identify WOs where machine will idle waiting for materials |

---

## 12. Upgrade Procedure

### 12.1 Upgrade to v2.0 (MRP branch)

```bash
cd ~/frappe-bench

# Switch to MRP feature branch
git -C apps/machine_capacity_planner fetch origin
git -C apps/machine_capacity_planner checkout feature/mrp-integration

bench --site YOUR-SITE.local migrate   # creates MRP Run Log + Material Readiness Override DocTypes
bench build --app machine_capacity_planner
bench restart
```

Then in ERPNext:
1. Open **Machine Selection Settings**
2. Set **Global Stock Check Warehouse**
3. Adjust weights to include **Material Readiness = 20**
4. Save

### 12.2 Routine App Update

```bash
cd ~/frappe-bench
bench update --app machine_capacity_planner
bench --site YOUR-SITE.local migrate
bench build --app machine_capacity_planner
bench restart
```

---

## 13. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Job Cards not auto-assigned after WO submit | BOM operation links to individual machine, not group | Edit Operation → Workstation = GROUP |
| "No active machines found" error | Child WCs disabled or wrong parent | Check Work Centre: `Is Group=No`, `Parent=CNC-GROUP`, `Disabled=No` |
| Machine Score = 0 on Job Card | Custom fields not migrated | `bench --site site migrate` |
| Planning Board shows blank | JS assets not built | `bench build --app machine_capacity_planner` |
| Weights validation error on Settings save | Weights don't sum to 100 | Adjust weights (v1: 4 weights; v2: 5 weights) |
| No daily email received | Manager email not set | Set email in Machine Selection Settings |
| Rebalancer not running | Scheduler stopped | `bench restart` + `bench doctor` |
| Material Status always "Ready" | MRP check disabled or no warehouse set | Check Settings: Enable MRP + set Warehouse |
| Material Status always "Blocked" | No open POs for raw materials | Create POs or use Material Readiness Override |

---

## 14. Escalation Matrix

| Issue | First Contact | Escalate To |
|---|---|---|
| Machine not assigned | Production Supervisor | IT Admin (check logs) |
| Planning Board blank | IT Admin | Bench restart |
| MRP showing wrong data | Production Manager | Check Production Plan linkage |
| App not found after install | IT Admin | Re-run `bench migrate` |
| Weights error | Production Manager | System Manager |
| GitHub/deployment issues | IT Admin | DevOps team |

---

## 15. Log File Location

```bash
# All MCP engine logs:
tail -f ~/frappe-bench/logs/machine_capacity_planner.log

# General frappe errors:
tail -f ~/frappe-bench/logs/frappe.log
```

---

## 16. Key Navigation Paths — Quick Reference

| What | Path |
|---|---|
| Planning Board | Search: `Capacity Planning Board` |
| Settings | Search: `Machine Selection Settings` |
| Manual Override | MCP Workspace → Manual Overrides |
| Material Override | MCP Workspace → Material Overrides |
| Selection Log | MCP Workspace → Selection Log |
| MRP Run Log | MCP Workspace → MRP Run Log |
| Machine Load Report | MCP Workspace → Machine Load Analysis |
| Alignment Report | MCP Workspace → Material-Machine Alignment |

---

## 17. Uninstall

```bash
bench --site YOUR-SITE.local uninstall-app machine_capacity_planner
bench --site YOUR-SITE.local migrate
bench restart
```

> ⚠️ This removes all MCP DocTypes and custom fields. Job Card history is unaffected.

---

*Document Owner: Production Manager | Review Cycle: Quarterly | Next Review: 2026-07-27*
