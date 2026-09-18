from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import pandas as pd


@dataclass(frozen=True)
class Line:
    line_code: str
    line_name: str


@dataclass(frozen=True)
class Station:
    station_id: str
    line_code: str
    seq: int
    is_interchange: bool


@dataclass(frozen=True)
class Sector:
    sector_id: str
    line_code: str
    from_station_id: str
    to_station_id: str
    seq: int
    is_shared: bool


@dataclass(frozen=True)
class LocationSupply:
    location_id: str
    location_kind: str  # 'tunnel sector' or 'platform sector'
    line_code: str
    bound: str  # 'EB' or 'WB'
    supply_capacity: int


@dataclass(frozen=True)
class BufferRule:
    nature_of_works: str
    up_to_buffer_sectors: int
    opposite_bound_required: bool


@dataclass(frozen=True)
class Contract:
    contract_number: str
    contract_description: str
    contract_award_date: str
    activity_type: str
    nature_of_activity: str
    contract_priority: int  # 1 (High), 2 (Default), 3 (Low)
    contract_completion_date: str
    planned_completion_date: str
    number_of_workfronts: int
    access_type: str  # 'PM', 'PC', 'C'
    number_of_maximum_access_per_week: int  # 2 for Live, 3 for others


@dataclass(frozen=True)
class Activity:
    activity_id: str
    contract_number: str
    activity_type: str
    start_location_id: str
    end_location_id: str
    total_accesses: int
    planned_start_date: str
    predecessor_activity_id: Optional[str]
    activity_priority: int  # 1 (High), 2 (Default), 3 (Low)


@dataclass
class ProblemInstance:
    horizon_start: date
    horizon_weeks: int
    lines: Dict[str, Line]
    stations: List[Station]
    sectors: List[Sector]
    location_supply: Dict[str, LocationSupply]
    buffer_rules: Dict[str, BufferRule]
    contracts: Dict[str, Contract]
    activities: Dict[str, Activity]

    # Pre-calculated helper mappings
    station_by_id: Dict[str, Station] = field(default_factory=dict)
    sector_by_id: Dict[str, Sector] = field(default_factory=dict)
    activities_by_contract: Dict[str, List[Activity]] = field(default_factory=dict)

    def __post_init__(self):
        for s in self.stations:
            # Note: H01 and H02 exist on both lines, store by (station_id, line_code)
            self.station_by_id[(s.station_id, s.line_code)] = s
        for sec in self.sectors:
            self.sector_by_id[sec.sector_id] = sec
        for act in self.activities.values():
            self.activities_by_contract.setdefault(act.contract_number, []).append(act)

    def date_to_week(self, d_str: str) -> int:
        """Calculate 1-based calendar week relative to horizon_start (Monday)."""
        d = datetime.strptime(d_str, "%Y-%m-%d").date()
        days_diff = (d - self.horizon_start).days
        return (days_diff // 7) + 1

    def week_end_date(self, week_num: int) -> date:
        """Returns the Sunday (end of week) for a 1-based calendar week."""
        return self.horizon_start + timedelta(days=int(week_num) * 7 - 1)

    def week_end_date_str(self, week_num: int) -> str:
        return self.week_end_date(week_num).strftime("%Y-%m-%d")


def load_problem_instance(data_dir: str | Path) -> ProblemInstance:
    """Load and parse the 8 CSV instance files into ProblemInstance."""
    path = Path(data_dir)

    # 1. Lines
    lines_df = pd.read_csv(path / "01_LINES.csv")
    lines = {
        row["line_code"]: Line(row["line_code"], row["line_name"])
        for _, row in lines_df.iterrows()
    }

    # 2. Stations
    stations_df = pd.read_csv(path / "02_STATIONS.csv")
    stations = [
        Station(
            station_id=row["station_id"],
            line_code=row["line_code"],
            seq=int(row["seq"]),
            is_interchange=bool(row["is_interchange"]),
        )
        for _, row in stations_df.iterrows()
    ]

    # 3. Sectors
    sectors_df = pd.read_csv(path / "03_SECTORS.csv")
    sectors = [
        Sector(
            sector_id=row["sector_id"],
            line_code=row["line_code"],
            from_station_id=row["from_station_id"],
            to_station_id=row["to_station_id"],
            seq=int(row["seq"]),
            is_shared=bool(row["is_shared"]),
        )
        for _, row in sectors_df.iterrows()
    ]

    # 4. Location Supply
    supply_df = pd.read_csv(path / "04_LOCATION_SUPPLY.csv")
    location_supply = {
        row["location_id"]: LocationSupply(
            location_id=row["location_id"],
            location_kind=row["location_kind"],
            line_code=row["line_code"],
            bound=row["bound"],
            supply_capacity=int(row["supply_capacity"]),
        )
        for _, row in supply_df.iterrows()
    }

    # 5. Buffer rules
    buffer_df = pd.read_csv(path / "05_BUFFER_LOCATION.csv")
    buffer_rules = {
        row["nature_of_works"]: BufferRule(
            nature_of_works=row["nature_of_works"],
            up_to_buffer_sectors=int(row["up_to_buffer_sectors"]),
            opposite_bound_required=bool(row["opposite_bound_required"]),
        )
        for _, row in buffer_df.iterrows()
    }

    # 6. Parameters
    param_df = pd.read_csv(path / "06_PARAMETERS.csv")
    param_map = dict(zip(param_df["key"], param_df["value"]))
    horizon_start = datetime.strptime(str(param_map["horizon_start"]), "%Y-%m-%d").date()
    horizon_weeks = int(param_map["horizon_weeks"])

    # 7. Projects
    proj_df = pd.read_csv(path / "07_PROJECT_DETAILS.csv")
    contracts = {
        row["contract_number"]: Contract(
            contract_number=row["contract_number"],
            contract_description=row["contract_description"],
            contract_award_date=str(row["contract_award_date"]),
            activity_type=str(row["activity_type"]),
            nature_of_activity=str(row["nature_of_activity"]),
            contract_priority=int(row["contract_priority"]),
            contract_completion_date=str(row["contract_completion_date"]),
            planned_completion_date=str(row["planned_completion_date"]),
            number_of_workfronts=int(row["number_of_workfronts"]),
            access_type=str(row["access_type"]),
            number_of_maximum_access_per_week=int(row["number_of_maximum_access_per_week"]),
        )
        for _, row in proj_df.iterrows()
    }

    # 8. Activities
    act_df = pd.read_csv(path / "08_ACTIVITY_DETAILS.csv")
    activities = {
        row["activity_id"]: Activity(
            activity_id=row["activity_id"],
            contract_number=row["contract_number"],
            activity_type=str(row["activity_type"]),
            start_location_id=str(row["start_location_id"]),
            end_location_id=str(row["end_location_id"]),
            total_accesses=int(row["total_accesses"]),
            planned_start_date=str(row["planned_start_date"]),
            predecessor_activity_id=str(row["predecessor_activity_id"]) if pd.notna(row["predecessor_activity_id"]) and str(row["predecessor_activity_id"]).strip() else None,
            activity_priority=int(row["activity_priority"]),
        )
        for _, row in act_df.iterrows()
    }

    return ProblemInstance(
        horizon_start=horizon_start,
        horizon_weeks=horizon_weeks,
        lines=lines,
        stations=stations,
        sectors=sectors,
        location_supply=location_supply,
        buffer_rules=buffer_rules,
        contracts=contracts,
        activities=activities,
    )
