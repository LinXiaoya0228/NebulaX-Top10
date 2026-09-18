"""
tests/test_data_parser.py - Unit tests for data parsing, topology, path expansion, and safety footprints.
"""

import pytest
from data_parser import DataMall


@pytest.fixture(scope="module")
def dm():
    return DataMall("PS1/01_data")


def test_network_stations_and_sectors(dm):
    assert len(dm.stations["ALP"]) == 10
    assert len(dm.stations["BET"]) == 10
    assert "ALP" in dm.lines
    assert "BET" in dm.lines
    alp_hubs = [s for s in dm.stations["ALP"] if s.is_interchange]
    assert len(alp_hubs) == 2
    assert {s.station_id for s in alp_hubs} == {"H01", "H02"}


def test_path_expansion_single_sector(dm):
    # Route from S01_S02 to S01_S02 on Line Alpha Eastbound
    locs, tunnels, plats, line, bound, min_seq, max_seq = dm.expand_route(
        "SEC:ALP:S01_S02:EB", "SEC:ALP:S01_S02:EB"
    )
    assert "PLAT:ALP:S01:EB" in locs
    assert "PLAT:ALP:S02:EB" in locs
    assert "SEC:ALP:S01_S02:EB" in locs
    assert len(locs) == 3


def test_path_expansion_multi_sector(dm):
    # Route from S01_S02 to S03_S04 on Line Alpha Eastbound: 3 tunnel sectors + 4 platforms = 7 locations
    locs, tunnels, plats, line, bound, min_seq, max_seq = dm.expand_route(
        "SEC:ALP:S01_S02:EB", "SEC:ALP:S03_S04:EB"
    )
    expected = {
        "PLAT:ALP:S01:EB", "PLAT:ALP:S02:EB", "PLAT:ALP:S03:EB", "PLAT:ALP:S04:EB",
        "SEC:ALP:S01_S02:EB", "SEC:ALP:S02_S03:EB", "SEC:ALP:S03_S04:EB"
    }
    assert locs == expected


def test_path_expansion_westbound(dm):
    # Westbound S07_S08 to S07_S08
    locs, tunnels, plats, line, bound, min_seq, max_seq = dm.expand_route(
        "SEC:ALP:S07_S08:WB", "SEC:ALP:S07_S08:WB"
    )
    expected = {"PLAT:ALP:S08:WB", "PLAT:ALP:S07:WB", "SEC:ALP:S07_S08:WB"}
    assert locs == expected


def test_predecessor_cycle_detection(dm):
    topo_order = dm.detect_predecessor_cycles()
    assert len(topo_order) == len(dm.activities)
    # Check that for all activities with predecessor, predecessor appears before activity
    seen = set()
    for aid in topo_order:
        act = dm.activities[aid]
        if act.predecessor_activity_id:
            assert act.predecessor_activity_id in seen
        seen.add(aid)


def test_safety_footprint_non_live_others(dm):
    # Non-live (Others): no buffers, no mirror, no cross-line
    act_id = "A019"
    act = dm.activities[act_id]
    assert dm.contracts[act.contract_number].nature_of_activity == "Non-live (Others)"
    fp = dm.get_safety_footprint(act_id)
    assert len(fp["buffer_locations"]) == 0
    assert len(fp["mirror_locations"]) == 0
    assert len(fp["cross_line_locations"]) == 0
    assert fp["total_closure"] == fp["work_span"]


def test_safety_footprint_non_live_consist(dm):
    # Non-live (Consist): 1-sector buffer upstream/downstream, no mirror, no cross-line
    act_id = "A001"
    act = dm.activities[act_id]
    assert dm.contracts[act.contract_number].nature_of_activity == "Non-live (Consist)"
    fp = dm.get_safety_footprint(act_id)
    assert len(fp["buffer_locations"]) > 0
    assert len(fp["mirror_locations"]) == 0
    assert len(fp["cross_line_locations"]) == 0
    assert fp["work_span"].issubset(fp["total_closure"])


def test_safety_footprint_live(dm):
    # Live: 2-sector buffer, opposite bound mirroring, H01_H02 cross-line closure
    act_id = "A074"
    act = dm.activities[act_id]
    assert dm.contracts[act.contract_number].nature_of_activity == "Live"
    fp = dm.get_safety_footprint(act_id)
    assert len(fp["buffer_locations"]) > 0
    assert len(fp["mirror_locations"]) > 0
    assert len(fp["cross_line_locations"]) > 0

    # Cross-line must include Betaline H01_H02 sector and platforms
    assert "SEC:BET:H01_H02:EB" in fp["cross_line_locations"]
    assert "SEC:BET:H01_H02:WB" in fp["cross_line_locations"]
    assert "PLAT:BET:H01:EB" in fp["cross_line_locations"]
    assert "PLAT:BET:H02:WB" in fp["cross_line_locations"]

    # Mirror must include opposite bound WB
    assert "SEC:ALP:H01_H02:WB" in fp["mirror_locations"]

