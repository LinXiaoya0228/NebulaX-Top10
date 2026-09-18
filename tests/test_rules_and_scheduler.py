"""
tests/test_rules_and_scheduler.py - Unit tests for validator rules, legal mixes,
co-sharing, and end-to-end scheduler execution across Scenarios A, B, and C.
"""

import os
import pytest
import pandas as pd
from data_parser import DataMall
from validator import Validator
from scheduler import ScenarioScheduler


@pytest.fixture(scope="module")
def dm():
    return DataMall("PS1/01_data")


@pytest.fixture(scope="module")
def validator():
    return Validator("PS1/01_data")


@pytest.fixture(scope="module")
def scheduler():
    return ScenarioScheduler("PS1/01_data")


def test_sample_submission_validation(validator):
    report = validator.validate("PS1/03_submission_sample", "A")
    assert report["feasible"] is True
    assert len(report["hard_violations"]) == 0
    assert report["soft_scores"]["objective_score"] == 32.2
    assert report["soft_scores"]["overrun_days_total"] == 28
    assert report["soft_scores"]["excess_access_nights_total"] == 0
    assert report["soft_scores"]["eclo_nights_total"] == 0


def test_scenario_A_solver_and_validator(scheduler, validator, tmp_path):
    out_dir = str(tmp_path / "scenario_A")
    report = scheduler.solve("A", out_dir, timeout_seconds=15, verbose=False)
    assert report["feasible"] is True
    assert len(report["hard_violations"]) == 0
    assert report["soft_scores"]["objective_score"] <= 32.2
    assert report["soft_scores"]["excess_access_nights_total"] == 0
    assert report["soft_scores"]["eclo_nights_total"] == 0

    # Verify generated files
    assert os.path.exists(os.path.join(out_dir, "SCHEDULE_ACCESS.csv"))
    assert os.path.exists(os.path.join(out_dir, "SCHEDULE_OCCUPANCY.csv"))
    assert os.path.exists(os.path.join(out_dir, "RESULTS.csv"))


def test_scenario_B_zero_overrun(scheduler, validator, tmp_path):
    out_dir = str(tmp_path / "scenario_B")
    report = scheduler.solve("B", out_dir, timeout_seconds=15, verbose=False)
    assert report["feasible"] is True
    assert len(report["hard_violations"]) == 0
    assert report["soft_scores"]["overrun_days_total"] == 0
    assert report["soft_scores"]["contracts_overrunning"] == 0
    assert report["soft_scores"]["objective_score"] >= 0


def test_scenario_C_pareto_tradeoff(scheduler, validator, tmp_path):
    out_dir = str(tmp_path / "scenario_C")
    report = scheduler.solve("C", out_dir, timeout_seconds=15, verbose=False)
    assert report["feasible"] is True
    assert len(report["hard_violations"]) == 0
    assert report["soft_scores"]["objective_score"] >= 0


def test_predecessor_strict_later_week_rule(dm, validator, tmp_path):
    # Verify that if successor starts in the same week as predecessor finish, validator catches it
    out_dir = str(tmp_path / "pred_test")
    os.makedirs(out_dir, exist_ok=True)

    access_df = pd.read_csv("PS1/03_submission_sample/SCHEDULE_ACCESS.csv")
    occ_df = pd.read_csv("PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv")
    res_df = pd.read_csv("PS1/03_submission_sample/RESULTS.csv")

    # A004 has predecessor A003. In sample, A003 finishes week 16.
    # A004 starts in week 21.
    # If we shift A004's first access to week 16:
    bad_access = access_df.copy()
    mask_a = (bad_access["activity_id"] == "A004") & (bad_access["week"] == 21)
    bad_access.loc[mask_a, "week"] = 16

    bad_occ = occ_df.copy()
    mask_o = (bad_occ["activity_id"] == "A004") & (bad_occ["week"] == 21)
    bad_occ.loc[mask_o, "week"] = 16

    bad_access.to_csv(os.path.join(out_dir, "SCHEDULE_ACCESS.csv"), index=False)
    bad_occ.to_csv(os.path.join(out_dir, "SCHEDULE_OCCUPANCY.csv"), index=False)
    res_df.to_csv(os.path.join(out_dir, "RESULTS.csv"), index=False)

    report = validator.validate(out_dir, "A")
    assert report["feasible"] is False
    assert any(v["rule"] == "predecessor" for v in report["hard_violations"])


def test_legal_mix_validation(validator, tmp_path):
    # Multiple PMs in same slot or PC + >3 C must be caught by validator
    out_dir = str(tmp_path / "legal_mix_test")
    os.makedirs(out_dir, exist_ok=True)

    access_df = pd.read_csv("PS1/03_submission_sample/SCHEDULE_ACCESS.csv")
    occ_df = pd.read_csv("PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv")
    res_df = pd.read_csv("PS1/03_submission_sample/RESULTS.csv")

    # In sample, A075 is PM (Contract C014) in week 29 at SEC:BET:H01_H02:WB with co_share_group b1
    # Add a co-worker to that exact slot:
    bad_occ = occ_df.copy()
    extra_row = pd.DataFrame([{
        "activity_id": "A001",
        "week": 29,
        "location_id": "SEC:BET:H01_H02:WB",
        "co_share_group": "b1",
    }])
    bad_occ = pd.concat([bad_occ, extra_row], ignore_index=True)

    access_df.to_csv(os.path.join(out_dir, "SCHEDULE_ACCESS.csv"), index=False)
    bad_occ.to_csv(os.path.join(out_dir, "SCHEDULE_OCCUPANCY.csv"), index=False)
    res_df.to_csv(os.path.join(out_dir, "RESULTS.csv"), index=False)

    report = validator.validate(out_dir, "A")
    assert report["feasible"] is False
    assert any(v["rule"] == "legal_mix" for v in report["hard_violations"])


def test_scenario_A_eclo_forbidden(validator, tmp_path):
    # ECLO in Scenario A must be caught as hard violation
    out_dir = str(tmp_path / "eclo_test")
    os.makedirs(out_dir, exist_ok=True)

    access_df = pd.read_csv("PS1/03_submission_sample/SCHEDULE_ACCESS.csv")
    occ_df = pd.read_csv("PS1/03_submission_sample/SCHEDULE_OCCUPANCY.csv")
    res_df = pd.read_csv("PS1/03_submission_sample/RESULTS.csv")

    bad_access = access_df.copy()
    bad_access.loc[0, "eclo"] = 1

    bad_access.to_csv(os.path.join(out_dir, "SCHEDULE_ACCESS.csv"), index=False)
    occ_df.to_csv(os.path.join(out_dir, "SCHEDULE_OCCUPANCY.csv"), index=False)
    res_df.to_csv(os.path.join(out_dir, "RESULTS.csv"), index=False)

    report = validator.validate(out_dir, "A")
    assert report["feasible"] is False
    assert any(v["rule"] == "eclo" for v in report["hard_violations"])
