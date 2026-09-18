"""
test_phase2_modules.py - Test suite for Phase 2 Industrial Works Control platform modules.
"""

import os
import pandas as pd
import pytest

from operations_sandbox import (
    AdHocMaintenanceActivity,
    DisruptionEngine,
    DisruptionScenario,
    MaintenancePlanner,
    SandboxManager,
)
from passenger_advisor import (
    CommuterImpactCalculator,
    ECLOWindowAdvisor,
    PassengerDataAdapter,
)
from explainer import DeterministicExplainer, HandoverBriefingGenerator


def test_sandbox_manager_isolation():
    sb = SandboxManager(scenario="A")
    assert sb.working_scenario == "A"
    assert not sb.access_df.empty
    assert not sb.occ_df.empty

    # Mutate working access_df and ensure official baseline is not changed
    orig_len = len(sb.access_df)
    sb.access_df.drop(sb.access_df.index[0], inplace=True)
    assert len(sb.access_df) == orig_len - 1

    # Official file on disk should remain untouched
    disk_df = pd.read_csv("results/scenario_A/SCHEDULE_ACCESS.csv")
    assert len(disk_df) == orig_len


def test_maintenance_coshare_feasibility():
    sb = SandboxManager(scenario="A")
    planner = MaintenancePlanner(sb)

    # Ad-hoc inspection activity on Beta line
    m_act = AdHocMaintenanceActivity(
        id="M_TEST_01",
        name="Signaling Track Circuit Calibration",
        category="Signaling Maintenance",
        owning_team="Signal Maintenance Dep 1",
        nature_of_work="Non-live",
        consist_type="Non-consist",
        access_type="C",
        line_code="BET",
        bound="EB",
        start_stn="H01",
        end_stn="H02",
        preferred_weeks=[10, 11],
        required_accesses=1,
    )

    feasibility_results = planner.check_coshare_feasibility(m_act, target_week=10)
    assert len(feasibility_results) >= 1
    # Check that diagnostic strings are properly populated
    for res in feasibility_results:
        assert "mode" in res
        assert "feasible" in res
        assert "diagnostic" in res


def test_disruption_preview_and_auto_replan():
    sb = SandboxManager(scenario="A")
    engine = DisruptionEngine(sb)

    # Close sector PLAT:ALP:S01:EB on week 10
    disr = DisruptionScenario(
        id="DISR_TEST_01",
        title="Rail Crack at Station S01 EB",
        disruption_type="Rail Defect",
        line_code="ALP",
        bound="EB",
        locations=["PLAT:ALP:S01:EB"],
        weeks=[10],
        revised_capacity=0,
    )

    preview = engine.preview_disruption(disr)
    assert "directly_displaced_activities" in preview
    assert "PLAT:ALP:S01:EB" in disr.locations

    # Run minimal-churn hot replan
    replan_res = engine.auto_replan(disr, max_time_seconds=10)
    assert replan_res["success"] is True
    assert replan_res["activities_moved"] >= 0

    # Validate that replanned schedule is 100% compliant with 0 hard violations
    val = sb.validate_current_working_schedule()
    assert val["feasible"] is True
    assert len(val["hard_violations"]) == 0


def test_passenger_adapter_and_impact_calc():
    adapter = PassengerDataAdapter()
    assert adapter.metadata["source"] == "LTA DataMall API v6.8"
    assert len(adapter.station_volumes) > 0

    calc = CommuterImpactCalculator(adapter)
    access_df_c = pd.read_csv("results/scenario_C/SCHEDULE_ACCESS.csv")
    impact = calc.calculate_eclo_passenger_impact(access_df_c)
    assert impact["total_eclo_accesses"] > 0
    assert impact["impacted_commuters"] > 0
    assert "disruption_level" in impact


def test_eclo_window_advisor():
    advisor = ECLOWindowAdvisor()
    report = advisor.get_pareto_recommendation_report("BET")
    assert "recommended_window" in report
    assert "estimated_pax_affected" in report
    assert report["estimated_pax_affected"] > 0
    assert report["all_evaluated_windows_count"] == 29


def test_deterministic_explainer():
    exp = DeterministicExplainer()
    access_df_a = pd.read_csv("results/scenario_A/SCHEDULE_ACCESS.csv")

    res = exp.explain_contract_milestone("C006", access_df_a)
    assert res["contract_number"] == "C006"
    assert len(res["root_causes"]) > 0
    assert "activity_chain" in res


def test_handover_briefing_generator_and_html(tmp_path):
    gen = HandoverBriefingGenerator()
    access_df_a = pd.read_csv("results/scenario_A/SCHEDULE_ACCESS.csv")
    occ_df_a = pd.read_csv("results/scenario_A/SCHEDULE_OCCUPANCY.csv")

    brief = gen.generate_shift_briefing(
        current_week=10,
        access_night=1,
        access_df=access_df_a,
        occ_df=occ_df_a,
        scenario_name="Scenario A",
    )
    assert brief["summary_kpis"]["active_possessions_tonight"] >= 0
    assert len(brief["action_checklist"]) == 6

    html_file = str(tmp_path / "test_briefing.html")
    exported = gen.export_html_briefing(brief, html_file)
    assert os.path.exists(exported)
    with open(exported, "r", encoding="utf-8") as f:
        content = f.read()
    assert "2 AM WORKS CONTROLLER SHIFT HANDOVER BRIEFING" in content

