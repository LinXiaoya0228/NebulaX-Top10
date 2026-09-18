from pathlib import Path

import pandas as pd

from src.models import load_problem_instance
from src.solver import TrackAccessSolver
from src.validator import Validator


def test_scenario_a_solves_without_seed():
    root = Path(__file__).resolve().parent.parent
    instance = load_problem_instance(root / "01_data")
    solution = TrackAccessSolver(instance).solve("A", time_limit_sec=20)
    report = Validator(instance).validate(
        pd.DataFrame(solution.access_records),
        pd.DataFrame(solution.occupancy_records),
        pd.DataFrame(solution.results_records),
        "A",
    )
    assert solution.access_records
    assert report.feasible, [violation.detail for violation in report.hard_violations]