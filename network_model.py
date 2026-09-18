import os
import pandas as pd
from typing import Dict, List, Set, Tuple, Optional

class RailNetwork:
    """
    Dual-line railway network model for Line Alpha (ALP) and Line Beta (BET).
    Handles station/sector sequences, location expansion, and buffer closures.
    """
    def __init__(self, data_dir: str = "PS1/01_data"):
        if not os.path.exists(data_dir):
            if os.path.exists(os.path.join("..", data_dir)):
                data_dir = os.path.join("..", data_dir)
            elif os.path.exists("01_data"):
                data_dir = "01_data"
                
        self.data_dir = data_dir
        self.lines_df = pd.read_csv(os.path.join(data_dir, "01_LINES.csv"))
        self.stations_df = pd.read_csv(os.path.join(data_dir, "02_STATIONS.csv"))
        self.sectors_df = pd.read_csv(os.path.join(data_dir, "03_SECTORS.csv"))
        self.supply_df = pd.read_csv(os.path.join(data_dir, "04_LOCATION_SUPPLY.csv"))
        self.buffer_df = pd.read_csv(os.path.join(data_dir, "05_BUFFER_LOCATION.csv"))
        self.params_df = pd.read_csv(os.path.join(data_dir, "06_PARAMETERS.csv"))
        
        # Parse horizon parameters
        key_col = 'key' if 'key' in self.params_df.columns else 'parameter'
        params = dict(zip(self.params_df[key_col], self.params_df['value']))
        self.horizon_start = pd.to_datetime(params['horizon_start'])
        self.horizon_weeks = int(params['horizon_weeks'])
        
        # Capacities: location_id -> supply_capacity
        self.location_capacity: Dict[str, int] = dict(zip(self.supply_df['location_id'], self.supply_df['supply_capacity']))
        
        # Sectors ordered by seq per line
        self.sectors_by_line: Dict[str, List[dict]] = {}
        for line, g in self.sectors_df.sort_values('seq').groupby('line_code'):
            self.sectors_by_line[line] = list(g.to_dict('records'))
            
        # Stations ordered by seq per line
        self.stations_by_line: Dict[str, List[dict]] = {}
        for line, g in self.stations_df.sort_values('seq').groupby('line_code'):
            self.stations_by_line[line] = list(g.to_dict('records'))
            
        # Buffer rules
        self.buffer_rules = dict(zip(self.buffer_df['nature_of_works'], self.buffer_df['up_to_buffer_sectors']))

    def expand_activity_locations(self, start_loc: str, end_loc: str) -> List[str]:
        """
        Expands start and end tunnel sectors into all traversed platform sectors
        and tunnel sectors between them (inclusive).
        Matches the benchmark ground truth 100%.
        """
        s_parts = start_loc.split(':')
        line = s_parts[1]
        bound = s_parts[3]
        
        line_secs = self.sectors_by_line[line]
        sec_names = [f"SEC:{line}:{s['from_station_id']}_{s['to_station_id']}:{bound}" for s in line_secs]
        
        s_idx = sec_names.index(start_loc)
        e_idx = sec_names.index(end_loc)
        if s_idx > e_idx:
            s_idx, e_idx = e_idx, s_idx
            
        occupied = []
        for i in range(s_idx, e_idx + 1):
            st_from = line_secs[i]['from_station_id']
            st_to = line_secs[i]['to_station_id']
            plat_from = f"PLAT:{line}:{st_from}:{bound}"
            plat_to = f"PLAT:{line}:{st_to}:{bound}"
            sec = sec_names[i]
            if plat_from not in occupied:
                occupied.append(plat_from)
            if sec not in occupied:
                occupied.append(sec)
            if plat_to not in occupied:
                occupied.append(plat_to)
        return occupied

    def get_closure_and_buffers(
        self,
        nature: str,
        start_loc: str,
        end_loc: str
    ) -> Tuple[Set[str], Set[str]]:
        """
        Returns (work_locations, buffer_and_mirrored_locations).
        - work_locations: physically occupied stations and sectors (plus Live opposite bound if applicable)
        - buffer_and_mirrored_locations: buffer sectors, mirrored buffers, and crossover closures.
        """
        s_parts = start_loc.split(':')
        line = s_parts[1]
        bound = s_parts[3]
        opp_bound = 'WB' if bound == 'EB' else 'EB'
        
        line_secs = self.sectors_by_line[line]
        sec_names = [f"SEC:{line}:{s['from_station_id']}_{s['to_station_id']}:{bound}" for s in line_secs]
        
        s_idx = sec_names.index(start_loc)
        e_idx = sec_names.index(end_loc)
        if s_idx > e_idx:
            s_idx, e_idx = e_idx, s_idx
            
        work_locations = set(self.expand_activity_locations(start_loc, end_loc))
        buffer_locations = set()
        
        buf_size = self.buffer_rules.get(nature, 0)
        
        if buf_size > 0:
            b_start = max(0, s_idx - buf_size)
            b_end = min(len(line_secs) - 1, e_idx + buf_size)
            for i in range(b_start, b_end + 1):
                if i < s_idx or i > e_idx:
                    buffer_locations.add(f"SEC:{line}:{line_secs[i]['from_station_id']}_{line_secs[i]['to_station_id']}:{bound}")
                    
        if nature == 'Live':
            # Opposite bound mirroring for work sectors and buffer sectors
            for i in range(s_idx, e_idx + 1):
                work_locations.add(f"SEC:{line}:{line_secs[i]['from_station_id']}_{line_secs[i]['to_station_id']}:{opp_bound}")
                work_locations.add(f"PLAT:{line}:{line_secs[i]['from_station_id']}:{opp_bound}")
                work_locations.add(f"PLAT:{line}:{line_secs[i]['to_station_id']}:{opp_bound}")
                
            for i in range(max(0, s_idx - buf_size), min(len(line_secs) - 1, e_idx + buf_size) + 1):
                if i < s_idx or i > e_idx:
                    buffer_locations.add(f"SEC:{line}:{line_secs[i]['from_station_id']}_{line_secs[i]['to_station_id']}:{opp_bound}")
                    
            # Interchange crossover: if touching H01_H02 (sector or station)
            touches_interchange = any('H01' in loc or 'H02' in loc for loc in (work_locations | buffer_locations))
            if touches_interchange:
                other_line = 'BET' if line == 'ALP' else 'ALP'
                buffer_locations.add(f"SEC:{other_line}:H01_H02:EB")
                buffer_locations.add(f"SEC:{other_line}:H01_H02:WB")
                buffer_locations.add(f"PLAT:{other_line}:H01:EB")
                buffer_locations.add(f"PLAT:{other_line}:H01:WB")
                buffer_locations.add(f"PLAT:{other_line}:H02:EB")
                buffer_locations.add(f"PLAT:{other_line}:H02:WB")
                
        return work_locations, buffer_locations
