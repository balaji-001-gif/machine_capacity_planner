/**
 * Capacity Planning Board
 * ========================
 * Live dashboard showing real-time machine load for all Workstation Groups.
 * Auto-refreshes every 60 seconds. Allows manual rebalance trigger.
 *
 * Layout:
 *   - Summary cards (total machines, avg utilisation, overloaded count)
 *   - Per-group section with one card per machine
 *   - Horizon selector (1–7 days)
 *   - "Trigger Rebalance" button for Production Managers
 */

frappe.pages["capacity_planning_board"].on_page_load = function (wrapper) {

    // ── Page setup ────────────────────────────────────────────────────────
    const page = frappe.ui.make_app_page({
        parent:        wrapper,
        title:         "Capacity Planning Board",
        single_column: false,
    });

    // ── Toolbar controls ──────────────────────────────────────────────────
    page.add_button(__("Refresh"), () => refresh_dashboard(true), { icon: "refresh" });

    page.add_button(__("Trigger Rebalance"), () => {
        frappe.confirm(
            "Re-evaluate and possibly reassign all open Job Cards. Continue?",
            () => trigger_rebalance(),
        );
    }, { icon: "repeat", type: "primary" });

    const horizon_field = page.add_field({
        label:     "Horizon (Days)",
        fieldtype: "Int",
        fieldname: "horizon_days",
        default:   1,
        change()   { refresh_dashboard(true); },
    });

    // ── Main container ────────────────────────────────────────────────────
    const $main = $(`
        <div class="mcp-board" style="padding:16px;">
            <div class="mcp-summary row" style="margin-bottom:20px;"></div>
            <div class="mcp-groups"></div>
        </div>
    `).appendTo(page.main);

    // ── Data loading ──────────────────────────────────────────────────────
    async function refresh_dashboard(is_manual = false) {
        // Prevent rogue background refreshing if user navigated away
        if (!is_manual && frappe.get_route()[0] !== "capacity_planning_board") return;

        const horizon = horizon_field.get_value() || 1;
        
        if (is_manual) {
            frappe.show_progress("Loading capacity data...", 30, 100);
        }

        try {
            const r = await frappe.call({
                method: "machine_capacity_planner.api.capacity.get_all_groups_capacity",
                args:   { horizon_days: horizon },
            });
            if (is_manual) frappe.hide_progress();
            render_board(r.message || []);
        } catch (e) {
            if (is_manual) {
                frappe.hide_progress();
                frappe.msgprint({ message: "Failed to load capacity data.", indicator: "red" });
            }
        }
    }

    // ── Rendering ─────────────────────────────────────────────────────────
    function render_board(groups) {
        $main.find(".mcp-summary").empty();
        $main.find(".mcp-groups").empty();

        // Summary cards
        const total_machines = groups.reduce((a, g) => a + g.machines.length, 0);
        const overloaded     = groups.reduce((a, g) =>
            a + g.machines.filter(m => m.utilisation >= 92).length, 0);
        const avg_util = groups.length
            ? groups.reduce((a, g) => a + g.summary.avg_utilisation, 0) / groups.length
            : 0;

        $main.find(".mcp-summary").html(`
            ${summary_card("Total Machines",   total_machines,              "#2E86C1")}
            ${summary_card("Avg Utilisation",  avg_util.toFixed(1) + "%",
                avg_util >= 92 ? "#E74C3C" : avg_util >= 75 ? "#F39C12" : "#27AE60")}
            ${summary_card("Overloaded",       overloaded,
                overloaded > 0 ? "#E74C3C" : "#27AE60")}
            ${summary_card("Machine Groups",   groups.length,               "#8E44AD")}
        `);

        // Per-group machine cards
        groups.forEach(g => {
            const $group = $(`
                <div class="mcp-group" style="margin-bottom:24px;">
                    <h5 style="color:#0B2545; border-bottom:2px solid #2E86C1;
                               padding-bottom:6px; margin-bottom:12px;">
                        ${g.group}
                        <small style="color:#7F8C8D; font-size:11px; margin-left:8px;">
                            Avg: ${g.summary.avg_utilisation}%
                            &nbsp;|&nbsp;
                            Free: ${g.summary.total_free_hrs} hrs
                        </small>
                    </h5>
                    <div class="row mcp-machine-row"></div>
                </div>
            `).appendTo($main.find(".mcp-groups"));

            g.machines.forEach(m => {
                const color = m.utilisation >= 92 ? "#E74C3C"
                            : m.utilisation >= 75 ? "#F39C12"
                            : "#27AE60";

                $(`
                    <div class="col-md-4">
                        <div style="
                            border:1px solid #E0E0E0;
                            border-left:4px solid ${color};
                            border-radius:8px;
                            padding:14px 16px;
                            margin-bottom:12px;
                            background:#fff;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <strong style="font-size:15px;">${m.name}</strong>
                                <span style="
                                    background:${color}; color:#fff;
                                    border-radius:12px; padding:2px 10px; font-size:12px;">
                                    ${m.utilisation.toFixed(1)}%
                                </span>
                            </div>
                            <div style="margin:10px 0;">
                                ${progress_bar(m.utilisation, color)}
                            </div>
                            <div style="font-size:12px; color:#666; display:flex; gap:16px;">
                                <span>Booked: <strong>${m.committed_hrs}h</strong></span>
                                <span>Free: <strong>${m.free_hrs}h</strong></span>
                                <span>Gross: <strong>${m.gross_hrs}h</strong></span>
                            </div>
                            <div style="margin-top:8px;">
                                <a href="/app/job-card?workstation=${encodeURIComponent(m.name)}&status=Open"
                                   target="_blank"
                                   style="font-size:11px; color:#2E86C1;">
                                    View Job Queue →
                                </a>
                            </div>
                        </div>
                    </div>
                `).appendTo($group.find(".mcp-machine-row"));
            });
        });

        // Show empty state
        if (!groups.length) {
            $main.find(".mcp-groups").html(`
                <div style="text-align:center; padding:60px; color:#999;">
                    <div style="font-size:48px;">🏭</div>
                    <p>No Workstation Groups found. Add machines in Manufacturing → Workstation.</p>
                </div>
            `);
        }
    }

    // ── Template helpers ──────────────────────────────────────────────────
    function summary_card(label, value, color) {
        return `
            <div class="col-md-3">
                <div style="background:${color}; color:#fff; border-radius:8px;
                            padding:14px 18px; text-align:center; margin-bottom:10px;
                            box-shadow:0 2px 8px rgba(0,0,0,0.12);">
                    <div style="font-size:28px; font-weight:700;">${value}</div>
                    <div style="font-size:11px; opacity:0.85; margin-top:4px;">${label}</div>
                </div>
            </div>`;
    }

    function progress_bar(pct, color) {
        const w = Math.min(pct, 100).toFixed(1);
        return `
            <div style="background:#F0F0F0; border-radius:4px; height:8px; overflow:hidden;">
                <div style="width:${w}%; background:${color}; height:100%;
                            border-radius:4px; transition:width 0.4s ease;">
                </div>
            </div>`;
    }

    // ── Actions ───────────────────────────────────────────────────────────
    async function trigger_rebalance() {
        frappe.show_progress("Rebalancing...", 50, 100);
        try {
            const r = await frappe.call({
                method: "machine_capacity_planner.api.capacity.trigger_rebalance",
            });
            frappe.hide_progress();
            frappe.show_alert({
                message:   r.message?.message || "Rebalancing done.",
                indicator: "green",
            });
            refresh_dashboard(true);
        } catch (e) {
            frappe.hide_progress();
            frappe.msgprint({ message: "Rebalance failed. Check error log.", indicator: "red" });
        }
    }

    // ── Init ──────────────────────────────────────────────────────────────
    refresh_dashboard(true);
    setInterval(() => refresh_dashboard(false), 60_000);   // silent auto-refresh every 60s
};
