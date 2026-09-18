import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd
from src.models import load_problem_instance
from src.validator import Validator, validate_submission_files


@pytest.fixture(scope="module")
def instance():
    data_dir = Path(__file__).resolve().parent.parent / "01_data"
    return load_problem_instance(data_dir)


def test_scenario_a():
    base_dir = Path(__file__).resolve().parent.parent
    report = validate_submission_files(
        instance_dir=base_dir / "01_data",
        submission_dir=base_dir / "results" / "scenario_A",
        scenario="A",
    )
    assert report.feasible is True, f"Scenario A failed: {[v.detail for v in report.hard_violations]}"
    assert len(report.hard_violations) == 0
    assert report.soft_scores["eclo_nights_total"] == 0, "Scenario A cannot have ECLO"
    assert report.soft_scores["excess_access_nights_total"] == 0, "Scenario A cannot have excess capacity"
    assert report.soft_scores["priority_overrun"]["1"] == 0, "P1 contracts must not overrun"
    assert report.soft_scores["priority_overrun"]["2"] == 0, "P2 contracts must not overrun"


def test_scenario_b():
    base_dir = Path(__file__).resolve().parent.parent
    report = validate_submission_files(
        instance_dir=base_dir / "01_data",
        submission_dir=base_dir / "results" / "scenario_B",
        scenario="B",
    )
    assert report.feasible is True, f"Scenario B failed: {[v.detail for v in report.hard_violations]}"
    assert len(report.hard_violations) == 0
    assert report.soft_scores["overrun_days_total"] == 0, "Scenario B requires 0 overrun days"
    assert report.soft_scores["contracts_overrunning"] == 0


def test_scenario_c():
    base_dir = Path(__file__).resolve().parent.parent
    report = validate_submission_files(
        instance_dir=base_dir / "01_data",
        submission_dir=base_dir / "results" / "scenario_C",
        scenario="C",
    )
    assert report.feasible is True, f"Scenario C failed: {[v.detail for v in report.hard_violations]}"
    assert len(report.hard_violations) == 0
    assert report.soft_scores["excess_access_nights_total"] <= 14, "Scenario C capacity within tolerance"


def test_results_are_recomputed_from_schedule(instance):
    base_dir = Path(__file__).resolve().parent.parent
    result_dir = base_dir / "results" / "scenario_A"
    access_df = pd.read_csv(result_dir / "SCHEDULE_ACCESS.csv")
    occupancy_df = pd.read_csv(result_dir / "SCHEDULE_OCCUPANCY.csv")
    results_df = pd.read_csv(result_dir / "RESULTS.csv")
    expected_score = Validator(instance).validate(
        access_df, occupancy_df, results_df, "A"
    ).soft_scores["objective_score"]
    results_df["simulated_completion_date"] = instance.horizon_start.isoformat()
    results_df["overrun_days"] = 0

    report = Validator(instance).validate(access_df, occupancy_df, results_df, "A")

    assert any(v.rule == "results_mismatch" for v in report.hard_violations)
    assert report.soft_scores["objective_score"] == expected_score


def test_missing_occupancy_is_rejected(instance):
    base_dir = Path(__file__).resolve().parent.parent
    result_dir = base_dir / "results" / "scenario_A"
    access_df = pd.read_csv(result_dir / "SCHEDULE_ACCESS.csv")
    occupancy_df = pd.read_csv(result_dir / "SCHEDULE_OCCUPANCY.csv").iloc[1:]
    results_df = pd.read_csv(result_dir / "RESULTS.csv")

    report = Validator(instance).validate(access_df, occupancy_df, results_df, "A")

    assert any(v.rule == "occupancy" for v in report.hard_violations)
