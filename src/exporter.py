from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd

from src.graph import RailNetworkGraph
from src.models import ProblemInstance


@dataclass
class ScheduleSolution:
    scenario: str
    # Map (activity_id, week) -> {'eclo': int, 'access_night': int, 'co_share_group': str}
    # Or detailed per-access records:
    access_records: List[Dict]  # activity_id, access_seq, week, eclo, access_night
    occupancy_records: List[Dict]  # activity_id, week, location_id, co_share_group
    results_records: List[Dict]  # scenario, contract_number, simulated_completion_date, overrun_days


class ScheduleExporter:
    def __init__(self, instance: ProblemInstance, graph: RailNetworkGraph):
        self.instance = instance
        self.graph = graph

    def export_solution(self, solution: ScheduleSolution, output_dir: str | Path):
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # 1. SCHEDULE_ACCESS.csv
        access_df = pd.DataFrame(solution.access_records)
        access_cols = ["activity_id", "access_seq", "week", "eclo", "access_night"]
        access_df = access_df[access_cols].sort_values(by=["activity_id", "access_seq"])
        access_df.to_csv(out_path / "SCHEDULE_ACCESS.csv", index=False)

        # 2. SCHEDULE_OCCUPANCY.csv
        occ_df = pd.DataFrame(solution.occupancy_records)
        occ_cols = ["activity_id", "week", "location_id", "co_share_group"]
        occ_df = occ_df[occ_cols].sort_values(by=["activity_id", "week", "location_id"])
        occ_df.to_csv(out_path / "SCHEDULE_OCCUPANCY.csv", index=False)

        # 3. RESULTS.csv
        results_df = pd.DataFrame(solution.results_records)
        results_cols = ["scenario", "contract_number", "simulated_completion_date", "overrun_days"]
        results_df = results_df[results_cols].sort_values(by=["contract_number"])
        results_df.to_csv(out_path / "RESULTS.csv", index=False)
