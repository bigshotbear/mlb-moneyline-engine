from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.config import ensure_directories, get_odds_api_key
from src.matchup_dashboard import eye_test_html, matchup_header_html
from src.scoring_engine import evaluate_indicators, score_matchup
from src.score_ui import all_indicators_rows, matchup_score_html, top_five_html
from src.mlb_data import (
    MLBDataError,
    event_date_eastern,
    fetch_bullpen_workload,
    fetch_game_lineups,
    fetch_pitcher_season_stats,
    fetch_schedule,
    match_schedule_game,
)
from src.model_status import MODEL_STATUS
from src.odds_client import OddsAPIError, fetch_mlb_moneylines, parse_events
from src.snapshot_store import SnapshotStoreError, save_snapshot
from src.team_rankings import TeamRankingError, fetch_league_rankings
from src.ui_helpers import format_game_time_et

ensure_directories()

st.set_page_config(
    page_title="MLB Moneyline Engine",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
.block-container {padding-top:.8rem; max-width:1450px;}
.matchup-select-label {font-size:.82rem; opacity:.7; margin-bottom:.2rem;}
.matchup-header {
    display:grid; grid-template-columns:1fr 145px 1fr; gap:1rem;
    background:#151c24; color:white; border-radius:16px;
    padding:1rem 1.2rem; align-items:center; border:1px solid #2d3742;
}
.match-team h2 {margin:0; font-size:1.35rem;}
.match-team.right {text-align:right;}
.price {font-size:1.3rem; font-weight:800; margin:.2rem 0;}
.starter {font-weight:650;}
.starter span {display:block; font-size:.8rem; opacity:.65;}
.versus {text-align:center;}
.versus span {
    display:inline-flex; width:44px; height:44px; border-radius:50%;
    align-items:center; justify-content:center; background:#242e39; font-weight:800;
}
.versus small {display:block; margin-top:.45rem; opacity:.68;}
.signal-strip-scroll {overflow-x:auto; width:100%; margin:.75rem 0;}
.top-lights {
    display:flex; gap:.72rem; min-width:max-content;
    background:#151c24; padding:.8rem 1rem; border-radius:14px;
    border:1px solid #2d3742;
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
    display:grid; grid-template-columns:32px 1fr 78px; gap:.65rem;
    align-items:center; padding:.68rem .55rem; border-bottom:1px solid #27313c;
}
.score-row:last-child {border-bottom:none;}
.score-num {
    width:26px; height:26px; border-radius:50%; display:flex;
    align-items:center; justify-content:center; color:white; font-weight:800;
}
.score-copy strong {display:block; font-size:.92rem;}
.score-copy span {display:block; opacity:.68; font-size:.79rem; margin-top:.15rem;}
.supporting-badge {
    display:inline-block!important; margin-left:.4rem!important; padding:.1rem .35rem;
    border-radius:999px; background:#725b20; color:#ffe8a0; font-size:.6rem!important;
}
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
.empty-signals {
    background:#151c24; color:white; border:1px solid #2d3742;
    border-radius:14px; padding:1rem; opacity:.75;
}
@media (max-width:750px) {
    .matchup-header {grid-template-columns:1fr 64px 1fr; padding:.75rem;}
    .match-team h2 {font-size:.98rem;}
    .price {font-size:1rem;}
    .starter {font-size:.76rem;}
    .versus small {font-size:.6rem;}
    .top-light {width:29px; height:29px; font-size:.75rem;}
    .eye-test-grid {grid-template-columns:1fr;}
    .eye-columns, .eye-row {font-size:.68rem; grid-template-columns:1.3fr .9fr .9fr .9fr .9fr;}
}

.final-score-card, .top-five-card {
    background:#151c24; color:white; border:1px solid #2d3742;
    border-radius:16px; padding:1rem; margin:.8rem 0;
}
.score-kicker {font-size:.68rem; letter-spacing:.11em; opacity:.6;}
.score-leader {font-size:1.35rem; font-weight:850; margin:.2rem 0 .75rem;}
.team-score-grid {
    display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:.55rem;
}
.team-score-grid > div {display:flex; justify-content:space-between; align-items:center;}
.team-score-grid > div:last-child {text-align:right;}
.team-score-grid span {font-size:1.45rem; font-weight:900;}
.score-track {height:12px; display:flex; overflow:hidden; border-radius:999px; background:#303844;}
.score-away {background:#d64b55;}
.score-home {background:#20b660;}
.coverage-line {font-size:.78rem; opacity:.72; margin-top:.65rem;}
.score-disclaimer {font-size:.72rem; opacity:.55; margin-top:.2rem;}
.top-reason-row {
    display:grid; grid-template-columns:28px 16px 1fr 54px;
    gap:.55rem; align-items:center; padding:.72rem .2rem;
    border-bottom:1px solid #29323c;
}
.top-reason-row:last-child {border-bottom:none;}
.reason-rank {
    width:25px; height:25px; display:flex; align-items:center; justify-content:center;
    border-radius:50%; background:#27313b; font-weight:800;
}
.reason-dot {width:12px; height:12px; border-radius:50%;}
.reason-green {background:#20b660; box-shadow:0 0 8px rgba(32,182,96,.6);}
.reason-red {background:#d64b55; box-shadow:0 0 8px rgba(214,75,85,.55);}
.reason-copy strong {display:block; font-size:.9rem;}
.reason-copy > span {display:block; font-size:.76rem; opacity:.67; margin:.12rem 0 .38rem;}
.context-chip {
    display:inline-block!important; margin-left:.4rem!important;
    padding:.08rem .3rem; border-radius:999px; background:#725b20;
    color:#ffe9a1; font-size:.56rem!important;
}
.strength-track {height:5px; background:#303944; border-radius:999px; overflow:hidden;}
.strength-fill {height:100%; border-radius:999px;}
.strength-strong {background:#20b660;}
.strength-medium {background:#e7a92d;}
.strength-light {background:#82909f;}
.strength-number {font-size:1.05rem; font-weight:850; text-align:right;}
.strength-number small {display:block; font-size:.57rem; opacity:.55;}
</style>
""",
    unsafe_allow_html=True,
)

st.title("⚾ MLB Moneyline Engine")
st.caption("Active Signals • Eye Test • Current Lean")

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

labels = {
    f"{event['away_team']} at {event['home_team']} — "
    f"{format_game_time_et(event.get('commence_time'))}": event
    for event in events
}

st.markdown("<div class='matchup-select-label'>CHOOSE GAME</div>", unsafe_allow_html=True)
selected_label = st.selectbox(
    "Choose game",
    list(labels.keys()),
    label_visibility="collapsed",
)
event = labels[selected_label]

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
        schedule_game.get("away_probable_pitcher_id"),
        season,
    )
except MLBDataError:
    away_pitcher = {"available": False}

try:
    home_pitcher = load_pitcher_stats(
        schedule_game.get("home_probable_pitcher_id"),
        season,
    )
except MLBDataError:
    home_pitcher = {"available": False}

# Load workload only for the selected game so the main view can include a real
# bullpen-fatigue signal without making every slate load excessively expensive.
try:
    away_bullpen = load_bullpen(schedule_game.get("away_team_id"), game_date)
    home_bullpen = load_bullpen(schedule_game.get("home_team_id"), game_date)
except MLBDataError:
    away_bullpen = {"available": False}
    home_bullpen = {"available": False}

indicators = evaluate_indicators(
    event=event,
    schedule_game=schedule_game,
    rankings=rankings,
    away_pitcher=away_pitcher,
    home_pitcher=home_pitcher,
    away_bullpen_workload=away_bullpen,
    home_bullpen_workload=home_bullpen,
)

matchup_score = score_matchup(
    indicators,
    event["away_team"],
    event["home_team"],
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

score_team = st.radio(
    "View reasons for",
    [event["away_team"], event["home_team"]],
    horizontal=True,
)

st.markdown(matchup_score_html(matchup_score), unsafe_allow_html=True)

score_tab, eye_tab, winner_tab, details_tab = st.tabs(
    ["Top 5", "Eye Test", "Full Score", "Game Details"]
)

with score_tab:
    st.markdown(top_five_html(matchup_score, score_team), unsafe_allow_html=True)
    st.caption(
        "Only the five strongest active reasons are shown. Red supports the opponent."
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
    st.markdown(matchup_score_html(matchup_score), unsafe_allow_html=True)
    st.markdown("### Family Contribution Caps")
    family_rows = []
    for family, values in matchup_score["families"].items():
        family_rows.append(
            {
                "Family": family.replace("_", " ").title(),
                event["away_team"]: round(values["away"], 2),
                event["home_team"]: round(values["home"], 2),
                "Cap": values["cap"],
            }
        )
    st.dataframe(
        pd.DataFrame(family_rows),
        hide_index=True,
        use_container_width=True,
    )

    with st.expander("View all 30 indicators"):
        st.dataframe(
            pd.DataFrame(all_indicators_rows(indicators, score_team)),
            hide_index=True,
            use_container_width=True,
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
        (b1, event["away_team"], away_bullpen),
        (b2, event["home_team"], home_bullpen),
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
                    st.dataframe(
                        pd.DataFrame(rows),
                        hide_index=True,
                        use_container_width=True,
                    )
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
                "away_bullpen": away_bullpen,
                "home_bullpen": home_bullpen,
                "indicators": indicators,
                "matchup_score": matchup_score,
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
    "The score is relative weighted support, not a validated win probability. "
    "Unavailable indicators reduce data coverage and stay out of the Top 5."
)
