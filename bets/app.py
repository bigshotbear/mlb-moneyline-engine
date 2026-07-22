from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from src.best_bets_ui import parlay_card_html, ranked_card_html
from src.config import ensure_directories, get_odds_api_key
from src.live_game import (
    LiveGameError,
    base_state_text,
    fetch_live_game_state,
    inning_text,
    live_watch_label,
)
from src.matchup_dashboard import eye_test_html, matchup_header_html
from src.mlb_data import (
    EASTERN,
    MLBDataError,
    event_date_eastern,
    fetch_all_bullpen_workloads,
    fetch_bullpen_workload,
    fetch_game_lineups,
    fetch_pitcher_season_stats,
    fetch_schedule,
    match_schedule_game,
)
from src.model_status import MODEL_STATUS
from src.odds_client import OddsAPIError, fetch_mlb_moneylines, parse_events
from src.parlay_engine import suggested_parlays
from src.score_ui import all_indicators_rows, matchup_score_html, top_five_html
from src.scoring_engine import evaluate_indicators, score_matchup
from src.slate_engine import build_ranked_entry, rank_slate
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
.block-container {padding-top:.7rem; max-width:1500px;}
.page-nav {margin-bottom:.5rem;}
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
.final-score-card, .top-five-card, .live-card {
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
.reason-green {background:#20b660;}
.reason-red {background:#d64b55;}
.reason-copy strong {display:block; font-size:.9rem;}
.reason-copy > span {display:block; font-size:.76rem; opacity:.67; margin:.12rem 0 .38rem;}
.strength-track {height:5px; background:#303944; border-radius:999px; overflow:hidden;}
.strength-fill {height:100%; border-radius:999px;}
.strength-strong {background:#20b660;}
.strength-medium {background:#e7a92d;}
.strength-light {background:#82909f;}
.strength-number {font-size:1.05rem; font-weight:850; text-align:right;}
.strength-number small {display:block; font-size:.57rem; opacity:.55;}
.context-chip {
    display:inline-block!important; margin-left:.4rem!important;
    padding:.08rem .3rem; border-radius:999px; background:#725b20;
    color:#ffe9a1; font-size:.56rem!important;
}
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
.ranked-bet-card {
    display:grid; grid-template-columns:52px 1fr; gap:.75rem;
    background:#151c24; color:white; border:1px solid #2d3742;
    border-left:5px solid #66717d; border-radius:14px; padding:.9rem;
    margin:.65rem 0;
}
.card-strong {border-left-color:#20b660;}
.card-lean {border-left-color:#4f8fde;}
.card-watch {border-left-color:#e1a62b;}
.card-pass {border-left-color:#7b838e;}
.rank-number {
    width:40px; height:40px; border-radius:50%; background:#27313b;
    display:flex; align-items:center; justify-content:center; font-weight:850;
}
.bet-card-main h3 {margin:.18rem 0 .55rem; font-size:1.05rem;}
.bet-label {font-size:.68rem; letter-spacing:.06em; opacity:.65;}
.bet-score-grid {display:flex; flex-wrap:wrap; gap:.45rem .9rem; font-size:.78rem; opacity:.8;}
.bet-card-main details {margin-top:.65rem;}
.bet-card-main li {font-size:.78rem; margin:.35rem 0; opacity:.82;}
.parlay-grid {display:grid; grid-template-columns:repeat(3,1fr); gap:.8rem;}
.parlay-card {
    background:#151c24; color:white; border:1px solid #2d3742;
    border-radius:14px; padding:.9rem;
}
.parlay-card > div:first-child {display:flex; justify-content:space-between;}
.parlay-name {font-weight:800;}
.parlay-price {font-size:1.15rem; color:#20b660;}
.parlay-leg {display:flex; justify-content:space-between; gap:.5rem; padding:.55rem 0; border-bottom:1px solid #29323c;}
.parlay-leg span {font-size:.7rem; opacity:.65; text-align:right;}
.weakest-leg {font-size:.72rem; opacity:.62; margin-top:.55rem;}
.live-score {
    display:grid; grid-template-columns:1fr 110px 1fr; gap:.6rem;
    align-items:center; text-align:center;
}
.live-team {font-size:1rem; font-weight:750;}
.live-runs {font-size:2.8rem; font-weight:900;}
.live-inning {font-size:.9rem; opacity:.72;}
.live-state-grid {display:grid; grid-template-columns:repeat(4,1fr); gap:.55rem; margin-top:.8rem;}
.live-state-box {background:#222c36; border-radius:10px; padding:.65rem; text-align:center;}
.live-state-box small {display:block; opacity:.55;}
.live-matchup {margin-top:.8rem; padding:.75rem; border-radius:10px; background:#202a34;}
.live-watch {
    margin-top:.8rem; border-radius:12px; padding:.85rem; border:1px solid #3a4652;
}
.tone-green {background:rgba(32,182,96,.16); border-color:#20b660;}
.tone-yellow {background:rgba(225,166,43,.15); border-color:#e1a62b;}
.tone-red {background:rgba(214,75,85,.16); border-color:#d64b55;}
.tone-gray {background:rgba(120,130,143,.13);}
.live-watch strong {display:block; font-size:1rem;}
.live-watch span {display:block; font-size:.78rem; opacity:.75; margin-top:.2rem;}
.base-diamond {font-size:1.15rem; letter-spacing:.2rem;}
@media (max-width:760px) {
    .matchup-header {grid-template-columns:1fr 64px 1fr; padding:.75rem;}
    .match-team h2 {font-size:.98rem;}
    .price {font-size:1rem;}
    .starter {font-size:.76rem;}
    .versus small {font-size:.6rem;}
    .eye-test-grid, .parlay-grid {grid-template-columns:1fr;}
    .eye-columns, .eye-row {font-size:.68rem; grid-template-columns:1.3fr .9fr .9fr .9fr .9fr;}
    .ranked-bet-card {grid-template-columns:42px 1fr;}
    .live-score {grid-template-columns:1fr 72px 1fr;}
    .live-runs {font-size:2.2rem;}
    .live-state-grid {grid-template-columns:1fr 1fr;}
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("⚾ MLB Moneyline Engine")
page = st.radio(
    "Page",
    ["Best Bets", "Matchup Lab", "Live Center", "Parlays"],
    horizontal=True,
    label_visibility="collapsed",
)

api_key = get_odds_api_key()
today_et = datetime.now(EASTERN).date()


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


@st.cache_data(ttl=600, show_spinner=False)
def load_all_bullpens(game_date: date):
    return fetch_all_bullpen_workloads(game_date)


@st.cache_data(ttl=300, show_spinner=False)
def load_bullpen(team_id: int | None, game_date: date):
    return fetch_bullpen_workload(team_id, game_date)


@st.cache_data(ttl=60, show_spinner=False)
def load_lineups(game_pk: int):
    return fetch_game_lineups(game_pk)


@st.cache_data(ttl=8, show_spinner=False)
def load_live_state(game_pk: int):
    return fetch_live_game_state(game_pk)


def odds_payload_or_empty() -> dict[str, Any]:
    if not api_key:
        return {"events": [], "remaining": None, "fetched_at": None}
    try:
        return load_odds(api_key)
    except OddsAPIError as exc:
        st.warning(str(exc))
        return {"events": [], "remaining": None, "fetched_at": None}


def build_full_slate(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not events:
        return []

    dates = sorted({event_date_eastern(event.get("commence_time")) for event in events})
    schedule_by_date: dict[date, list[dict[str, Any]]] = {}
    rankings_by_date: dict[date, dict[str, Any]] = {}
    bullpens_by_date: dict[date, dict[int, dict[str, Any]]] = {}

    for game_date in dates:
        try:
            schedule_by_date[game_date] = load_schedule(game_date)
        except MLBDataError:
            schedule_by_date[game_date] = []
        try:
            rankings_by_date[game_date] = load_rankings(game_date)
        except TeamRankingError:
            rankings_by_date[game_date] = {"windows": {}}
        try:
            bullpens_by_date[game_date] = load_all_bullpens(game_date)
        except MLBDataError:
            bullpens_by_date[game_date] = {}

    entries: list[dict[str, Any]] = []
    for event in events:
        game_date = event_date_eastern(event.get("commence_time"))
        schedule_game = match_schedule_game(
            event,
            schedule_by_date.get(game_date, []),
        )
        if not schedule_game:
            continue

        season = game_date.year
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

        bullpens = bullpens_by_date.get(game_date, {})
        away_bullpen = bullpens.get(
            int(schedule_game.get("away_team_id") or 0),
            {"available": False},
        )
        home_bullpen = bullpens.get(
            int(schedule_game.get("home_team_id") or 0),
            {"available": False},
        )

        entries.append(
            build_ranked_entry(
                event=event,
                schedule_game=schedule_game,
                rankings=rankings_by_date.get(game_date, {"windows": {}}),
                away_pitcher=away_pitcher,
                home_pitcher=home_pitcher,
                away_bullpen=away_bullpen,
                home_bullpen=home_bullpen,
            )
        )

    return rank_slate(entries)


def odds_event_for_schedule(
    schedule_game: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    synthetic = {
        "away_team": schedule_game.get("away_team"),
        "home_team": schedule_game.get("home_team"),
        "commence_time": schedule_game.get("game_date"),
    }
    match = match_schedule_game(synthetic, [
        {
            "away_team": event.get("away_team"),
            "home_team": event.get("home_team"),
            "game_date": event.get("commence_time"),
            "_event": event,
        }
        for event in events
    ])
    return match.get("_event") if match else None


def selected_matchup_data(event: dict[str, Any]) -> dict[str, Any] | None:
    game_date = event_date_eastern(event.get("commence_time"))
    try:
        schedule_game = match_schedule_game(event, load_schedule(game_date))
    except MLBDataError:
        return None
    if not schedule_game:
        return None

    try:
        rankings = load_rankings(game_date)
    except TeamRankingError:
        rankings = {"windows": {}}
    try:
        away_pitcher = load_pitcher_stats(
            schedule_game.get("away_probable_pitcher_id"),
            game_date.year,
        )
    except MLBDataError:
        away_pitcher = {"available": False}
    try:
        home_pitcher = load_pitcher_stats(
            schedule_game.get("home_probable_pitcher_id"),
            game_date.year,
        )
    except MLBDataError:
        home_pitcher = {"available": False}
    try:
        away_bullpen = load_bullpen(schedule_game.get("away_team_id"), game_date)
        home_bullpen = load_bullpen(schedule_game.get("home_team_id"), game_date)
    except MLBDataError:
        away_bullpen = home_bullpen = {"available": False}

    entry = build_ranked_entry(
        event=event,
        schedule_game=schedule_game,
        rankings=rankings,
        away_pitcher=away_pitcher,
        home_pitcher=home_pitcher,
        away_bullpen=away_bullpen,
        home_bullpen=home_bullpen,
    )
    return {
        "entry": entry,
        "event": event,
        "schedule_game": schedule_game,
        "rankings": rankings,
        "away_pitcher": away_pitcher,
        "home_pitcher": home_pitcher,
        "away_bullpen": away_bullpen,
        "home_bullpen": home_bullpen,
    }


if page in ("Best Bets", "Matchup Lab", "Parlays"):
    if not api_key:
        st.error("ODDS_API_KEY is required for odds and slate ranking.")
        st.stop()

    odds_payload = odds_payload_or_empty()
    events = odds_payload["events"]
    if not events:
        st.info("No current MLB moneyline events were returned.")
        st.stop()

if page == "Best Bets":
    st.subheader("Today’s Ranked Moneyline Board")
    st.caption(
        "Every matchup is sorted from strongest to weakest after incomplete scores "
        "are pulled back toward 50."
    )
    with st.spinner("Scoring the complete slate..."):
        ranked_entries = build_full_slate(events)

    top_tab, all_tab = st.tabs(["Top 5", "Full Slate"])
    with top_tab:
        for rank, entry in enumerate(ranked_entries[:5], start=1):
            st.markdown(ranked_card_html(entry, rank), unsafe_allow_html=True)

    with all_tab:
        for rank, entry in enumerate(ranked_entries, start=1):
            st.markdown(ranked_card_html(entry, rank), unsafe_allow_html=True)

elif page == "Parlays":
    st.subheader("Provisional Parlay Builder")
    st.caption(
        "These combinations use adjustable screening rules. They are not guaranteed "
        "or validated parlay recommendations."
    )
    min_score = st.slider("Minimum adjusted matchup score", 52.0, 70.0, 56.0, 0.5)
    min_coverage = st.slider("Minimum data coverage", 10.0, 90.0, 30.0, 5.0)

    with st.spinner("Scoring the complete slate..."):
        ranked_entries = build_full_slate(events)
    parlays = suggested_parlays(
        ranked_entries,
        min_adjusted_score=min_score,
        min_coverage=min_coverage,
    )

    if not parlays:
        st.warning(
            "No responsible provisional parlay is available under the current filters."
        )
    else:
        st.markdown('<div class="parlay-grid">', unsafe_allow_html=True)
        for parlay in parlays:
            st.markdown(parlay_card_html(parlay), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

elif page == "Matchup Lab":
    st.subheader("Single-Matchup Research Lab")
    labels = {
        f"{event['away_team']} at {event['home_team']} — "
        f"{format_game_time_et(event.get('commence_time'))}": event
        for event in events
    }
    selected_label = st.selectbox("Choose game", list(labels))
    event = labels[selected_label]
    data = selected_matchup_data(event)
    if not data:
        st.warning("This matchup could not be connected to MLB's schedule.")
        st.stop()

    entry = data["entry"]
    schedule_game = data["schedule_game"]
    st.markdown(
        matchup_header_html(
            event,
            schedule_game,
            data["away_pitcher"],
            data["home_pitcher"],
        ),
        unsafe_allow_html=True,
    )

    adjusted = {
        **entry["raw_score"],
        "away_score": entry["away_adjusted_score"],
        "home_score": entry["home_adjusted_score"],
        "leader": entry["leader"],
    }
    st.markdown(matchup_score_html(adjusted), unsafe_allow_html=True)

    perspective = st.radio(
        "View reasons for",
        [event["away_team"], event["home_team"]],
        horizontal=True,
    )
    top_tab, eye_tab, full_tab, details_tab = st.tabs(
        ["Top 5", "Eye Test", "All 30", "Game Details"]
    )

    with top_tab:
        st.markdown(
            top_five_html(entry["raw_score"], perspective),
            unsafe_allow_html=True,
        )

    with eye_tab:
        st.markdown(
            eye_test_html(
                event,
                schedule_game,
                data["rankings"],
                data["away_pitcher"],
                data["home_pitcher"],
            ),
            unsafe_allow_html=True,
        )

    with full_tab:
        st.dataframe(
            pd.DataFrame(all_indicators_rows(entry["indicators"], perspective)),
            hide_index=True,
            use_container_width=True,
        )

    with details_tab:
        try:
            lineups = load_lineups(schedule_game["game_pk"])
        except MLBDataError:
            lineups = {
                "away": {"lineup": [], "confirmed": False},
                "home": {"lineup": [], "confirmed": False},
            }

        st.markdown("### Official Lineups")
        c1, c2 = st.columns(2)
        for column, side, name in (
            (c1, "away", event["away_team"]),
            (c2, "home", event["home_team"]),
        ):
            with column:
                st.markdown(f"**{name}**")
                rows = lineups.get(side, {}).get("lineup", [])
                if rows:
                    st.dataframe(
                        pd.DataFrame(rows),
                        hide_index=True,
                        use_container_width=True,
                    )
                else:
                    st.caption("Waiting for official lineup.")

        st.markdown("### Bullpen Workload")
        b1, b2 = st.columns(2)
        for column, name, workload in (
            (b1, event["away_team"], data["away_bullpen"]),
            (b2, event["home_team"], data["home_bullpen"]),
        ):
            with column:
                st.markdown(f"**{name}**")
                summary = workload.get("summary", {})
                m1, m2, m3 = st.columns(3)
                m1.metric("1D", summary.get("pitches_1d", 0))
                m2.metric("2D", summary.get("pitches_2d", 0))
                m3.metric("3D", summary.get("pitches_3d", 0))

        if st.button("Save Timestamped Snapshot", type="primary"):
            payload = {
                "model_status": MODEL_STATUS,
                "event": event,
                "mlb_schedule_match": schedule_game,
                "automated_data": {
                    "lineups": lineups,
                    "away_pitcher": data["away_pitcher"],
                    "home_pitcher": data["home_pitcher"],
                    "away_bullpen": data["away_bullpen"],
                    "home_bullpen": data["home_bullpen"],
                    "indicators": entry["indicators"],
                    "raw_score": entry["raw_score"],
                    "adjusted_scores": {
                        "away": entry["away_adjusted_score"],
                        "home": entry["home_adjusted_score"],
                    },
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

elif page == "Live Center":
    st.subheader("Live Betting Center")
    st.caption(
        "MLB game state refreshes automatically. Live odds refresh only when you press "
        "the button so your Odds API credits are protected."
    )

    try:
        schedule_games = load_schedule(today_et)
    except MLBDataError as exc:
        st.error(str(exc))
        st.stop()

    if not schedule_games:
        st.info("No MLB games are scheduled today.")
        st.stop()

    status_order = {"In Progress": 0, "Warmup": 1, "Scheduled": 2, "Final": 3}
    schedule_games = sorted(
        schedule_games,
        key=lambda game: (
            status_order.get(game.get("status"), 2),
            game.get("game_date") or "",
        ),
    )
    live_labels = {
        f"{game['away_team']} at {game['home_team']} — "
        f"{game.get('status') or 'Scheduled'}": game
        for game in schedule_games
    }
    selected_live_label = st.selectbox("Choose live game", list(live_labels))
    schedule_game = live_labels[selected_live_label]

    current_odds = odds_payload_or_empty()
    odds_event = odds_event_for_schedule(
        schedule_game,
        current_odds.get("events", []),
    )

    if st.button("Refresh live odds"):
        load_odds.clear()
        current_odds = odds_payload_or_empty()
        odds_event = odds_event_for_schedule(
            schedule_game,
            current_odds.get("events", []),
        )

    pregame_entry = None
    if odds_event:
        data = selected_matchup_data(odds_event)
        pregame_entry = data["entry"] if data else None

    @st.fragment(run_every="20s")
    def live_panel() -> None:
        load_live_state.clear()
        try:
            state = load_live_state(int(schedule_game["game_pk"]))
        except LiveGameError as exc:
            st.error(str(exc))
            return

        st.markdown('<div class="live-card">', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="live-score">
              <div>
                <div class="live-team">{state.get('away_team') or schedule_game['away_team']}</div>
                <div class="live-runs">{state.get('away_score', 0)}</div>
              </div>
              <div>
                <div class="live-inning">{inning_text(state)}</div>
                <div>{state.get('outs', 0)} outs</div>
              </div>
              <div>
                <div class="live-team">{state.get('home_team') or schedule_game['home_team']}</div>
                <div class="live-runs">{state.get('home_score', 0)}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        bases = base_state_text(state)
        st.markdown(
            f"""
            <div class="live-state-grid">
              <div class="live-state-box"><small>Count</small>
                {state.get('balls', 0)}-{state.get('strikes', 0)}
              </div>
              <div class="live-state-box"><small>Bases</small>{bases}</div>
              <div class="live-state-box"><small>Batter</small>{state.get('batter') or '—'}</div>
              <div class="live-state-box"><small>Pitcher</small>{state.get('pitcher') or '—'}</div>
            </div>
            <div class="live-matchup">
              <strong>Latest:</strong> {state.get('at_bat_description') or state.get('detailed_state') or 'Waiting for live play data.'}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if pregame_entry:
            watch = live_watch_label(
                state=state,
                pregame_leader=pregame_entry.get("leader"),
                adjusted_leader_score=pregame_entry.get("adjusted_leader_score"),
                coverage=pregame_entry.get("coverage"),
            )
        else:
            watch = live_watch_label(
                state=state,
                pregame_leader=None,
                adjusted_leader_score=None,
                coverage=None,
            )

        st.markdown(
            f"""
            <div class="live-watch tone-{watch['tone']}">
              <strong>{watch['label']}</strong>
              <span>{watch['reason']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        completeness = []
        if state.get("is_live"):
            completeness.extend(["Live score", "Inning/outs", "Count", "Base state"])
        if state.get("batter"):
            completeness.append("Current batter")
        if state.get("pitcher"):
            completeness.append("Current pitcher")
        if state.get("away_lineup_count", 0) >= 9 and state.get("home_lineup_count", 0) >= 9:
            completeness.append("Official lineups")

        if state.get("is_live"):
            st.success(
                "Live feed connected: " + ", ".join(completeness) + "."
            )
        else:
            st.info(state.get("detailed_state") or "Game has not started.")

    live_panel()

    price_col1, price_col2, price_col3 = st.columns(3)
    if odds_event:
        price_col1.metric(
            schedule_game["away_team"],
            f"{odds_event.get('best_away_odds'):+d}"
            if odds_event.get("best_away_odds") is not None else "N/A",
        )
        price_col2.metric(
            schedule_game["home_team"],
            f"{odds_event.get('best_home_odds'):+d}"
            if odds_event.get("best_home_odds") is not None else "N/A",
        )
        price_col3.metric(
            "Books",
            len(odds_event.get("bookmakers", [])),
        )
        st.caption(
            "These are the most recent odds returned when the live-odds button was pressed. "
            "Availability depends on whether sportsbooks are still posting the moneyline."
        )
    else:
        st.warning(
            "No current live moneyline was returned for this game. The MLB live feed "
            "still continues to update the game state."
        )

    if pregame_entry:
        with st.expander("Pregame profile carried into the live game"):
            st.write(pregame_entry["sentence"])
            st.write(
                f"Adjusted score: {pregame_entry['adjusted_leader_score']:.1f} · "
                f"Coverage: {pregame_entry['coverage']:.1f}%"
            )

st.caption(
    "All rankings and live-entry labels are provisional research tools, not "
    "validated win probabilities or guaranteed bets."
)
