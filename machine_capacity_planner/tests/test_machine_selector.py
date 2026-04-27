"""
Unit tests for machine_selector.py

Run locally (no ERPNext needed):
    pytest machine_capacity_planner/tests/ -v

Run inside bench:
    bench --site your-site.local run-tests --app machine_capacity_planner
"""

import sys
import pytest
from unittest.mock import patch, MagicMock


# ── Stub frappe so tests run without a live ERPNext instance ─────────────────
frappe_mock = MagicMock()
frappe_mock.utils.time_diff_in_hours = lambda a, b: 24.0
frappe_mock.utils.getdate = lambda x: x
frappe_mock.utils.now_datetime = lambda: "2025-09-15 06:00:00"
frappe_mock.logger = MagicMock(return_value=MagicMock())

# Stub frappe.model.document so DocType controllers can be imported
class _FakeDocument:
    pass

frappe_model_mock = MagicMock()
frappe_model_mock.document.Document = _FakeDocument

sys.modules["frappe"]                 = frappe_mock
sys.modules["frappe.utils"]           = frappe_mock.utils
sys.modules["frappe.model"]           = frappe_model_mock
sys.modules["frappe.model.document"]  = frappe_model_mock.document

from machine_capacity_planner.utils import machine_selector as sel   # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "w_load": 25,
    "w_free": 25,
    "w_slack": 20,
    "w_maint": 10,
    "w_material": 20,
    "overload_threshold_pct": 92,
    "rebalance_threshold": 10,
    "manager_email": "manager@test.com",
    "enable_mrp_check": False,   # disabled by default in unit tests (no DB)
    "material_check_warehouse": "",
}


def mock_capacity(
    utilisation=50,
    free_hrs=10,
    earliest_free=0,
    has_maint=0,
    horizon_hrs=24,
    gross_hrs=16,
    committed_hrs=8,
):
    return {
        "utilisation":   utilisation,
        "free_hrs":      free_hrs,
        "earliest_free": earliest_free,
        "has_maint":     has_maint,
        "horizon_hrs":   horizon_hrs,
        "gross_hrs":     gross_hrs,
        "committed_hrs": committed_hrs,
    }


# ── Tests: _calculate_score ───────────────────────────────────────────────────
class TestCalculateScore:

    def test_idle_machine_has_low_score(self):
        cap   = mock_capacity(utilisation=0, free_hrs=16, earliest_free=0, has_maint=0)
        score = sel._calculate_score(cap, DEFAULT_SETTINGS)
        assert score < 10, f"Idle machine should score < 10, got {score}"

    def test_overloaded_machine_has_high_score(self):
        cap   = mock_capacity(utilisation=95, free_hrs=0, earliest_free=20, has_maint=1)
        score = sel._calculate_score(cap, DEFAULT_SETTINGS)
        assert score > 70, f"Overloaded machine should score > 70, got {score}"

    def test_maintenance_adds_weight_penalty(self):
        cap_no_maint = mock_capacity(utilisation=50, has_maint=0)
        cap_maint    = mock_capacity(utilisation=50, has_maint=1)
        s1 = sel._calculate_score(cap_no_maint, DEFAULT_SETTINGS)
        s2 = sel._calculate_score(cap_maint,    DEFAULT_SETTINGS)
        assert s2 > s1,                                  "Maintenance should worsen score"
        assert abs(s2 - s1 - DEFAULT_SETTINGS["w_maint"]) < 0.01

    def test_score_bounded_within_sum_of_weights(self):
        cap = mock_capacity(utilisation=100, free_hrs=0, earliest_free=24, has_maint=1)
        cap["material_delay_hrs"] = 24.0
        score = sel._calculate_score(cap, DEFAULT_SETTINGS)
        max_score = sum(DEFAULT_SETTINGS[k] for k in ["w_load", "w_free", "w_slack", "w_maint", "w_material"])
        assert 0 <= score <= max_score + 0.01, f"Score {score} out of bounds [0, {max_score}]"

    def test_earlier_free_slot_gives_better_score(self):
        cap_now  = mock_capacity(earliest_free=0,  utilisation=50)
        cap_late = mock_capacity(earliest_free=20, utilisation=50)
        s1 = sel._calculate_score(cap_now,  DEFAULT_SETTINGS)
        s2 = sel._calculate_score(cap_late, DEFAULT_SETTINGS)
        assert s2 > s1, "Machine free later should score worse"

    def test_better_delivery_slack_gives_better_score(self):
        cap_good = mock_capacity(free_hrs=20, horizon_hrs=24, utilisation=50)
        cap_poor = mock_capacity(free_hrs=2,  horizon_hrs=24, utilisation=50)
        s1 = sel._calculate_score(cap_good, DEFAULT_SETTINGS)
        s2 = sel._calculate_score(cap_poor, DEFAULT_SETTINGS)
        assert s2 > s1, "Tighter slack should score worse"

    def test_score_is_zero_for_perfect_machine(self):
        """A machine with 0% load, free now, full slack, no maintenance → score ~0"""
        cap   = mock_capacity(
            utilisation=0, free_hrs=24, earliest_free=0, has_maint=0, horizon_hrs=24
        )
        score = sel._calculate_score(cap, DEFAULT_SETTINGS)
        assert score < 1, f"Perfect machine should score near 0, got {score}"


# ── Tests: select_best_machine ────────────────────────────────────────────────
class TestSelectBestMachine:

    THREE_MACHINES = [
        {"name": "MCH-01", "capacity_planning_factor": 1, "description": ""},
        {"name": "MCH-02", "capacity_planning_factor": 1, "description": ""},
        {"name": "MCH-03", "capacity_planning_factor": 1, "description": ""},
    ]
    CAPACITIES = {
        "MCH-01": mock_capacity(utilisation=78, free_hrs=3,  earliest_free=2),
        "MCH-02": mock_capacity(utilisation=45, free_hrs=10, earliest_free=0),  # winner
        "MCH-03": mock_capacity(utilisation=91, free_hrs=1,  earliest_free=8),
    }

    @patch.object(sel, "_get_settings",          return_value=DEFAULT_SETTINGS)
    @patch.object(sel, "_log_selection")
    @patch.object(sel, "_create_capacity_alert")
    @patch.object(sel, "_get_candidate_machines")
    @patch.object(sel, "get_machine_capacity")
    @patch("frappe.db.get_value",                return_value="CNC-GROUP")
    def test_selects_lowest_load_machine(
        self, mock_gv, mock_cap, mock_candidates, mock_alert, mock_log, mock_settings
    ):
        mock_candidates.return_value = self.THREE_MACHINES
        mock_cap.side_effect = lambda name, *a, **kw: self.CAPACITIES[name]

        result = sel.select_best_machine("CNC Turning", "2025-09-15", "2025-09-16", 5)

        assert result is not None
        assert result["name"] == "MCH-02", (
            f"Expected MCH-02 (lowest load 45%), got {result['name']}"
        )

    @patch.object(sel, "_get_settings",          return_value=DEFAULT_SETTINGS)
    @patch.object(sel, "_create_capacity_alert")
    @patch.object(sel, "_get_candidate_machines")
    @patch.object(sel, "get_machine_capacity")
    @patch("frappe.db.get_value",                return_value="CNC-GROUP")
    def test_returns_none_when_all_machines_overloaded(
        self, mock_gv, mock_cap, mock_candidates, mock_alert, mock_settings
    ):
        mock_candidates.return_value = self.THREE_MACHINES
        mock_cap.return_value = mock_capacity(utilisation=95, free_hrs=0)

        result = sel.select_best_machine("CNC Turning", "2025-09-15", "2025-09-16")

        assert result is None
        mock_alert.assert_called_once()

    @patch("frappe.db.get_value", return_value=None)
    def test_returns_none_when_operation_has_no_wc_group(self, _):
        result = sel.select_best_machine("UNKNOWN_OP", "2025-09-15", "2025-09-16")
        assert result is None

    @patch.object(sel, "_get_settings",          return_value=DEFAULT_SETTINGS)
    @patch.object(sel, "_log_selection")
    @patch.object(sel, "_create_capacity_alert")
    @patch.object(sel, "_get_candidate_machines")
    @patch.object(sel, "get_machine_capacity")
    @patch("frappe.db.get_value",                return_value="CNC-GROUP")
    def test_machine_with_maintenance_not_chosen_when_alternative_available(
        self, mock_gv, mock_cap, mock_candidates, mock_alert, mock_log, mock_settings
    ):
        machines = [
            {"name": "MCH-A", "capacity_planning_factor": 1, "description": ""},
            {"name": "MCH-B", "capacity_planning_factor": 1, "description": ""},
        ]
        caps = {
            "MCH-A": mock_capacity(utilisation=50, has_maint=1),   # penalised
            "MCH-B": mock_capacity(utilisation=55, has_maint=0),   # should win
        }
        mock_candidates.return_value = machines
        mock_cap.side_effect = lambda name, *a, **kw: caps[name]

        result = sel.select_best_machine("CNC Turning", "2025-09-15", "2025-09-16")

        assert result is not None
        assert result["name"] == "MCH-B", (
            "MCH-B (no maintenance) should beat MCH-A (has maintenance)"
        )


# ── Tests: MRP Material Readiness scoring (F5) ────────────────────────────────
class TestMRPScoring:
    """Tests for the 5th scoring factor: material readiness."""

    MRP_SETTINGS = {**DEFAULT_SETTINGS, "w_material": 20}

    def test_zero_material_delay_adds_no_penalty(self):
        """If material arrives before machine is free → F5 = 0."""
        cap = {**mock_capacity(utilisation=50), "material_delay_hrs": 0.0}
        s_without = sel._calculate_score(cap, {**self.MRP_SETTINGS, "w_material": 0})
        s_with    = sel._calculate_score(cap,  self.MRP_SETTINGS)
        assert abs(s_with - s_without) < 0.01, "Zero delay should add no F5 penalty"

    def test_material_delay_increases_score(self):
        """Machine that must wait 12h for materials should score worse."""
        cap_ready   = {**mock_capacity(utilisation=50), "material_delay_hrs": 0.0}
        cap_delayed = {**mock_capacity(utilisation=50), "material_delay_hrs": 12.0}
        s1 = sel._calculate_score(cap_ready,   self.MRP_SETTINGS)
        s2 = sel._calculate_score(cap_delayed, self.MRP_SETTINGS)
        assert s2 > s1, "Delayed materials should worsen machine score"

    def test_material_delay_proportional_to_weight(self):
        """Full delay (delay = horizon) adds exactly w_material to score."""
        cap = {**mock_capacity(utilisation=0, earliest_free=0, free_hrs=24, has_maint=0, horizon_hrs=24),
               "material_delay_hrs": 24.0}
        settings = {**self.MRP_SETTINGS, "w_load": 0, "w_free": 0, "w_slack": 0, "w_maint": 0, "w_material": 20}
        score = sel._calculate_score(cap, settings)
        assert abs(score - 20.0) < 0.01, f"Full delay should add exactly 20 (w_material), got {score}"

    def test_material_delay_capped_at_weight(self):
        """Delay > horizon should not exceed w_material contribution."""
        cap = {**mock_capacity(horizon_hrs=8), "material_delay_hrs": 999.0}
        settings = {**self.MRP_SETTINGS, "w_load": 0, "w_free": 0, "w_slack": 0, "w_maint": 0, "w_material": 20}
        score = sel._calculate_score(cap, settings)
        assert score <= 20.0 + 0.01, f"Capped at w_material=20, got {score}"

    def test_machine_with_ready_materials_beats_delayed_machine(self):
        """Same utilisation but one machine's materials arrive 8h late → loses."""
        cap_ready   = {**mock_capacity(utilisation=55), "material_delay_hrs": 0.0}
        cap_delayed = {**mock_capacity(utilisation=50), "material_delay_hrs": 8.0}
        s_ready   = sel._calculate_score(cap_ready,   self.MRP_SETTINGS)
        s_delayed = sel._calculate_score(cap_delayed, self.MRP_SETTINGS)
        assert s_delayed > s_ready, (
            "Machine with material delay should score worse despite lower utilisation"
        )

    def test_weight_validation_includes_w_material(self):
        """Settings validator must count w_material in the sum."""
        from machine_capacity_planner.doctype.machine_selection_settings.machine_selection_settings import (
            MachineSelectionSettings,
        )
        doc = MachineSelectionSettings.__new__(MachineSelectionSettings)
        doc.weight_load               = 25
        doc.weight_free_slot          = 25
        doc.weight_delivery_slack     = 20
        doc.weight_maintenance_risk   = 10
        doc.weight_material_readiness = 20   # total = 100

        with patch("frappe.throw") as mock_throw:
            doc.validate()
            mock_throw.assert_not_called()   # should pass

    def test_weight_validation_fails_without_w_material(self):
        """Old 4-weight config (30+35+25+10=100) should now fail with w_material=0."""
        from machine_capacity_planner.doctype.machine_selection_settings.machine_selection_settings import (
            MachineSelectionSettings,
        )
        doc = MachineSelectionSettings.__new__(MachineSelectionSettings)
        doc.weight_load               = 30
        doc.weight_free_slot          = 35
        doc.weight_delivery_slack     = 25
        doc.weight_maintenance_risk   = 10
        doc.weight_material_readiness = 0    # total = 100 still — should PASS

        with patch("frappe.throw") as mock_throw:
            doc.validate()
            mock_throw.assert_not_called()   # 30+35+25+10+0 = 100 → valid
