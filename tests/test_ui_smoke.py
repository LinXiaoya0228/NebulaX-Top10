"""
tests/test_ui_smoke.py - Automated smoke tests for UI theme, components, and chart builders.
"""

import os
import pandas as pd
import pytest

from data_parser import DataMall
from ui.theme import CLOSURE_THEME, LINE_THEME, STATUS_THEME, SURFACES
from ui.components import render_bound_badge, render_eclo_badge, render_line_badge
from ui.charts import (
    build_access_schedule_chart,
    build_capacity_heatmap,
    build_contract_completion_chart,
    build_contract_gantt_chart,
    build_topology_schematic,
)
from app import create_submission_zip, get_default_data_dir


@pytest.fixture(scope="module")
def dm():
    return DataMall(get_default_data_dir())


def test_theme_tokens():
    assert "bg_app" in SURFACES
    assert "ALP" in LINE_THEME
    assert "BET" in LINE_THEME
    assert "text_tag" in LINE_THEME["ALP"]
    assert "FEASIBLE" in STATUS_THEME
    assert "direct" in CLOSURE_THEME


def test_component_badges():
    alp_badge = render_line_badge("ALP")
    assert "[ALP]" in alp_badge
    assert "Alpha Line" in alp_badge

    bet_badge = render_line_badge("BET")
    assert "[BET]" in bet_badge
    assert "Beta Line" in bet_badge

    eb_badge = render_bound_badge("EB")
    assert "Eastbound" in eb_badge

    eclo_badge = render_eclo_badge()
    assert "ECLO" in eclo_badge


def test_access_schedule_chart(dm):
    acc_df = pd.read_csv("results/scenario_A/SCHEDULE_ACCESS.csv")
    fig_cont = build_access_schedule_chart(
        access_df=acc_df,
        dm=dm,
        scenario_label="Scenario A",
        line_filter="All",
        nature_filter="All",
        eclo_only=False,
        view_mode="continuous",
    )
    assert fig_cont is not None
    assert len(fig_cont.data) >= 1

    fig_disc = build_access_schedule_chart(
        access_df=acc_df,
        dm=dm,
        scenario_label="Scenario A",
        line_filter="All",
        nature_filter="All",
        eclo_only=False,
        view_mode="discrete",
    )
    assert fig_disc is not None
    assert len(fig_disc.data) >= 1


def test_contract_gantt_chart(dm):
    acc_df = pd.read_csv("results/scenario_A/SCHEDULE_ACCESS.csv")
    res_df = pd.read_csv("results/scenario_A/RESULTS.csv")
    fig = build_contract_gantt_chart(
        access_df=acc_df,
        results_df=res_df,
        dm=dm,
        scenario_label="Scenario A",
    )
    assert fig is not None
    assert len(fig.data) >= 2


def test_contract_completion_chart(dm):
    res_df = pd.read_csv("results/scenario_A/RESULTS.csv")
    fig = build_contract_completion_chart(
        results_df=res_df,
        dm=dm,
        scenario_label="Scenario A",
    )
    assert fig is not None
    assert len(fig.data) >= 2


def test_capacity_heatmap(dm):
    occ_df = pd.read_csv("results/scenario_A/SCHEDULE_OCCUPANCY.csv")
    fig, heat_df = build_capacity_heatmap(
        occ_df=occ_df,
        dm=dm,
        scenario_label="Scenario A",
        metric_choice="Capacity Utilisation (%)",
        display_mode="Capacity Hotspots (Top 20)",
    )
    assert fig is not None
    assert not heat_df.empty
    assert "utilisation" in heat_df.columns


def test_topology_schematic(dm):
    fig_alp = build_topology_schematic(dm, active_activity_id="A001", line_code="ALP")
    assert fig_alp is not None
    fig_bet = build_topology_schematic(dm, active_activity_id="A036", line_code="BET")
    assert fig_bet is not None


def test_submission_zip_creation():
    zip_bytes = create_submission_zip("results/scenario_A", "A")
    assert len(zip_bytes) > 0

