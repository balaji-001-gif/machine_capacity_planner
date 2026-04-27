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
sys.modules["frappe"]       = frappe_mock
sys.modules["frappe.utils"] = frappe_mock.utils

from machine_capacity_planner.utils import machine_selector as sel   # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "w_load": 30,
    "w_free": 35,
    "w_slack": 25,
    "w_maint": 10,
    "overload_threshold_pct": 92,
    "rebalance_threshold": 10,
    "manager_email": "manager@test.com",
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
        score = sel._calculate_score(cap, DEFAULT_SETTINGS)
        max_score = sum(DEFAULT_SETTINGS[k] for k in ["w_load", "w_free", "w_slack", "w_maint"])
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
