# Standard Operating Procedure (SOP)
# Machine Capacity Planner v3.0 — End-to-End Implementation

**Effective Date:** 2026-04-27 | **Owner:** Production & Operations Management

---

> [!NOTE]
> **Purpose of this SOP**
> This document defines the end-to-end procedures for configuring and operating the Machine Capacity Planner (MCP) app on ERPNext v15. It ensures operations are automatically assigned to the best Workstations using a 5-factor scoring engine, evaluating both machine capacity and material readiness.

---

## 1. PHASE ONE: Initial System Configuration (One-Time Setup)

Before the automation engine can work, the master data must be properly configured.

### Step 1.1: Configure Workstation Groups
The engine works by choosing the best individual machine out of a broader "Group".
1. Go to `Manufacturing > Workstation`
2. Click **New**
3. Create the group (e.g., `CNC-GROUP`)
4. **CRITICAL:** Check the box that says `Is Group`. Do not assign working hours to the group.

### Step 1.2: Configure Individual Workstations & Resources
You must define the individual resources that belong to the groups.
1. Go to `Manufacturing > Workstation`
2. Click **New** (e.g., `MCH-CNC-01`)
3. Set **Parent Workstation** to the group you created (e.g., `CNC-GROUP`).
4. Set the **Resource Type**:
   - `Machine`: For standard automated equipment.
   - `Manpower`: For manual stations (Stores, Quality, Assembly). You must also enter the **Operators Count** (e.g., 3).
   - `External`: For subcontracting (the system will skip assigning these).
5. Save the document.

### Step 1.3: Link Operations & BOMs to Groups
The most common implementation mistake is linking an operation to an individual machine.
1. Go to `Manufacturing > Operation`
2. Open an operation (e.g., `CNC Turning`)
3. Set the **Default Workstation** to the **GROUP** (e.g., `CNC-GROUP`), *never* an individual machine like `CNC-01`.
4. Ensure your Bill of Materials (BOM) also points to the Workstation Group.

---

## 2. PHASE TWO: Global Settings & Thresholds

> [!IMPORTANT]
> The scoring algorithm and escalation engines rely entirely on these settings.

Go to `Machine Capacity Planner > Machine Selection Settings` and configure:

### 2.1 Scoring Weights
Ensure the weights total exactly 100.
* **Utilisation Load % (e.g., 25):** Penalizes busy machines.
* **Earliest Free Slot (e.g., 25):** Prioritizes machines that can start sooner.
* **Delivery Slack (e.g., 20):** Penalizes tight delivery windows.
* **Maintenance Risk (e.g., 10):** Avoids machines with upcoming maintenance.
* **Material Readiness (e.g., 20):** Prefers machines whose free slot aligns with the expected arrival of raw materials.

### 2.2 MRP & Alerts
* **Enable MRP Material Check:** Turn `ON` and set your `Global Stock Check Warehouse`.
* **Escalation Emails:** Enter the email addresses for the Production Supervisor and Plant Head.
* **Escalation Thresholds:** Set how many hours a Job Card can sit un-started before triggering alerts:
  * Warning After: `0` hours
  * Critical After: `4` hours
  * Stopped After: `8` hours

---

## 3. PHASE THREE: Daily Planning & Execution (The Automated Workflow)

### 3.1 Generating the Plan
1. Planners navigate to `Manufacturing > Production Plan` to generate Work Orders.
2. Open the newly created **Work Order** and click **Submit**.

### 3.2 The Automated Engine (Behind the Scenes)
The moment a Work Order is submitted, the system automatically:
1. Calculates the **Full-Part Cycle Time** based on machine hours or manpower operators.
2. Checks **Material Readiness** via the MRP engine.
3. Scores every Workstation in the Group out of 100.
4. Auto-assigns the winning Workstation to the newly generated **Job Cards**.

> [!TIP]
> You can view exactly *why* a Workstation was chosen by checking the **Machine Selection Log**.

### 3.3 Floor Execution
1. Floor Supervisors and Operators open the **Capacity Planning Board**.
2. The board visually displays the queue:
   * 🟢 Green = Normal Load (< 75%)
   * 🟡 Yellow = High Load (75–91%)
   * 🔴 Red = Overloaded (≥ 92%)
3. Operators open their assigned Job Cards and click **Start** and **Complete** as they work.

---

## 4. PHASE FOUR: Exception Handling & Escalations

### 4.1 Automated Escalations
If an operator does not start a Job Card on time, the system takes action:
* **0 Hours Overdue:** A Warning email is sent to the Supervisor.
* **4 Hours Overdue:** A Critical email is sent to the Supervisor.
* **8 Hours Overdue:** A Stopped email is sent to the Plant Head.
* Every alert is permanently logged in the **Escalation Log** DocType.

### 4.2 Manual Overrides
Sometimes manual intervention is required. Do not edit the Job Card directly.
* **Machine Breakdowns:** Use the `Machine Capacity Override` DocType. Select the Job Card, choose the replacement Workstation, and select the reason (e.g., Machine Breakdown). The system reassigns it immediately.
* **Verbal Material Confirmations:** If a supplier confirms a delivery but it's not in the system yet, use the `Material Readiness Override` DocType. This tells the MRP engine to stop penalizing that Work Order.

### 4.3 Automated Background Jobs
* **Every 30 Mins:** The Rebalancer checks all open Job Cards. If a much better Workstation has opened up, it reassigns the queue.
* **Daily @ 5:00 AM:** The MRP Sync re-checks material availability for all open Work Orders.
* **Daily @ 6:00 AM:** The Daily Utilisation Report is emailed to the Production Manager.
