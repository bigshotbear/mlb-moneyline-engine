from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.config import ensure_directories, get_odds_api_key
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
from src.team_rankings import (
    TeamRankingError,
    comparative_lean,
    fetch_league_rankings,
    team_profile,
    trend_label,
)
from src.ui_helpers import format_game_time_et, format_moneyline, rank_text

ensure_directories()

st.set_page_config(
    page_title="MLB Moneyline Engine",
    page_icon="⚾",
    layout="wide",
)

st.markdown(
    """
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 4rem; max-width: 1500px;}
[data-testid="stMetricValue"] {font-size: 1.65rem;}
.game-title {font-size: 1.35rem; font-weight: 800; margin-bottom: .15rem;}
.team-title {font-size: 1.15rem; font-weight: 800;}
.subtle {opacity: .72; font-size: .9rem;}
.rank-row {padding: .28rem 0; border-bottom: 1px solid rgba(128,128,128,.18);}
.status-pill {display:inline-block; padding:.18rem .55rem; border-radius:999px; background:#20262f;}
</style>
""",
    unsafe_allow_html=True,
)

st.title("⚾ MLB Moneyline Engine")
st.caption("Fast eye test + deeper indicator tracker • MLB moneyline only")
st.info(
    f"**{MODEL_STATUS['stage']}** — {MODEL_STATUS['reason']}",
    icon="🧭",
)

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
def load_bullpen(team_id: int | None, as_of_date: date):
    return fetch_bullpen_workload(team_id, as_of_date)


def rank_grid(profile: dict[str, Any]) -> None:
    header = st.columns([1.45, 1, 1, 1, 1.1])
    header[0].caption("Category")
    header[1].caption("Season")
    header[2].caption("30 Days")
    header[3].caption("7 Days")
    header[4].caption("Trend")

    rows = (
        ("Batting", "batting"),
        ("Starting pitching", "starting_pitching"),
        ("Bullpen", "bullpen"),
    )

    for label, key in rows:
        cols = st.columns([1.45, 1, 1, 1, 1.1])
        cols[0].markdown(f"**{label}**")
        cols[1].write(rank_text(profile.get(key, {}).get("season", {})))
        cols[2].write(rank_text(profile.get(key, {}).get("month", {})))
        cols[3].write(rank_text(profile.get(key, {}).get("week", {})))
        cols[4].write(trend_label(profile.get(key, {})))


def pitcher_summary(
    team_name: str,
    moneyline: int | None,
    pitcher_name: str | None,
    pitcher_stats: dict[str, Any],
) -> None:
    st.markdown(f"<div class='team-title'>{team_name}</div>", unsafe_allow_html=True)
    price_col, pitcher_col = st.columns([0.7, 2.3])
    price_col.metric("Moneyline", format_moneyline(moneyline))
    record = pitcher_stats.get("record") if pitcher_stats.get("available") else None
    era = pitcher_stats.get("era") if pitcher_stats.get("available") else None
    pitcher_col.markdown(
        f"**SP: {pitcher_name or 'TBD'}**  \n"
        f"Record: **{record or 'N/A'}**"
        + (f" • ERA: **{era}**" if era else "")
    )


def basic_game_card(
    event: dict[str, Any],
    schedule_game: dict[str, Any] | None,
    rankings: dict[str, Any],
    pitcher_stats_cache: dict[tuple[int | None, int], dict[str, Any]],
) -> None:
    with st.container(border=True):
        time_text = format_game_time_et(event.get("commence_time"))
        st.markdown(
            f"<div class='game-title'>{event['away_team']} at {event['home_team']}</div>"
            f"<div class='subtle'>{time_text}</div>",
            unsafe_allow_html=True,
        )

        if not schedule_game:
            st.warning("MLB schedule match is still loading for this game.")
            return

        season = event_date_eastern(event.get("commence_time")).year
        away_pitcher_key = (schedule_game.get("away_probable_pitcher_id"), season)
        home_pitcher_key = (schedule_game.get("home_probable_pitcher_id"), season)

        away_pitcher = pitcher_stats_cache.get(
            away_pitcher_key,
            {"available": False},
        )
        home_pitcher = pitcher_stats_cache.get(
            home_pitcher_key,
            {"available": False},
        )

        away_profile = team_profile(rankings, schedule_game.get("away_team_id"))
        home_profile = team_profile(rankings, schedule_game.get("home_team_id"))

        away_col, home_col = st.columns(2, gap="large")
        with away_col:
            pitcher_summary(
                event["away_team"],
                event.get("best_away_odds"),
                schedule_game.get("away_probable_pitcher"),
                away_pitcher,
            )
            rank_grid(away_profile)

        with home_col:
            pitcher_summary(
                event["home_team"],
                event.get("best_home_odds"),
                schedule_game.get("home_probable_pitcher"),
                home_pitcher,
            )
            rank_grid(home_profile)

        confirmed_text = "Check game details for lineup status"
        st.caption(
            f"Market baseline: {event.get('consensus_away_no_vig', 0):.1%} "
            f"{event['away_team']} / {event.get('consensus_home_no_vig', 0):.1%} "
            f"{event['home_team']} • {confirmed_text}"
        )


def indicator_row(
    number: int,
    label: str,
    status: str,
    explanation: str,
) -> None:
    cols = st.columns([0.45, 2.2, 1.5, 4.2])
    cols[0].markdown(f"**{number}**")
    cols[1].markdown(f"**{label}**")
    cols[2].write(status)
    cols[3].caption(explanation)


def indicators_game_card(
    event: dict[str, Any],
    schedule_game: dict[str, Any] | None,
    rankings: dict[str, Any],
    pitcher_stats_cache: dict[tuple[int | None, int], dict[str, Any]],
) -> None:
    with st.container(border=True):
        st.markdown(
            f"<div class='game-title'>{event['away_team']} at {event['home_team']}</div>"
            f"<div class='subtle'>{format_game_time_et(event.get('commence_time'))}</div>",
            unsafe_allow_html=True,
        )

        if not schedule_game:
            st.warning("Schedule data unavailable.")
            return

        season = event_date_eastern(event.get("commence_time")).year
        away_pitcher = pitcher_stats_cache.get(
            (schedule_game.get("away_probable_pitcher_id"), season),
            {"available": False},
        )
        home_pitcher = pitcher_stats_cache.get(
            (schedule_game.get("home_probable_pitcher_id"), season),
            {"available": False},
        )
        away_profile = team_profile(rankings, schedule_game.get("away_team_id"))
        home_profile = team_profile(rankings, schedule_game.get("home_team_id"))

        starter_lean = comparative_lean(
            away_profile.get("starting_pitching", {}),
            home_profile.get("starting_pitching", {}),
            event["away_team"],
            event["home_team"],
        )
        batting_lean = comparative_lean(
            away_profile.get("batting", {}),
            home_profile.get("batting", {}),
            event["away_team"],
            event["home_team"],
        )
        bullpen_lean = comparative_lean(
            away_profile.get("bullpen", {}),
            home_profile.get("bullpen", {}),
            event["away_team"],
            event["home_team"],
        )

        away_sp_record = away_pitcher.get("record") or "N/A"
        home_sp_record = home_pitcher.get("record") or "N/A"

        indicator_row(
            1,
            "Starting-pitcher projection",
            starter_lean["label"],
            (
                f"{schedule_game.get('away_probable_pitcher') or 'TBD'} "
                f"({away_sp_record}) vs "
                f"{schedule_game.get('home_probable_pitcher') or 'TBD'} "
                f"({home_sp_record}); uses team SP ranks as an eye-test direction."
            ),
        )
        indicator_row(
            2,
            "Starter vs confirmed lineup",
            "Waiting / detailed view",
            "Requires official lineups and the advanced pitch-mix matchup layer.",
        )
        indicator_row(
            3,
            "Lineup strength",
            batting_lean["label"],
            "Compares batting ranks across season, last 30 days, and last 7 days.",
        )
        indicator_row(
            4,
            "Bullpen asymmetry",
            bullpen_lean["label"],
            "Performance rank is shown here; recent workload is loaded in game details.",
        )
        indicator_row(
            5,
            "Hidden runs",
            "Not scored yet",
            "Catcher framing, blocking, throwing, and baserunning remain a later data layer.",
        )
        indicator_row(
            6,
            "Batted-ball defense",
            "Not scored yet",
            "Will require Statcast contact profile and position-specific OAA.",
        )
        indicator_row(
            7,
            "Situational context",
            f"Home: {event['home_team']}",
            "Home field is visible, but travel, rest, injuries, and park fit are not yet scored.",
        )

        st.warning(
            "These are preliminary supporting directions, not validated indicator hits "
            "or a betting recommendation."
        )


def load_daily_context(events: list[dict[str, Any]]):
    if not events:
        return {}, {}, {}

    dates = {event_date_eastern(event.get("commence_time")) for event in events}
    schedule_by_date: dict[date, list[dict[str, Any]]] = {}
    rankings_by_date: dict[date, dict[str, Any]] = {}

    for game_date in dates:
        try:
            schedule_by_date[game_date] = load_schedule(game_date)
        except MLBDataError:
            schedule_by_date[game_date] = []

        try:
            rankings_by_date[game_date] = load_rankings(game_date)
        except TeamRankingError:
            rankings_by_date[game_date] = {"windows": {}, "warnings": ["Rankings unavailable."]}

    matched: dict[str, dict[str, Any] | None] = {}
    pitcher_keys: set[tuple[int | None, int]] = set()

    for event in events:
        game_date = event_date_eastern(event.get("commence_time"))
        schedule_game = match_schedule_game(event, schedule_by_date.get(game_date, []))
        matched[event.get("event_id") or event["commence_time"]] = schedule_game

        if schedule_game:
            pitcher_keys.add((schedule_game.get("away_probable_pitcher_id"), game_date.year))
            pitcher_keys.add((schedule_game.get("home_probable_pitcher_id"), game_date.year))

    pitcher_stats_cache: dict[tuple[int | None, int], dict[str, Any]] = {}
    for person_id, season in pitcher_keys:
        try:
            pitcher_stats_cache[(person_id, season)] = load_pitcher_stats(person_id, season)
        except MLBDataError:
            pitcher_stats_cache[(person_id, season)] = {"available": False}

    return matched, rankings_by_date, pitcher_stats_cache


tabs = st.tabs(
    [
        "Matchups",
        "Game Details",
        "Saved Snapshots",
        "Model Notes",
        "Setup",
    ]
)

with tabs[0]:
    top_a, top_b = st.columns([3, 1])
    with top_a:
        view_mode = st.radio(
            "Choose your view",
            ["Basic / Eye Test", "Indicators"],
            horizontal=True,
        )
    with top_b:
        refresh_clicked = st.button("Refresh odds", type="primary", use_container_width=True)

    if not api_key:
        st.warning("Add ODDS_API_KEY in Render Environment.")
        events = []
        odds_payload = None
    else:
        if refresh_clicked:
            load_odds.clear()
            load_schedule.clear()
            load_rankings.clear()
            load_pitcher_stats.clear()

        try:
            odds_payload = load_odds(api_key)
            events = odds_payload["events"]
            st.caption(
                f"Odds updated {format_game_time_et(odds_payload['fetched_at'])} • "
                f"Credits remaining: {odds_payload['remaining'] or 'unknown'}"
            )
        except OddsAPIError as exc:
            st.error(str(exc))
            events = []
            odds_payload = None

    if events:
        with st.spinner("Loading starters and team rankings..."):
            matched_games, rankings_by_date, pitcher_cache = load_daily_context(events)

        for event in events:
            event_key = event.get("event_id") or event["commence_time"]
            schedule_game = matched_games.get(event_key)
            game_date = event_date_eastern(event.get("commence_time"))
            rankings = rankings_by_date.get(game_date, {"windows": {}})

            if view_mode == "Basic / Eye Test":
                basic_game_card(event, schedule_game, rankings, pitcher_cache)
            else:
                indicators_game_card(event, schedule_game, rankings, pitcher_cache)
    elif api_key:
        st.info("No MLB games are currently available.")

with tabs[1]:
    st.subheader("Detailed Game View")

    if not api_key:
        st.warning("Add ODDS_API_KEY first.")
    else:
        try:
            detail_events = load_odds(api_key)["events"]
        except OddsAPIError as exc:
            st.error(str(exc))
            detail_events = []

        if detail_events:
            detail_labels = {
                f"{event['away_team']} at {event['home_team']} — "
                f"{format_game_time_et(event.get('commence_time'))}": event
                for event in detail_events
            }
            selected_label = st.selectbox("Choose matchup", list(detail_labels))
            event = detail_labels[selected_label]
            game_date = event_date_eastern(event.get("commence_time"))

            try:
                schedule_game = match_schedule_game(
                    event,
                    load_schedule(game_date),
                )
            except MLBDataError as exc:
                st.error(str(exc))
                schedule_game = None

            if schedule_game:
                st.markdown(
                    f"## {event['away_team']} at {event['home_team']}\n"
                    f"**{format_game_time_et(event.get('commence_time'))}**"
                )

                refresh_detail = st.button("Refresh lineup and bullpen data")
                if refresh_detail:
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
                    away_bullpen = load_bullpen(
                        schedule_game.get("away_team_id"),
                        game_date,
                    )
                    home_bullpen = load_bullpen(
                        schedule_game.get("home_team_id"),
                        game_date,
                    )
                except MLBDataError as exc:
                    st.warning(str(exc))
                    away_bullpen = {"available": False}
                    home_bullpen = {"available": False}

                st.markdown("### Official lineups")
                line_a, line_h = st.columns(2)
                with line_a:
                    st.markdown(f"**{event['away_team']}**")
                    away_rows = lineups.get("away", {}).get("lineup", [])
                    if away_rows:
                        st.dataframe(pd.DataFrame(away_rows), hide_index=True, use_container_width=True)
                    else:
                        st.caption("Waiting for official lineup.")
                with line_h:
                    st.markdown(f"**{event['home_team']}**")
                    home_rows = lineups.get("home", {}).get("lineup", [])
                    if home_rows:
                        st.dataframe(pd.DataFrame(home_rows), hide_index=True, use_container_width=True)
                    else:
                        st.caption("Waiting for official lineup.")

                st.markdown("### Bullpen workload — previous 3 days")
                bp_a, bp_h = st.columns(2)
                for column, team_name, workload in (
                    (bp_a, event["away_team"], away_bullpen),
                    (bp_h, event["home_team"], home_bullpen),
                ):
                    with column:
                        st.markdown(f"**{team_name}**")
                        if workload.get("available"):
                            summary = workload.get("summary", {})
                            m1, m2, m3 = st.columns(3)
                            m1.metric("1D pitches", summary.get("pitches_1d", 0))
                            m2.metric("2D pitches", summary.get("pitches_2d", 0))
                            m3.metric("3D pitches", summary.get("pitches_3d", 0))
                            rows = workload.get("relievers", [])
                            if rows:
                                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                        else:
                            st.caption("Workload unavailable.")

                with st.expander("Bookmaker prices"):
                    st.dataframe(
                        pd.DataFrame(event.get("bookmakers", [])),
                        hide_index=True,
                        use_container_width=True,
                    )

                with st.expander("Late-news override"):
                    away_override = st.selectbox(
                        f"{event['away_team']} bullpen",
                        ["No override", "Fully available", "Possibly limited", "Taxed", "Key arms unavailable"],
                    )
                    home_override = st.selectbox(
                        f"{event['home_team']} bullpen",
                        ["No override", "Fully available", "Possibly limited", "Taxed", "Key arms unavailable"],
                    )
                    late_news = st.text_area("Late injury, scratch, or pitch-limit notes")

                if st.button("Save timestamped snapshot", type="primary"):
                    payload = {
                        "model_status": MODEL_STATUS,
                        "event": event,
                        "mlb_schedule_match": schedule_game,
                        "automated_data": {
                            "lineups": lineups,
                            "away_bullpen_workload": away_bullpen,
                            "home_bullpen_workload": home_bullpen,
                        },
                        "manual_overrides": {
                            "away_bullpen": away_override,
                            "home_bullpen": home_override,
                            "late_news": late_news,
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

with tabs[2]:
    st.subheader("Saved Pregame Snapshots")
    try:
        snapshots = list_snapshots()
    except SnapshotStoreError as exc:
        st.error(str(exc))
        snapshots = []

    if not snapshots:
        st.info("No snapshots have been saved.")
    else:
        snapshot_labels = {
            f"{item.get('created_at') or 'Unknown'} — "
            f"{item.get('matchup') or item['identifier']}": item
            for item in snapshots
        }
        selected = st.selectbox("Snapshot", list(snapshot_labels))
        st.json(snapshot_labels[selected].get("payload", {}))

with tabs[3]:
    st.subheader("What the seven indicators contain")
    for family in SIGNAL_FAMILIES:
        st.markdown(
            f"### {family['number']}. {family['name']}\n"
            f"{family['purpose']}"
        )

    dictionary_path = Path(__file__).resolve().parent / "data_dictionary.csv"
    if dictionary_path.exists():
        st.dataframe(
            pd.read_csv(dictionary_path),
            use_container_width=True,
            hide_index=True,
        )

with tabs[4]:
    st.subheader("Setup and Data Status")
    checks = {
        "Odds API key configured": bool(api_key),
        "Supabase permanent storage configured": supabase_enabled(),
        "Normal Eastern game times enabled": True,
        "Season / 30-day / 7-day team ranks installed": True,
        "Basic eye-test view installed": True,
        "Indicator tracker installed": True,
        "Recommendations disabled until validation": not MODEL_STATUS["recommendations_enabled"],
    }

    for label, passed in checks.items():
        st.write(("✅" if passed else "⚠️") + " " + label)

    st.caption(
        "Ranks are descriptive eye-test information. Preliminary indicator direction "
        "does not equal a calibrated win probability or official bet."
    )
