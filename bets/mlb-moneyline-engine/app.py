from __future__ import annotations

from datetime import date
from pathlib import Path

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
from src.snapshot_store import SnapshotStoreError, list_snapshots, save_snapshot, supabase_enabled

ensure_directories()
st.set_page_config(page_title="MLB Moneyline Engine", page_icon="⚾", layout="wide")
st.title("⚾ MLB Moneyline Engine")
st.caption("Automated data MVP • MLB moneyline only • Recommendations remain disabled")
st.info(f"**{MODEL_STATUS['stage']}** — {MODEL_STATUS['reason']}", icon="🤖")

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


@st.cache_data(ttl=60, show_spinner=False)
def load_lineups(game_pk: int):
    return fetch_game_lineups(game_pk)


@st.cache_data(ttl=3600, show_spinner=False)
def load_pitcher_stats(person_id: int | None, season: int):
    return fetch_pitcher_season_stats(person_id, season)


@st.cache_data(ttl=300, show_spinner=False)
def load_bullpen(team_id: int | None, as_of_date: date):
    return fetch_bullpen_workload(team_id, as_of_date)


def pitcher_card(team: str, probable_name: str | None, stats: dict):
    st.markdown(f"**{team} — {probable_name or 'TBD'}**")
    if stats.get("available"):
        st.write(
            f"Record: **{stats.get('record') or 'N/A'}**  |  "
            f"ERA: **{stats.get('era') or 'N/A'}**  |  "
            f"WHIP: **{stats.get('whip') or 'N/A'}**"
        )
        st.caption(
            f"GS: {stats.get('games_started')} • IP: {stats.get('innings_pitched')} • "
            f"K: {stats.get('strikeouts')} • BB: {stats.get('walks')}"
        )
    else:
        st.caption(stats.get("reason", "Pitcher statistics unavailable."))


def bullpen_panel(team: str, workload: dict):
    st.markdown(f"**{team} bullpen**")
    if not workload.get("available"):
        st.caption(workload.get("reason", "Bullpen workload unavailable."))
        return
    summary = workload["summary"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Pitches 1D", summary["pitches_1d"])
    c2.metric("Pitches 2D", summary["pitches_2d"])
    c3.metric("Pitches 3D", summary["pitches_3d"])
    st.caption(
        f"Innings last 3 days: {summary['innings_3d']} • "
        f"Relievers used: {summary['relievers_used_3d']}"
    )
    if workload.get("relievers"):
        st.dataframe(pd.DataFrame(workload["relievers"]), hide_index=True, use_container_width=True)


tabs = st.tabs(["Today's Slate", "Game Workspace", "Signal Families", "Saved Snapshots", "Setup Check"])

with tabs[0]:
    st.subheader("Today's MLB Moneylines")
    odds_payload = None
    if not api_key:
        st.warning("No Odds API key is configured. Add ODDS_API_KEY in Render Environment.")
    else:
        refresh_col, status_col = st.columns([1, 4])
        with refresh_col:
            if st.button("Refresh odds", type="primary"):
                load_odds.clear()
        try:
            odds_payload = load_odds(api_key)
            with status_col:
                st.caption(
                    f"Fetched: {odds_payload['fetched_at']} UTC • "
                    f"Credits remaining: {odds_payload['remaining'] or 'unknown'}"
                )
        except OddsAPIError as exc:
            st.error(str(exc))
    if odds_payload and odds_payload["events"]:
        rows = []
        for event in odds_payload["events"]:
            rows.append({
                "Start (UTC)": event["commence_time"],
                "Away": event["away_team"],
                "Best Away ML": event["best_away_odds"],
                "Away No-Vig": event["consensus_away_no_vig"],
                "Home": event["home_team"],
                "Best Home ML": event["best_home_odds"],
                "Home No-Vig": event["consensus_home_no_vig"],
                "Books": len(event["bookmakers"]),
            })
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Away No-Vig": st.column_config.NumberColumn(format="percent"),
                "Home No-Vig": st.column_config.NumberColumn(format="percent"),
            },
        )
        st.caption("No-vig values are the median normalized probability across returned books.")

with tabs[1]:
    st.subheader("Automated Pregame Workspace")
    if not api_key:
        st.warning("Configure ODDS_API_KEY before loading a matchup.")
    else:
        try:
            events = load_odds(api_key)["events"]
        except OddsAPIError as exc:
            st.error(str(exc))
            events = []
        if not events:
            st.info("No live MLB games are currently available.")
        else:
            labels = {
                f"{event['away_team']} at {event['home_team']} — {event['commence_time']}": event
                for event in events
            }
            selected_label = st.selectbox("Choose matchup", list(labels))
            event = labels[selected_label]
            local_game_date = event_date_eastern(event.get("commence_time"))
            season = local_game_date.year
            try:
                schedule_game = match_schedule_game(event, load_schedule(local_game_date))
            except MLBDataError as exc:
                st.error(str(exc))
                schedule_game = None

            away_col, start_col, home_col = st.columns(3)
            away_col.metric(event["away_team"], f"{event['best_away_odds']:+d}" if event["best_away_odds"] is not None else "N/A")
            start_col.metric("Start", event.get("commence_time") or "Unknown")
            home_col.metric(event["home_team"], f"{event['best_home_odds']:+d}" if event["best_home_odds"] is not None else "N/A")
            p1, p2 = st.columns(2)
            p1.metric("Away market baseline", f"{event['consensus_away_no_vig']:.1%}" if event.get("consensus_away_no_vig") is not None else "N/A")
            p2.metric("Home market baseline", f"{event['consensus_home_no_vig']:.1%}" if event.get("consensus_home_no_vig") is not None else "N/A")

            if not schedule_game:
                st.warning("The odds matchup could not be matched to MLB's schedule.")
            else:
                refresh_col, storage_col = st.columns([1, 3])
                with refresh_col:
                    if st.button("Refresh MLB data"):
                        load_lineups.clear()
                        load_pitcher_stats.clear()
                        load_bullpen.clear()
                with storage_col:
                    st.caption("Snapshot storage: " + ("Supabase (persistent)" if supabase_enabled() else "Render local disk (temporary)"))

                game_pk = schedule_game["game_pk"]
                try:
                    lineups = load_lineups(game_pk)
                except MLBDataError as exc:
                    st.warning(f"Lineup automation unavailable: {exc}")
                    lineups = {"away": {"confirmed": False, "lineup": []}, "home": {"confirmed": False, "lineup": []}}
                try:
                    away_pitcher = load_pitcher_stats(schedule_game.get("away_probable_pitcher_id"), season)
                    home_pitcher = load_pitcher_stats(schedule_game.get("home_probable_pitcher_id"), season)
                except MLBDataError as exc:
                    st.warning(f"Pitcher statistics unavailable: {exc}")
                    away_pitcher, home_pitcher = {"available": False}, {"available": False}
                try:
                    away_bullpen = load_bullpen(schedule_game.get("away_team_id"), local_game_date)
                    home_bullpen = load_bullpen(schedule_game.get("home_team_id"), local_game_date)
                except MLBDataError as exc:
                    st.warning(f"Bullpen workload unavailable: {exc}")
                    away_bullpen, home_bullpen = {"available": False}, {"available": False}

                st.markdown("### Starting pitchers")
                sp1, sp2 = st.columns(2)
                with sp1:
                    pitcher_card(event["away_team"], schedule_game.get("away_probable_pitcher"), away_pitcher)
                with sp2:
                    pitcher_card(event["home_team"], schedule_game.get("home_probable_pitcher"), home_pitcher)

                st.markdown("### Official lineups")
                both_confirmed = lineups.get("away", {}).get("confirmed") and lineups.get("home", {}).get("confirmed")
                if both_confirmed:
                    st.success("Both official starting lineups have been detected.")
                else:
                    st.warning("One or both lineups are not posted yet. Refresh after MLB publishes them.")
                l1, l2 = st.columns(2)
                with l1:
                    st.markdown(f"**{event['away_team']} lineup**")
                    rows = lineups.get("away", {}).get("lineup", [])
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True) if rows else st.caption("Waiting for official lineup.")
                with l2:
                    st.markdown(f"**{event['home_team']} lineup**")
                    rows = lineups.get("home", {}).get("lineup", [])
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True) if rows else st.caption("Waiting for official lineup.")

                st.markdown("### Automated bullpen workload")
                b1, b2 = st.columns(2)
                with b1:
                    bullpen_panel(event["away_team"], away_bullpen)
                with b2:
                    bullpen_panel(event["home_team"], home_bullpen)

                with st.expander("Optional manual overrides for late news"):
                    st.caption("Use only for injuries, manager announcements, pitch limits, or late scratches.")
                    away_override = st.selectbox(f"{event['away_team']} bullpen override", ["No override", "Fully available", "Possibly limited", "Taxed", "Key arms unavailable"])
                    home_override = st.selectbox(f"{event['home_team']} bullpen override", ["No override", "Fully available", "Possibly limited", "Taxed", "Key arms unavailable"])
                    late_news = st.text_area("Late-news notes")

                with st.expander("Seven-family research notes"):
                    family_notes = {}
                    for family in SIGNAL_FAMILIES:
                        family_notes[str(family["number"])] = st.text_area(
                            f"{family['number']}. {family['name']}",
                            help=family["purpose"],
                            key=f"family_note_{family['number']}",
                        )

                if st.button("Save automated timestamped snapshot", type="primary", use_container_width=True):
                    payload = {
                        "model_status": MODEL_STATUS,
                        "event": event,
                        "mlb_schedule_match": schedule_game,
                        "automated_data": {
                            "lineups": lineups,
                            "away_pitcher_season": away_pitcher,
                            "home_pitcher_season": home_pitcher,
                            "away_bullpen_workload": away_bullpen,
                            "home_bullpen_workload": home_bullpen,
                        },
                        "manual_overrides": {
                            "away_bullpen": away_override,
                            "home_bullpen": home_override,
                            "late_news": late_news,
                            "signal_family_notes": family_notes,
                        },
                    }
                    try:
                        result = save_snapshot(f"{event['away_team']} at {event['home_team']}", payload)
                        st.success(f"Saved to {result['source']}: {result['identifier'] or 'new row'}")
                    except SnapshotStoreError as exc:
                        st.error(str(exc))
                st.warning("Collection is automated, but official betting recommendations remain disabled.")

with tabs[2]:
    st.subheader("Seven Signal Families")
    for family in SIGNAL_FAMILIES:
        st.markdown(f"### {family['number']}. {family['name']}\n{family['purpose']}")
    dictionary_path = Path(__file__).resolve().parent / "data_dictionary.csv"
    if dictionary_path.exists():
        st.dataframe(pd.read_csv(dictionary_path), hide_index=True, use_container_width=True)

with tabs[3]:
    st.subheader("Saved Pregame Snapshots")
    try:
        snapshots = list_snapshots()
    except SnapshotStoreError as exc:
        st.error(str(exc))
        snapshots = []
    if not snapshots:
        st.info("No snapshots have been saved.")
    else:
        labels = {f"{item.get('created_at') or 'Unknown time'} — {item.get('matchup') or item['identifier']}": item for item in snapshots}
        selected = st.selectbox("Snapshot", list(labels))
        item = labels[selected]
        st.caption(f"Storage: {item['source']} • Lineups confirmed: {item.get('lineups_confirmed')}")
        st.json(item.get("payload", {}))

with tabs[4]:
    st.subheader("Setup Check")
    checks = {
        "Odds API key configured": bool(api_key),
        "Supabase permanent storage configured": supabase_enabled(),
        "Official MLB lineup automation installed": True,
        "Pitcher season-record automation installed": True,
        "Three-day bullpen workload automation installed": True,
        "Recommendations disabled until validation": not MODEL_STATUS["recommendations_enabled"],
    }
    for label, passed in checks.items():
        st.write(("✅" if passed else "⚠️") + " " + label)
    if not supabase_enabled():
        st.warning("Snapshots currently use Render's temporary disk. Run supabase/setup.sql and add Supabase environment variables for permanent storage.")
    st.markdown("""
### What remains manual
Only genuine exceptions: announced reliever unavailability, injuries, pitch limits, late scratches, and manager comments.

Do not paste API keys into chat or GitHub.
""")
