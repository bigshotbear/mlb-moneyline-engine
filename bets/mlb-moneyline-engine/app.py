from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import SNAPSHOT_DIR, ensure_directories, get_odds_api_key
from src.mlb_schedule import MLBScheduleError, fetch_schedule, match_schedule_game
from src.model_status import MODEL_STATUS, SIGNAL_FAMILIES
from src.odds_client import OddsAPIError, fetch_mlb_moneylines, parse_events
from src.snapshot_store import list_snapshots, read_snapshot, save_snapshot

ensure_directories()

st.set_page_config(
    page_title="MLB Moneyline Engine",
    page_icon="⚾",
    layout="wide",
)

st.title("⚾ MLB Moneyline Engine")
st.caption("Data-collection MVP • Moneyline only • No unvalidated betting recommendations")

st.info(
    f"**{MODEL_STATUS['stage']}** — {MODEL_STATUS['reason']}",
    icon="🧪",
)

api_key = get_odds_api_key()


@st.cache_data(ttl=300, show_spinner=False)
def load_odds(key: str):
    response = fetch_mlb_moneylines(key)
    return {
        "events": parse_events(response.events),
        "remaining": response.remaining_requests,
        "used": response.used_requests,
        "fetched_at": response.fetched_at_utc,
    }


@st.cache_data(ttl=900, show_spinner=False)
def load_schedule(selected_date: date):
    return fetch_schedule(selected_date)


tabs = st.tabs(
    [
        "Today's Slate",
        "Game Workspace",
        "Signal Families",
        "Saved Snapshots",
        "Setup Check",
    ]
)

with tabs[0]:
    st.subheader("Today's MLB Moneylines")
    odds_payload = None

    if not api_key:
        st.warning(
            "No API key is configured. Add ODDS_API_KEY to "
            ".streamlit/secrets.toml locally or Streamlit Cloud Secrets."
        )
    else:
        col_refresh, col_status = st.columns([1, 3])
        with col_refresh:
            if st.button("Refresh odds", type="primary"):
                load_odds.clear()
        try:
            with st.spinner("Loading current MLB moneylines..."):
                odds_payload = load_odds(api_key)
            with col_status:
                st.caption(
                    f"Fetched: {odds_payload['fetched_at']} UTC • "
                    f"Credits remaining: {odds_payload['remaining'] or 'unknown'}"
                )
        except OddsAPIError as exc:
            st.error(str(exc))

    if odds_payload and odds_payload["events"]:
        rows = []
        for event in odds_payload["events"]:
            rows.append(
                {
                    "Start (UTC)": event["commence_time"],
                    "Away": event["away_team"],
                    "Best Away ML": event["best_away_odds"],
                    "Away No-Vig": event["consensus_away_no_vig"],
                    "Home": event["home_team"],
                    "Best Home ML": event["best_home_odds"],
                    "Home No-Vig": event["consensus_home_no_vig"],
                    "Books": len(event["bookmakers"]),
                }
            )

        slate_df = pd.DataFrame(rows)
        st.dataframe(
            slate_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Away No-Vig": st.column_config.NumberColumn(format="percent"),
                "Home No-Vig": st.column_config.NumberColumn(format="percent"),
            },
        )
        st.caption(
            "No-vig values are the median normalized probability across returned books. "
            "Best available prices are displayed separately."
        )
    elif api_key:
        st.info("No MLB moneyline events were returned.")

with tabs[1]:
    st.subheader("Pregame Snapshot Workspace")

    if not api_key:
        st.warning("Configure the Odds API key before selecting a live game.")
    else:
        try:
            events = load_odds(api_key)["events"]
        except OddsAPIError as exc:
            st.error(str(exc))
            events = []

        if events:
            labels = {
                f"{e['away_team']} at {e['home_team']} — {e['commence_time']}": e
                for e in events
            }
            selected_label = st.selectbox("Choose matchup", list(labels))
            event = labels[selected_label]

            try:
                schedule = load_schedule(date.today())
                matched_schedule = match_schedule_game(event, schedule)
            except MLBScheduleError as exc:
                st.warning(str(exc))
                matched_schedule = None

            col_a, col_b, col_c = st.columns(3)
            col_a.metric(
                event["away_team"],
                f"{event['best_away_odds']:+d}" if event["best_away_odds"] is not None else "N/A",
            )
            col_b.metric("Start", event["commence_time"] or "Unknown")
            col_c.metric(
                event["home_team"],
                f"{event['best_home_odds']:+d}" if event["best_home_odds"] is not None else "N/A",
            )

            p1, p2 = st.columns(2)
            away_prob = event.get("consensus_away_no_vig")
            home_prob = event.get("consensus_home_no_vig")
            p1.metric("Away market baseline", f"{away_prob:.1%}" if away_prob is not None else "N/A")
            p2.metric("Home market baseline", f"{home_prob:.1%}" if home_prob is not None else "N/A")

            if matched_schedule:
                st.success(
                    "Probable pitchers: "
                    f"{matched_schedule.get('away_probable_pitcher') or 'TBD'} vs "
                    f"{matched_schedule.get('home_probable_pitcher') or 'TBD'}"
                )

            with st.expander("Bookmaker prices"):
                book_df = pd.DataFrame(event["bookmakers"])
                if not book_df.empty:
                    st.dataframe(book_df, use_container_width=True, hide_index=True)

            with st.form("pregame_snapshot_form"):
                st.markdown("### Manual verification")

                c1, c2 = st.columns(2)
                away_starter = c1.text_input(
                    "Away starting pitcher",
                    value=(matched_schedule or {}).get("away_probable_pitcher") or "",
                )
                home_starter = c2.text_input(
                    "Home starting pitcher",
                    value=(matched_schedule or {}).get("home_probable_pitcher") or "",
                )

                c1, c2 = st.columns(2)
                away_pitcher_record = c1.text_input(
                    "Away starter record (supporting only)",
                    placeholder="Example: 11-1",
                )
                home_pitcher_record = c2.text_input(
                    "Home starter record (supporting only)",
                    placeholder="Example: 6-6",
                )

                c1, c2 = st.columns(2)
                away_lineup = c1.text_area(
                    "Confirmed away lineup (one player per line)",
                    height=220,
                )
                home_lineup = c2.text_area(
                    "Confirmed home lineup (one player per line)",
                    height=220,
                )

                c1, c2 = st.columns(2)
                away_bullpen = c1.selectbox(
                    "Away high-leverage bullpen status",
                    ["Unknown", "Fully available", "Possibly limited", "Taxed", "Key arms unavailable"],
                )
                home_bullpen = c2.selectbox(
                    "Home high-leverage bullpen status",
                    ["Unknown", "Fully available", "Possibly limited", "Taxed", "Key arms unavailable"],
                )

                bullpen_notes = st.text_area(
                    "Bullpen workload notes",
                    placeholder="Closer 27 pitches yesterday; setup man used on back-to-back days...",
                )
                lineup_confirmed = st.checkbox("Official lineups have been confirmed")

                st.markdown("### Seven-family research notes")
                family_notes = {}
                for family in SIGNAL_FAMILIES:
                    with st.expander(f"{family['number']}. {family['name']}"):
                        st.caption(family["purpose"])
                        family_notes[str(family["number"])] = st.text_area(
                            "Notes / raw facts",
                            key=f"family_{family['number']}",
                        )

                submitted = st.form_submit_button(
                    "Save timestamped snapshot",
                    type="primary",
                    use_container_width=True,
                )

                if submitted:
                    payload = {
                        "model_status": MODEL_STATUS,
                        "event": event,
                        "mlb_schedule_match": matched_schedule,
                        "manual": {
                            "lineups_confirmed": lineup_confirmed,
                            "away_starter": away_starter,
                            "home_starter": home_starter,
                            "away_pitcher_record_supporting": away_pitcher_record,
                            "home_pitcher_record_supporting": home_pitcher_record,
                            "away_lineup": [x.strip() for x in away_lineup.splitlines() if x.strip()],
                            "home_lineup": [x.strip() for x in home_lineup.splitlines() if x.strip()],
                            "away_bullpen_status": away_bullpen,
                            "home_bullpen_status": home_bullpen,
                            "bullpen_notes": bullpen_notes,
                            "signal_family_notes": family_notes,
                        },
                    }
                    matchup = f"{event['away_team']}-at-{event['home_team']}"
                    destination = save_snapshot(SNAPSHOT_DIR, matchup, payload)
                    st.success(f"Saved: {destination.name}")

            st.warning(
                "Recommendations are intentionally disabled until historical "
                "walk-forward validation is completed."
            )
        else:
            st.info("No live games are available in the workspace.")

with tabs[2]:
    st.subheader("Seven Signal Families")
    for family in SIGNAL_FAMILIES:
        st.markdown(f"### {family['number']}. {family['name']}\n{family['purpose']}")

    dictionary_path = Path(__file__).resolve().parent / "data_dictionary.csv"
    if dictionary_path.exists():
        dictionary = pd.read_csv(dictionary_path)
        st.dataframe(dictionary, use_container_width=True, hide_index=True)

with tabs[3]:
    st.subheader("Saved Pregame Snapshots")
    snapshots = list_snapshots(SNAPSHOT_DIR)
    if not snapshots:
        st.info("No snapshots have been saved yet.")
    else:
        selected_snapshot = st.selectbox(
            "Snapshot",
            snapshots,
            format_func=lambda path: path.name,
        )
        st.json(read_snapshot(selected_snapshot))

with tabs[4]:
    st.subheader("Setup Check")
    checks = {
        "Odds API key configured": bool(api_key),
        "Snapshot directory available": SNAPSHOT_DIR.exists(),
        "Recommendations disabled until validation": not MODEL_STATUS["recommendations_enabled"],
        ".gitignore present": (Path(__file__).resolve().parent / ".gitignore").exists(),
    }

    for label, passed in checks.items():
        st.write(("✅" if passed else "❌") + " " + label)

    st.markdown(
        """
### Before using this app

1. Rotate any API key that appeared in a screenshot or public message.
2. Store the replacement only in Streamlit Secrets.
3. Run a few games as data-collection tests.
4. Verify names, odds, timestamps, lineups, and bullpen notes.
5. Do not enable recommendations until historical validation is complete.
"""
    )
