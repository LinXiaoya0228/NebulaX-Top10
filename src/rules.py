from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple
from src.graph import RailNetworkGraph, parse_location_id
from src.models import Activity, Contract, ProblemInstance


@dataclass
class ActivityFootprint:
    activity_id: str
    physical_occupancy: List[str]  # PLAT and SEC directly occupied
    buffer_locations: List[str]    # Buffer sectors and their platforms
    mirrored_locations: List[str]  # Opposite bound for Live
    cross_line_locations: List[str]# Cross-line interchange for Live
    all_closed_locations: Set[str] = field(default_factory=set)

    def __post_init__(self):
        self.all_closed_locations = (
            set(self.physical_occupancy)
            | set(self.buffer_locations)
            | set(self.mirrored_locations)
            | set(self.cross_line_locations)
        )


class RuleEngine:
    def __init__(self, instance: ProblemInstance, graph: RailNetworkGraph):
        self.instance = instance
        self.graph = graph
        self.activity_footprints: Dict[str, ActivityFootprint] = {}
        self._compute_all_footprints()

    def _compute_all_footprints(self):
        for act in self.instance.activities.values():
            contract = self.instance.contracts[act.contract_number]
            nature = contract.nature_of_activity
            buffer_rule = self.instance.buffer_rules.get(nature)
            buf_sectors_count = buffer_rule.up_to_buffer_sectors if buffer_rule else 0
            opp_bound_req = buffer_rule.opposite_bound_required if buffer_rule else False

            # 1. Physical occupancy
            physical = self.graph.expand_activity_occupancy(
                act.start_location_id, act.end_location_id
            )

            # Extract line, bound, and sector indices
            kind, line_code, seg_start, bound = parse_location_id(act.start_location_id)
            _, _, seg_end, _ = parse_location_id(act.end_location_id)
            opp_bound = "WB" if bound == "EB" else "EB"

            idx1 = self.graph.sector_index[(line_code, seg_start)]
            idx2 = self.graph.sector_index[(line_code, seg_end)]
            min_sec_idx = min(idx1, idx2)
            max_sec_idx = max(idx1, idx2)

            line_sectors = self.graph.line_sectors[line_code]
            total_sec_count = len(line_sectors)

            # 2. Buffer sectors (ahead and behind)
            buffer_locs: List[str] = []
            if buf_sectors_count > 0:
                # Buffer ahead (lower indices)
                start_buf_idx = max(0, min_sec_idx - buf_sectors_count)
                ahead_sectors = line_sectors[start_buf_idx:min_sec_idx]

                # Buffer behind (higher indices)
                end_buf_idx = min(total_sec_count - 1, max_sec_idx + buf_sectors_count)
                behind_sectors = line_sectors[max_sec_idx + 1 : end_buf_idx + 1]

                for sec in list(ahead_sectors) + list(behind_sectors):
                    from_to = f"{sec.from_station_id}_{sec.to_station_id}"
                    buffer_locs.append(f"SEC:{line_code}:{from_to}:{bound}")
                    buffer_locs.append(f"PLAT:{line_code}:{sec.from_station_id}:{bound}")
                    buffer_locs.append(f"PLAT:{line_code}:{sec.to_station_id}:{bound}")

            # 3. Mirrored opposite bound (if Live)
            mirrored_locs: List[str] = []
            if opp_bound_req:
                # Mirror physical occupancy
                for loc in physical:
                    k, l, s, b = parse_location_id(loc)
                    mirrored_locs.append(f"{k}:{l}:{s}:{opp_bound}")
                # Mirror buffer locations
                for loc in buffer_locs:
                    k, l, s, b = parse_location_id(loc)
                    mirrored_locs.append(f"{k}:{l}:{s}:{opp_bound}")

            # 4. Cross-line interchange exception (if Live and touches H01_H02)
            cross_line_locs: List[str] = []
            if nature == "Live":
                # Check if physical or buffer includes H01_H02
                touches_interchange = any(
                    "H01_H02" in loc or "H01" in loc or "H02" in loc
                    for loc in physical + buffer_locs
                )
                if touches_interchange:
                    other_line = "BET" if line_code == "ALP" else "ALP"
                    for b_dir in ["EB", "WB"]:
                        cross_line_locs.append(f"SEC:{other_line}:H01_H02:{b_dir}")
                        cross_line_locs.append(f"PLAT:{other_line}:H01:{b_dir}")
                        cross_line_locs.append(f"PLAT:{other_line}:H02:{b_dir}")

            self.activity_footprints[act.activity_id] = ActivityFootprint(
                activity_id=act.activity_id,
                physical_occupancy=physical,
                buffer_locations=buffer_locs,
                mirrored_locations=mirrored_locs,
                cross_line_locations=cross_line_locs,
            )

    def can_co_share(self, act_id1: str, act_id2: str) -> bool:
        """
        Check if two activities can co-share a possession slot.
        - Must be on the exact same physical locations or compatible.
        - Access types must satisfy legal mixes:
          PM alone (cannot co-share with anything else),
          PC with C (or C with C).
        """
        act1 = self.instance.activities[act_id1]
        act2 = self.instance.activities[act_id2]
        c1 = self.instance.contracts[act1.contract_number]
        c2 = self.instance.contracts[act2.contract_number]

        # PM is sole possession, cannot share
        if c1.access_type == "PM" or c2.access_type == "PM":
            return False

        # Two PCs cannot co-share together (max 1 PC per slot)
        if c1.access_type == "PC" and c2.access_type == "PC":
            return False

        return True

    def are_independent(self, act_id1: str, act_id2: str) -> bool:
        """
        Check if two activities have zero spatial conflict (their complete footprints do not overlap).
        If independent, they can run on the same night in separate possessions without conflict.
        """
        fp1 = self.activity_footprints[act_id1]
        fp2 = self.activity_footprints[act_id2]
        return len(fp1.all_closed_locations.intersection(fp2.all_closed_locations)) == 0
