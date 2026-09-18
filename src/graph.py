from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
from src.models import ProblemInstance, Sector, Station


def parse_location_id(location_id: str) -> Tuple[str, str, str, str]:
    """
    Parses a location_id into (kind, line_code, segment, bound).
    e.g.
    'SEC:ALP:S01_S02:EB' -> ('SEC', 'ALP', 'S01_S02', 'EB')
    'PLAT:ALP:S01:EB' -> ('PLAT', 'ALP', 'S01', 'EB')
    """
    parts = location_id.split(":")
    if len(parts) == 4:
        return parts[0], parts[1], parts[2], parts[3]
    raise ValueError(f"Invalid location_id format: {location_id}")


class RailNetworkGraph:
    def __init__(self, instance: ProblemInstance):
        self.instance = instance

        # Line -> ordered list of stations
        self.line_stations: Dict[str, List[Station]] = {}
        for s in sorted(instance.stations, key=lambda x: (x.line_code, x.seq)):
            self.line_stations.setdefault(s.line_code, []).append(s)

        # Line -> ordered list of sectors
        self.line_sectors: Dict[str, List[Sector]] = {}
        for sec in sorted(instance.sectors, key=lambda x: (x.line_code, x.seq)):
            self.line_sectors.setdefault(sec.line_code, []).append(sec)

        # Mapping sector_id without bound -> Sector object
        self.base_sector_map: Dict[str, Sector] = {s.sector_id: s for s in instance.sectors}

        # Sector index lookup: (line_code, from_to_str) -> int index in line_sectors
        self.sector_index: Dict[Tuple[str, str], int] = {}
        for line_code, sec_list in self.line_sectors.items():
            for idx, sec in enumerate(sec_list):
                # sec.sector_id is like 'SEC:ALP:S01_S02'
                from_to = f"{sec.from_station_id}_{sec.to_station_id}"
                self.sector_index[(line_code, from_to)] = idx
                self.sector_index[(line_code, sec.sector_id)] = idx

    def expand_activity_occupancy(
        self, start_location_id: str, end_location_id: str
    ) -> List[str]:
        """
        Given activity start_location_id and end_location_id,
        returns the complete ordered list of occupied location IDs:
        first all PLAT:..., then all SEC:... (matching official sample format).
        """
        kind_start, line_start, seg_start, bound_start = parse_location_id(start_location_id)
        kind_end, line_end, seg_end, bound_end = parse_location_id(end_location_id)

        if line_start != line_end:
            raise ValueError(f"Start and end lines do not match: {line_start} vs {line_end}")
        if bound_start != bound_end:
            raise ValueError(f"Start and end bounds do not match: {bound_start} vs {bound_end}")

        line_code = line_start
        bound = bound_start

        idx1 = self.sector_index[(line_code, seg_start)]
        idx2 = self.sector_index[(line_code, seg_end)]

        min_idx = min(idx1, idx2)
        max_idx = max(idx1, idx2)

        occupied_sectors = self.line_sectors[line_code][min_idx : max_idx + 1]

        # Gather all unique stations along these sectors in sequence order
        station_set = set()
        for sec in occupied_sectors:
            station_set.add(sec.from_station_id)
            station_set.add(sec.to_station_id)

        # Sort stations by their line sequence
        all_stations_on_line = self.line_stations[line_code]
        occupied_stations = [s for s in all_stations_on_line if s.station_id in station_set]

        # In official sample, occupancy list is formatted:
        # All PLAT locations first (sorted by station seq), then all SEC locations
        result: List[str] = []
        for s in occupied_stations:
            result.append(f"PLAT:{line_code}:{s.station_id}:{bound}")
        for sec in occupied_sectors:
            from_to = f"{sec.from_station_id}_{sec.to_station_id}"
            result.append(f"SEC:{line_code}:{from_to}:{bound}")

        return result
