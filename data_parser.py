"""
data_parser.py - Data loading, schema validation, network topology,
path expansion, and conflict analysis for Railway Track Access Optimisation.
"""

from __future__ import annotations
import os
import csv
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Optional, Any


@dataclass
class Station:
    station_id: str
    line_code: str
    seq: int
    is_interchange: bool


@dataclass
class Sector:
    sector_id: str
    line_code: str
    from_station_id: str
    to_station_id: str
    seq: int
    is_shared: bool


@dataclass
class LocationSupply:
    location_id: str
    location_kind: str
    line_code: str
    bound: str
    supply_capacity: int


@dataclass
class ProjectContract:
    contract_number: str
    contract_description: str
    contract_award_date: str
    activity_type: str
    nature_of_activity: str
    contract_priority: int
    contract_completion_date: str
    planned_completion_date: str
    number_of_workfronts: int
    access_type: str
    number_of_maximum_access_per_week: int


@dataclass
class Activity:
    activity_id: str
    contract_number: str
    activity_type: str
    start_location_id: str
    end_location_id: str
    total_accesses: int
    planned_start_date: str
    predecessor_activity_id: Optional[str]
    activity_priority: int
    # Derived fields
    planned_start_week: int = 1
    expanded_locations: Set[str] = field(default_factory=set)
    tunnel_sectors: List[str] = field(default_factory=list)
    platform_sectors: List[str] = field(default_factory=list)
    line_code: str = ""
    bound: str = ""
    min_sector_seq: int = 0
    max_sector_seq: int = 0


class DataMall:
    """Encapsulates all parsed data, network topology, and relationship lookups."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.horizon_start_str: str = "2027-01-04"
        self.horizon_start: datetime = datetime.strptime("2027-01-04", "%Y-%m-%d")
        self.horizon_weeks: int = 30

        self.lines: List[str] = []
        self.stations: Dict[str, List[Station]] = {"ALP": [], "BET": []}
        self.station_map: Dict[str, Station] = {}
        self.station_order: Dict[str, List[str]] = {"ALP": [], "BET": []}

        self.sectors: Dict[str, List[Sector]] = {"ALP": [], "BET": []}
        self.sector_map: Dict[str, Sector] = {}

        self.location_supply: Dict[str, LocationSupply] = {}
        self.buffer_rules: Dict[str, Tuple[int, bool]] = {}  # nature -> (sectors, opposite_mirror)
        self.contracts: Dict[str, ProjectContract] = {}
        self.activities: Dict[str, Activity] = {}

        self._load_parameters()
        self._load_lines()
        self._load_stations()
        self._load_sectors()
        self._load_location_supply()
        self._load_buffer_location()
        self._load_project_details()
        self._load_activity_details()
        self._validate_and_build_topology()

    def _read_csv(self, filename: str) -> List[Dict[str, str]]:
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Required input file missing: {filepath}")
        with open(filepath, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            return [row for row in reader]

    def _load_parameters(self):
        rows = self._read_csv("06_PARAMETERS.csv")
        for r in rows:
            key = r["key"].strip()
            val = r["value"].strip()
            if key == "horizon_start":
                self.horizon_start_str = val
                self.horizon_start = datetime.strptime(val, "%Y-%m-%d")
            elif key == "horizon_weeks":
                self.horizon_weeks = int(val)

    def _load_lines(self):
        rows = self._read_csv("01_LINES.csv")
        self.lines = [r["line_code"].strip() for r in rows]

    def _load_stations(self):
        rows = self._read_csv("02_STATIONS.csv")
        for r in rows:
            stn = Station(
                station_id=r["station_id"].strip(),
                line_code=r["line_code"].strip(),
                seq=int(r["seq"].strip()),
                is_interchange=bool(int(r["is_interchange"].strip())),
            )
            self.stations[stn.line_code].append(stn)
            self.station_map[f"{stn.line_code}:{stn.station_id}"] = stn

        for line in self.stations:
            self.stations[line].sort(key=lambda s: s.seq)
            self.station_order[line] = [s.station_id for s in self.stations[line]]

    def _load_sectors(self):
        rows = self._read_csv("03_SECTORS.csv")
        for r in rows:
            sec = Sector(
                sector_id=r["sector_id"].strip(),
                line_code=r["line_code"].strip(),
                from_station_id=r["from_station_id"].strip(),
                to_station_id=r["to_station_id"].strip(),
                seq=int(r["seq"].strip()),
                is_shared=bool(int(r["is_shared"].strip())),
            )
            self.sectors[sec.line_code].append(sec)
            self.sector_map[sec.sector_id] = sec

        for line in self.sectors:
            self.sectors[line].sort(key=lambda s: s.seq)

    def _load_location_supply(self):
        rows = self._read_csv("04_LOCATION_SUPPLY.csv")
        for r in rows:
            loc_id = r["location_id"].strip()
            self.location_supply[loc_id] = LocationSupply(
                location_id=loc_id,
                location_kind=r["location_kind"].strip(),
                line_code=r["line_code"].strip(),
                bound=r["bound"].strip(),
                supply_capacity=int(r["supply_capacity"].strip()),
            )

    def _load_buffer_location(self):
        rows = self._read_csv("05_BUFFER_LOCATION.csv")
        for r in rows:
            nature = r["nature_of_works"].strip()
            bufs = int(r["up_to_buffer_sectors"].strip())
            opp = bool(int(r["opposite_bound_required"].strip()))
            self.buffer_rules[nature] = (bufs, opp)

    def _load_project_details(self):
        rows = self._read_csv("07_PROJECT_DETAILS.csv")
        for r in rows:
            cid = r["contract_number"].strip()
            self.contracts[cid] = ProjectContract(
                contract_number=cid,
                contract_description=r.get("contract_description", "").strip(),
                contract_award_date=r.get("contract_award_date", "").strip(),
                activity_type=r["activity_type"].strip(),
                nature_of_activity=r["nature_of_activity"].strip(),
                contract_priority=int(r["contract_priority"].strip()),
                contract_completion_date=r["contract_completion_date"].strip(),
                planned_completion_date=r["planned_completion_date"].strip(),
                number_of_workfronts=int(r["number_of_workfronts"].strip()),
                access_type=r["access_type"].strip(),
                number_of_maximum_access_per_week=int(r["number_of_maximum_access_per_week"].strip()),
            )

    def _load_activity_details(self):
        rows = self._read_csv("08_ACTIVITY_DETAILS.csv")
        for r in rows:
            aid = r["activity_id"].strip()
            pred = r.get("predecessor_activity_id", "").strip()
            if not pred:
                pred = None

            p_start_str = r["planned_start_date"].strip()
            p_start_dt = datetime.strptime(p_start_str, "%Y-%m-%d")
            p_start_week = max(1, (p_start_dt - self.horizon_start).days // 7 + 1)

            act = Activity(
                activity_id=aid,
                contract_number=r["contract_number"].strip(),
                activity_type=r["activity_type"].strip(),
                start_location_id=r["start_location_id"].strip(),
                end_location_id=r["end_location_id"].strip(),
                total_accesses=int(r["total_accesses"].strip()),
                planned_start_date=p_start_str,
                predecessor_activity_id=pred,
                activity_priority=int(r["activity_priority"].strip()),
                planned_start_week=p_start_week,
            )
            self.activities[aid] = act

    def _validate_and_build_topology(self):
        # 1. Expand paths for all activities
        for act in self.activities.values():
            locs, secs, plats, line, bound, min_seq, max_seq = self.expand_route(
                act.start_location_id, act.end_location_id
            )
            act.expanded_locations = locs
            act.tunnel_sectors = secs
            act.platform_sectors = plats
            act.line_code = line
            act.bound = bound
            act.min_sector_seq = min_seq
            act.max_sector_seq = max_seq

        # 2. Cycle detection on predecessor graph
        self.detect_predecessor_cycles()

    def expand_route_by_endpoints(
        self, line_code: str, bound: str, start_stn: str, end_stn: str
    ) -> Set[str]:
        """Convenience method to expand a route given line, bound, and station endpoints."""
        dummy_act = Activity(
            activity_id="DUMMY",
            contract_number="C000",
            activity_type="DUMMY",
            total_accesses=1,
            planned_start_date="2027-01-04",
            planned_start_week=1,
            activity_priority=1,
            line_code=line_code,
            bound=bound,
            start_location_id=start_stn,
            end_location_id=end_stn,
            predecessor_activity_id=None,
        )
        return self.expand_route(dummy_act.start_location_id, dummy_act.end_location_id)[0]

    def _parse_endpoint_stations(self, line: str, loc_str: str) -> Tuple[int, int]:
        """Returns (min_stn_idx, max_stn_idx) in station_order[line] for a location endpoint."""
        parts = loc_str.split(":")
        kind = parts[0]
        stn_list = self.station_order[line]
        if kind == "PLAT":
            stn_id = parts[2]
            idx = stn_list.index(stn_id)
            return idx, idx
        elif kind == "SEC":
            pair = parts[2]
            if "_" in pair:
                from_stn, to_stn = pair.split("_")
                idx1 = stn_list.index(from_stn)
                idx2 = stn_list.index(to_stn)
                return min(idx1, idx2), max(idx1, idx2)
            else:
                idx = stn_list.index(pair)
                return idx, idx
        else:
            raise ValueError(f"Unknown location kind in endpoint: {loc_str}")

    def expand_route(self, start_loc: str, end_loc: str) -> Tuple[Set[str], List[str], List[str], str, str, int, int]:
        """
        Expands start_loc and end_loc to all tunnel sectors and platform sectors.
        Input formats supported:
          - SEC:<line>:<from>_<to>:<bound>
          - PLAT:<line>:<station_id>:<bound>
        """
        s_parts = start_loc.split(":")
        e_parts = end_loc.split(":")
        s_line, s_bound = s_parts[1], s_parts[-1]
        e_line, e_bound = e_parts[1], e_parts[-1]

        if s_line != e_line or s_bound != e_bound:
            raise ValueError(f"Route crosses lines or bounds directly: {start_loc} -> {end_loc}")

        line = s_line
        bound = s_bound
        line_secs = self.sectors[line]
        stn_list = self.station_order[line]

        s_min_stn, s_max_stn = self._parse_endpoint_stations(line, start_loc)
        e_min_stn, e_max_stn = self._parse_endpoint_stations(line, end_loc)

        overall_stn_min = min(s_min_stn, e_min_stn)
        overall_stn_max = max(s_max_stn, e_max_stn)

        # Platform sectors touched
        touched_plats = [f"PLAT:{line}:{stn_list[k]}:{bound}" for k in range(overall_stn_min, overall_stn_max + 1)]

        # Tunnel sectors touched
        touched_secs = []
        sec_seqs = []
        for k in range(overall_stn_min, overall_stn_max):
            from_s = stn_list[k]
            to_s = stn_list[k + 1]
            # Match sector
            sec_match = next(
                (sec for sec in line_secs if (sec.from_station_id == from_s and sec.to_station_id == to_s)
                 or (sec.from_station_id == to_s and sec.to_station_id == from_s)),
                None
            )
            if sec_match:
                touched_secs.append(f"{sec_match.sector_id}:{bound}")
                sec_seqs.append(sec_match.seq)

        min_seq = min(sec_seqs) if sec_seqs else 0
        max_seq = max(sec_seqs) if sec_seqs else 0

        all_locations = set(touched_secs + touched_plats)
        return all_locations, touched_secs, touched_plats, line, bound, min_seq, max_seq

    def detect_predecessor_cycles(self) -> List[str]:
        """Returns topological ordering of activities or raises ValueError on cycle."""
        adj: Dict[str, List[str]] = {aid: [] for aid in self.activities}
        in_degree: Dict[str, int] = {aid: 0 for aid in self.activities}

        for aid, act in self.activities.items():
            if act.predecessor_activity_id:
                pred = act.predecessor_activity_id
                if pred not in self.activities:
                    raise ValueError(f"Predecessor activity {pred} not found in activities list.")
                adj[pred].append(aid)
                in_degree[aid] += 1

        queue = [aid for aid, deg in in_degree.items() if deg == 0]
        topo_order = []

        while queue:
            curr = queue.pop(0)
            topo_order.append(curr)
            for succ in adj[curr]:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        if len(topo_order) != len(self.activities):
            raise ValueError("Predecessor dependency cycle detected among activities!")

        return topo_order

    def get_safety_footprint(self, activity_id: str) -> Dict[str, Any]:
        """
        Computes work span, buffer sectors, opposite bound mirroring, and interchange cross-line.
        """
        act = self.activities[activity_id]
        contract = self.contracts[act.contract_number]
        nature = contract.nature_of_activity
        buf_sectors_count, opp_mirror = self.buffer_rules.get(nature, (0, False))

        work_span = set(act.expanded_locations)
        buffer_locations = set()
        mirror_locations = set()
        cross_line_locations = set()

        line = act.line_code
        bound = act.bound
        opp_bound = "WB" if bound == "EB" else "EB"
        line_secs = self.sectors[line]

        # 1. Exclusion buffer sectors on the same line and bound
        s_indices = [
            i for i, sec in enumerate(line_secs)
            if f"{sec.sector_id}:{bound}" in act.tunnel_sectors
        ]
        if s_indices and buf_sectors_count > 0:
            min_i = min(s_indices)
            max_i = max(s_indices)
            # upstream buffer
            for b in range(1, buf_sectors_count + 1):
                idx = min_i - b
                if 0 <= idx < len(line_secs):
                    buffer_locations.add(f"{line_secs[idx].sector_id}:{bound}")
            # downstream buffer
            for b in range(1, buf_sectors_count + 1):
                idx = max_i + b
                if 0 <= idx < len(line_secs):
                    buffer_locations.add(f"{line_secs[idx].sector_id}:{bound}")
        elif not s_indices and act.platform_sectors and buf_sectors_count > 0:
            stn_list = self.station_order[line]
            touched_stn_indices = [
                stn_list.index(loc.split(":")[2])
                for loc in act.platform_sectors if loc.split(":")[2] in stn_list
            ]
            if touched_stn_indices:
                min_s = min(touched_stn_indices)
                max_s = max(touched_stn_indices)
                for b in range(1, buf_sectors_count + 1):
                    idx = min_s - b
                    if 0 <= idx < len(line_secs):
                        buffer_locations.add(f"{line_secs[idx].sector_id}:{bound}")
                for b in range(buf_sectors_count):
                    idx = max_s + b
                    if 0 <= idx < len(line_secs):
                        buffer_locations.add(f"{line_secs[idx].sector_id}:{bound}")

        # 2. Opposite bound mirroring (only for Live)
        if opp_mirror:
            for loc in work_span | buffer_locations:
                parts = loc.split(":")
                kind = parts[0]
                l = parts[1]
                target = parts[2]
                mirror_locations.add(f"{kind}:{l}:{target}:{opp_bound}")

        # 3. Interchange cross-line closure (only for Live touching H01-H02)
        if nature == "Live":
            # Check if H01-H02 tunnel sector or platforms are occupied
            touches_interchange = any(
                "H01" in loc or "H02" in loc for loc in work_span
            )
            if touches_interchange:
                other_line = "BET" if line == "ALP" else "ALP"
                for b in ["EB", "WB"]:
                    cross_line_locations.add(f"SEC:{other_line}:H01_H02:{b}")
                    cross_line_locations.add(f"PLAT:{other_line}:H01:{b}")
                    cross_line_locations.add(f"PLAT:{other_line}:H02:{b}")

        total_closure = work_span | buffer_locations | mirror_locations | cross_line_locations

        return {
            "activity_id": activity_id,
            "work_span": work_span,
            "buffer_locations": buffer_locations,
            "mirror_locations": mirror_locations,
            "cross_line_locations": cross_line_locations,
            "total_closure": total_closure,
            "nature": nature,
        }

    def date_for_week_end(self, week: int) -> str:
        """Returns the simulated completion date (Sunday) for a given week."""
        # Week 1 ends on horizon_start + 6 days
        end_dt = self.horizon_start + timedelta(days=int(week) * 7 - 1)
        return end_dt.strftime("%Y-%m-%d")

    def week_for_date(self, date_str: str) -> int:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return max(1, (dt - self.horizon_start).days // 7 + 1)
