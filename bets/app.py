from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import ensure_directories, get_odds_api_key
from src.matchup_dashboard import (
    build_signal_map,
    eye_test_html,
    indicator_lights_html,
    matchup_header_html,
    scorecard_html,
    who_wins_html,
)
from src.mlb_data import (
    MLBDataError,
    event_date_eastern,
    fetch_bullpen_workload,
    fetch_game_lineups,
    fetch_pitcher_season_stats,
    fetch_schedule,
    match_schedule_game,
)
from src.model_status import MODEL_STATUS, SIGNAL_FAMILIES
from src.odds_client import OddsAPIError, fetch_mlb_moneylines, parse_events
from src.snapshot_store import (
    SnapshotStoreError,
    list_snapshots,
    save_snapshot,
    supabase_enabled,
)
from src.team_rankings import TeamRankingError, fetch_league_rankings
from src.ui_helpers import format_game_time_et

ensure_directories()

st.set_page_config(
    page_title="MLB Moneyline Engine",
    page_icon="⚾",
    layout="wide",
)

st.markdown(
    """
<style>
.block-container {padding-top: 1rem; max-width: 1500px;}
[data-testid="stSidebar"] {background:#111820;}
[data-testid="stSidebar"] * {color:#f4f6f8;}
.matchup-header {
    display:grid; grid-template-columns:1fr 150px 1fr; gap:1rem;
    background:#151c24; color:white; border-radius:16px;
    padding:1rem 1.2rem; align-items:center; border:1px solid #2d3742;
}
.match-team h2 {margin:0; font-size:1.45rem;}
.match-team.right {text-align:right;}
.price {font-size:1.35rem; font-weight:800; margin:.2rem 0;}
.starter {font-weight:650; opacity:.95;}
.starter span {display:block; font-size:.8rem; opacity:.65;}
.versus {text-align:center;}
.versus span {
    display:inline-flex; width:44px; height:44px; border-radius:50%;
    align-items:center; justify-content:center; background:#242e39; font-weight:800;
}
.versus small {display:block; margin-top:.45rem; opacity:.68;}
.top-lights {
    display:grid; grid-template-columns:repeat(7,1fr); gap:.7rem;
    background:#151c24; padding:.8rem 1rem; border-radius:14px;
    margin:.75rem 0; border:1px solid #2d3742;
}
.top-light-wrap {position:relative; text-align:center;}
.top-light-wrap summary {list-style:none;}
.top-light-wrap summary::-webkit-details-marker {display:none;}
.top-light {
    width:34px; height:34px; border-radius:50%; display:inline-flex;
    align-items:center; justify-content:center; color:white; font-weight:800;
    cursor:pointer; border:2px solid rgba(255,255,255,.55);
}
.light-green {background:#1fb760; box-shadow:0 0 12px rgba(31,183,96,.65);}
.light-red {background:#df4b56; box-shadow:0 0 12px rgba(223,75,86,.55);}
.light-gray {background:#7a828e;}
.top-light-tip {
    display:none; position:absolute; z-index:20; width:250px;
    left:50%; transform:translateX(-50%); top:42px;
    padding:.65rem; border-radius:10px; background:#0c1218; color:white;
    text-align:left; font-size:.78rem; box-shadow:0 10px 28px rgba(0,0,0,.4);
}
.top-light-wrap:hover .top-light-tip,
.top-light-wrap[open] .top-light-tip {display:block;}
.scorecard {
    background:#151c24; border:1px solid #2d3742; border-radius:14px;
    padding:.55rem; color:white;
}
.score-row {
    display:grid; grid-template-columns:32px 1fr 82px; gap:.65rem;
    align-items:center; padding:.7rem .55rem; border-bottom:1px solid #27313c;
}
.score-row:last-child {border-bottom:none;}
.score-num {
    width:26px; height:26px; border-radius:50%; display:flex;
    align-items:center; justify-content:center; color:white; font-weight:800;
}
.score-copy strong {display:block; font-size:.92rem;}
.score-copy span {display:block; opacity:.68; font-size:.8rem; margin-top:.15rem;}
.score-status {
    justify-self:end; border-radius:999px; padding:.2rem .55rem;
    font-size:.72rem; font-weight:800; color:white;
}
.status-green {background:#1f9d55;}
.status-red {background:#ce3c46;}
.status-gray {background:#6f7782;}
.eye-test-grid {display:grid; grid-template-columns:1fr 1fr; gap:1rem;}
.eye-team {
    background:#151c24; color:white; border:1px solid #2d3742;
    border-radius:14px; padding:.9rem;
}
.eye-team-head {display:flex; justify-content:space-between; font-size:1.05rem;}
.eye-pitcher {opacity:.72; font-size:.82rem; margin:.25rem 0 .75rem;}
.eye-columns, .eye-row {
    display:grid; grid-template-columns:1.45fr 1fr 1fr 1fr 1fr; gap:.35rem;
    align-items:center; padding:.45rem 0; font-size:.78rem;
}
.eye-columns {opacity:.58; border-bottom:1px solid #2d3742;}
.eye-row {border-bottom:1px solid #27313c;}
.eye-label {font-weight:750;}
.winner-panel {
    display:grid; grid-template-columns:56px 1fr; gap:1rem; align-items:center;
    background:#151c24; border:1px solid #2d3742; border-radius:14px;
    padding:1.1rem; color:white;
}
.winner-light {width:48px; height:48px; border-radius:50%;}
.winner-panel h3 {margin:0 0 .25rem;}
.winner-panel p {margin:.15rem 0; opacity:.78;}
.winner-warning {font-size:.78rem;}
.winner-rows {display:grid; grid-template-columns:1fr 1fr; gap:.8rem; margin-top:.8rem;}
.winner-rows > div {
    display:flex; justify-content:space-between; align-items:center;
    background:#151c24; border:1px solid #2d3742; border-radius:12px;
    padding:.8rem; color:white;
}
.winner-rows span {padding:.25rem .55rem; border-radius:999px; color:white; font-size:.76rem;}
@media (max-width:750px) {
    .matchup-header {grid-template-columns:1fr 70px 1fr; padding:.8rem;}
    .match-team h2 {font-size:1rem;}
    .price {font-size:1rem;}
    .starter {font-size:.78rem;}
    .versus small {font-size:.62rem;}
    .top-lights {gap:.3rem; padding:.65rem .35rem;}
    .top-light {width:28px; height:28px; font-size:.76rem;}
    .eye-test-grid {grid-template-columns:1fr;}
    .eye-columns, .eye-row {font-size:.7rem; grid-template-columns:1.3fr .9fr .9fr .9fr .9fr;}
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("⚾ MLB Moneyline Engine")
st.caption("Scorecard • Eye Test • Current Lean")

api_key = get_odds_api_key()


@st.cache_data(ttl=300, show_spinner=False)
def load_odds(key: str):
    response = fetch_mlb_moneylines(key)
    return {
        "events": parse_events(response.events),
        "remaining": response.remaining_requests,
        "fetched_at": response.fetched_at_utc,
    }


@st.cache_data(ttl=900, show_spinner=False)
def load_schedule(game_date: date):
    return fetch_schedule(game_date)


@st.cache_data(ttl=3600, show_spinner=False)
def load_rankings(game_date: date):
    return fetch_league_rankings(game_date)


@st.cache_data(ttl=3600, show_spinner=False)
def load_pitcher_stats(person_id: int | None, season: int):
    return fetch_pitcher_season_stats(person_id, season)


@st.cache_data(ttl=60, show_spinner=False)
def load_lineups(game_pk: int):
    return fetch_game_lineups(game_pk)


@st.cache_data(ttl=300, show_spinner=False)
def load_bullpen(team_id: int | None, game_date: date):
    return fetch_bullpen_workload(team_id, game_date)


if not api_key:
    st.error("ODDS_API_KEY is missing in Render Environment.")
    st.stop()

try:
    odds_payload = load_odds(api_key)
    events = odds_payload["events"]
except OddsAPIError as exc:
    st.error(str(exc))
    st.stop()

if not events:
    st.info("No MLB games are currently available.")
    st.stop()

# Sidebar slate.
st.sidebar.markdown("## MLB Slate")
sidebar_labels = {}
for event in events:
    label = (
        f"{event['away_team']} @ {event['home_team']}\n"
        f"{format_game_time_et(event.get('commence_time'))}"
    )
    sidebar_labels[label] = event

selected_label = st.sidebar.radio(
    "Today's MLB",
    list(sidebar_labels.keys()),
    label_visibility="collapsed",
)
event = sidebar_labels[selected_label]
game_date = event_date_eastern(event.get("commence_time"))
season = game_date.year

try:
    schedule_game = match_schedule_game(event, load_schedule(game_date))
except MLBDataError as exc:
    st.error(str(exc))
    st.stop()

if not schedule_game:
    st.warning("Could not match this game to MLB's schedule.")
    st.stop()

try:
    rankings = load_rankings(game_date)
except TeamRankingError:
    rankings = {"windows": {}}

try:
    away_pitcher = load_pitcher_stats(
        schedule_game.get("away_probable_pitcher_id"), season
    )
except MLBDataError:
    away_pitcher = {"available": False}

try:
    home_pitcher = load_pitcher_stats(
        schedule_game.get("home_probable_pitcher_id"), season
    )
except MLBDataError:
    home_pitcher = {"available": False}

signal_map = build_signal_map(
    event,
    schedule_game,
    rankings,
    away_pitcher,
    home_pitcher,
)

st.markdown(
    matchup_header_html(
        event,
        schedule_game,
        away_pitcher,
        home_pitcher,
    ),
    unsafe_allow_html=True,
)

# Top light row uses the current market favorite as the row perspective.
away_market = event.get("consensus_away_no_vig") or 0
home_market = event.get("consensus_home_no_vig") or 0
perspective_team = (
    event["away_team"] if away_market >= home_market else event["home_team"]
)

st.markdown(
    indicator_lights_html(signal_map, perspective_team),
    unsafe_allow_html=True,
)

score_tab, eye_tab, winner_tab, details_tab = st.tabs(
    ["Scorecard", "Eye Test", "Who Wins", "Game Details"]
)

with score_tab:
    selected_score_team = st.radio(
        "Scorecard perspective",
        [event["away_team"], event["home_team"]],
        horizontal=True,
    )
    st.markdown(
        scorecard_html(signal_map, selected_score_team),
        unsafe_allow_html=True,
    )

with eye_tab:
    st.markdown(
        eye_test_html(
            event,
            schedule_game,
            rankings,
            away_pitcher,
            home_pitcher,
        ),
        unsafe_allow_html=True,
    )

with winner_tab:
    st.markdown(
        who_wins_html(event, signal_map),
        unsafe_allow_html=True,
    )

with details_tab:
    refresh = st.button("Refresh lineup and bullpen data")
    if refresh:
        load_lineups.clear()
        load_bullpen.clear()

    try:
        lineups = load_lineups(schedule_game["game_pk"])
    except MLBDataError as exc:
        st.warning(str(exc))
        lineups = {
            "away": {"confirmed": False, "lineup": []},
            "home": {"confirmed": False, "lineup": []},
        }

    try:
        away_bp = load_bullpen(schedule_game.get("away_team_id"), game_date)
        home_bp = load_bullpen(schedule_game.get("home_team_id"), game_date)
    except MLBDataError as exc:
        st.warning(str(exc))
        away_bp = {"available": False}
        home_bp = {"available": False}

    st.markdown("### Official Lineups")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**{event['away_team']}**")
        rows = lineups.get("away", {}).get("lineup", [])
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.caption("Waiting for official lineup.")
    with c2:
        st.markdown(f"**{event['home_team']}**")
        rows = lineups.get("home", {}).get("lineup", [])
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.caption("Waiting for official lineup.")

    st.markdown("### Bullpen Workload")
    b1, b2 = st.columns(2)
    for col, team_name, workload in [
        (b1, event["away_team"], away_bp),
        (b2, event["home_team"], home_bp),
    ]:
        with col:
            st.markdown(f"**{team_name}**")
            if workload.get("available"):
                summary = workload.get("summary", {})
                m1, m2, m3 = st.columns(3)
                m1.metric("1D", summary.get("pitches_1d", 0))
                m2.metric("2D", summary.get("pitches_2d", 0))
                m3.metric("3D", summary.get("pitches_3d", 0))
                rows = workload.get("relievers", [])
                if rows:
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            else:
                st.caption("Unavailable.")

    with st.expander("Bookmaker Prices"):
        st.dataframe(
            pd.DataFrame(event.get("bookmakers", [])),
            hide_index=True,
            use_container_width=True,
        )

    if st.button("Save Timestamped Snapshot", type="primary"):
        payload = {
            "model_status": MODEL_STATUS,
            "event": event,
            "mlb_schedule_match": schedule_game,
            "automated_data": {
                "lineups": lineups,
                "away_pitcher": away_pitcher,
                "home_pitcher": home_pitcher,
                "away_bullpen": away_bp,
                "home_bullpen": home_bp,
                "signal_map": signal_map,
            },
        }
        try:
            result = save_snapshot(
                f"{event['away_team']} at {event['home_team']}",
                payload,
            )
            st.success(f"Saved to {result['source']}: {result['identifier']}")
        except SnapshotStoreError as exc:
            st.error(str(exc))

st.caption(
    "Green supports the selected team, red supports the opponent, and gray is pending or neutral. "
    "Current Lean is not a trained win probability."
)
