from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from .team_rankings import team_profile


# These are engineering caps, not fitted empirical weights.
# They prevent correlated raw indicators from overwhelming the total.
FAMILY_CAPS = {
    "starter": 25.0,
    "offense": 25.0,
    "bullpen": 20.0,
    "defense_hidden": 10.0,
    "context": 10.0,
    "market": 10.0,
}

INDICATOR_CATALOG = [
    # Starting pitcher — 8
    ("starter_skill_composite", "Starter Skill Composite", "starter", 5.0),
    ("starter_era", "Starter ERA Edge", "starter", 3.5),
    ("starter_whip", "Starter WHIP Edge", "starter", 3.5),
    ("starter_kbb", "Starter K/BB Edge", "starter", 4.0),
    ("starter_batted_ball", "Starter Groundball / Flyball Fit", "starter", 2.5),
    ("starter_recent_form", "Starter Recent Form", "starter", 2.5),
    ("starter_expected_innings", "Expected Starter Innings", "starter", 2.0),
    ("starter_record_context", "Starter Record Context", "starter", 1.0),

    # Offense / confirmed lineup — 9
    ("lineup_wrc_hand", "Confirmed Lineup wRC+ vs Hand", "offense", 4.5),
    ("lineup_xwoba_hand", "Confirmed Lineup xwOBA vs Hand", "offense", 4.0),
    ("offense_season", "Season Offense", "offense", 2.5),
    ("offense_30", "30-Day Offense", "offense", 3.0),
    ("offense_7", "7-Day Offense", "offense", 2.5),
    ("contact_quality", "Barrel / Hard-Hit Edge", "offense", 3.0),
    ("lineup_plate_discipline", "Lineup K-BB Profile", "offense", 2.0),
    ("pitch_arsenal_fit", "Pitch-Arsenal Fit", "offense", 2.5),
    ("lineup_availability", "Confirmed Lineup Availability", "offense", 1.0),

    # Bullpen — 6
    ("bullpen_season", "Season Bullpen", "bullpen", 3.5),
    ("bullpen_30", "30-Day Bullpen", "bullpen", 3.5),
    ("bullpen_7", "7-Day Bullpen", "bullpen", 3.0),
    ("bullpen_workload", "Three-Day Bullpen Workload", "bullpen", 4.0),
    ("leverage_availability", "High-Leverage Arm Availability", "bullpen", 4.0),
    ("bullpen_handedness", "Bullpen Handedness Fit", "bullpen", 2.0),

    # Defense / hidden runs — 4
    ("catcher_value", "Catcher Framing / Blocking / Throwing", "defense_hidden", 2.5),
    ("infield_oaa_fit", "Infield OAA × Groundball Fit", "defense_hidden", 3.0),
    ("outfield_oaa_fit", "Outfield OAA × Flyball Fit", "defense_hidden", 2.5),
    ("baserunning", "Baserunning / Stolen-Base Edge", "defense_hidden", 2.0),

    # Context — 2
    ("home_park_fit", "Home Field / Asymmetric Park Fit", "context", 6.0),
    ("travel_roster_context", "Travel / Rest / Roster Context", "context", 4.0),

    # Market — 1
    ("price_edge", "No-Vig Price Edge", "market", 10.0),
]

assert len(INDICATOR_CATALOG) == 30

CATALOG_BY_KEY = {
    key: {
        "key": key,
        "title": title,
        "family": family,
        "max_points": max_points,
    }
    for key, title, family, max_points in INDICATOR_CATALOG
}


def _number(value: Any) -> float | None:
    if value in (None, "", "N/A", "-", "—"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rank(entry: dict[str, Any]) -> float | None:
    return _number(entry.get("rank"))


def _ratio(stats: dict[str, Any]) -> float | None:
    direct = _number(stats.get("strikeout_walk_ratio"))
    if direct is not None:
        return direct
    strikeouts = _number(stats.get("strikeouts"))
    walks = _number(stats.get("walks"))
    if strikeouts is None or walks is None or walks <= 0:
        return None
    return strikeouts / walks


def _win_pct(stats: dict[str, Any]) -> float | None:
    wins = _number(stats.get("wins"))
    losses = _number(stats.get("losses"))
    if wins is None or losses is None or wins + losses < 5:
        return None
    return wins / (wins + losses)


def _average_rank(category: dict[str, Any], windows: tuple[str, ...]) -> float | None:
    values = [_rank(category.get(window, {})) for window in windows]
    usable = [value for value in values if value is not None]
    return mean(usable) if usable else None


def _scaled_strength(
    magnitude: float,
    *,
    threshold: float,
    strong_at: float,
) -> float:
    """
    Return 0-100. Below threshold is neutral. At strong_at or larger = 100.
    """
    if magnitude < threshold:
        return 0.0
    if strong_at <= threshold:
        return 100.0
    scaled = (magnitude - threshold) / (strong_at - threshold)
    return round(max(0.0, min(1.0, scaled)) * 100.0, 1)


def _direction(
    away_value: float | None,
    home_value: float | None,
    *,
    higher_is_better: bool,
    threshold: float,
    strong_at: float,
    away_team: str,
    home_team: str,
) -> tuple[str | None, float, float | None]:
    if away_value is None or home_value is None:
        return None, 0.0, None

    raw_gap = away_value - home_value
    advantage = raw_gap if higher_is_better else -raw_gap
    magnitude = abs(advantage)
    strength = _scaled_strength(
        magnitude,
        threshold=threshold,
        strong_at=strong_at,
    )
    if strength <= 0:
        return None, 0.0, raw_gap

    supported_team = away_team if advantage > 0 else home_team
    return supported_team, strength, raw_gap


def _make_result(
    key: str,
    *,
    team: str | None,
    strength: float,
    reason: str,
    available: bool,
    supporting_only: bool = False,
) -> dict[str, Any]:
    meta = CATALOG_BY_KEY[key]
    points = (strength / 100.0) * meta["max_points"] if team else 0.0
    return {
        **meta,
        "team": team,
        "strength": round(strength, 1),
        "points": round(points, 3),
        "reason": reason,
        "available": available,
        "active": bool(team and strength > 0),
        "supporting_only": supporting_only,
    }


def evaluate_indicators(
    *,
    event: dict[str, Any],
    schedule_game: dict[str, Any],
    rankings: dict[str, Any],
    away_pitcher: dict[str, Any],
    home_pitcher: dict[str, Any],
    away_bullpen_workload: dict[str, Any] | None = None,
    home_bullpen_workload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    away = event["away_team"]
    home = event["home_team"]

    away_profile = team_profile(rankings, schedule_game.get("away_team_id"))
    home_profile = team_profile(rankings, schedule_game.get("home_team_id"))

    away_batting = away_profile.get("batting", {})
    home_batting = home_profile.get("batting", {})
    away_sp = away_profile.get("starting_pitching", {})
    home_sp = home_profile.get("starting_pitching", {})
    away_bp = away_profile.get("bullpen", {})
    home_bp = home_profile.get("bullpen", {})

    results: dict[str, dict[str, Any]] = {}

    def add_numeric(
        key: str,
        away_value: float | None,
        home_value: float | None,
        *,
        higher_is_better: bool,
        threshold: float,
        strong_at: float,
        reason_label: str,
        supporting_only: bool = False,
    ) -> None:
        team, strength, _ = _direction(
            away_value,
            home_value,
            higher_is_better=higher_is_better,
            threshold=threshold,
            strong_at=strong_at,
            away_team=away,
            home_team=home,
        )
        available = away_value is not None and home_value is not None
        results[key] = _make_result(
            key,
            team=team,
            strength=strength,
            reason=(
                f"{reason_label}: {away} "
                f"{round(away_value, 3) if away_value is not None else '—'} vs "
                f"{home} {round(home_value, 3) if home_value is not None else '—'}. "
                f"Strength {round(strength)} / 100."
            ),
            available=available,
            supporting_only=supporting_only,
        )

    # Currently available starter checks.
    add_numeric(
        "starter_era",
        _number(away_pitcher.get("era")),
        _number(home_pitcher.get("era")),
        higher_is_better=False,
        threshold=0.20,
        strong_at=1.50,
        reason_label="Starter ERA",
    )
    add_numeric(
        "starter_whip",
        _number(away_pitcher.get("whip")),
        _number(home_pitcher.get("whip")),
        higher_is_better=False,
        threshold=0.03,
        strong_at=0.35,
        reason_label="Starter WHIP",
    )
    add_numeric(
        "starter_kbb",
        _ratio(away_pitcher),
        _ratio(home_pitcher),
        higher_is_better=True,
        threshold=0.15,
        strong_at=2.00,
        reason_label="Starter K/BB ratio",
    )
    add_numeric(
        "starter_record_context",
        _win_pct(away_pitcher),
        _win_pct(home_pitcher),
        higher_is_better=True,
        threshold=0.08,
        strong_at=0.40,
        reason_label="Pitcher decision win percentage",
        supporting_only=True,
    )

    # Team offense ranks. Lower rank is better.
    for key, window, label in (
        ("offense_season", "season", "Season batting MLB rank"),
        ("offense_30", "month", "30-day batting MLB rank"),
        ("offense_7", "week", "7-day batting MLB rank"),
    ):
        add_numeric(
            key,
            _rank(away_batting.get(window, {})),
            _rank(home_batting.get(window, {})),
            higher_is_better=False,
            threshold=2.0,
            strong_at=20.0,
            reason_label=label,
        )

    # Team starting-pitching information fills recent-form context until the
    # deeper starter composite is implemented.
    add_numeric(
        "starter_recent_form",
        _average_rank(away_sp, ("month", "week")),
        _average_rank(home_sp, ("month", "week")),
        higher_is_better=False,
        threshold=2.0,
        strong_at=20.0,
        reason_label="Average 30-day and 7-day starting-pitching rank",
    )

    # Bullpen.
    add_numeric(
        "bullpen_season",
        _rank(away_bp.get("season", {})),
        _rank(home_bp.get("season", {})),
        higher_is_better=False,
        threshold=2.0,
        strong_at=20.0,
        reason_label="Season bullpen MLB rank",
    )
    add_numeric(
        "bullpen_30",
        _rank(away_bp.get("month", {})),
        _rank(home_bp.get("month", {})),
        higher_is_better=False,
        threshold=2.0,
        strong_at=20.0,
        reason_label="30-day bullpen MLB rank",
    )
    add_numeric(
        "bullpen_7",
        _rank(away_bp.get("week", {})),
        _rank(home_bp.get("week", {})),
        higher_is_better=False,
        threshold=2.0,
        strong_at=20.0,
        reason_label="7-day bullpen MLB rank",
    )

    away_workload = _number(
        (away_bullpen_workload or {}).get("summary", {}).get("pitches_3d")
    )
    home_workload = _number(
        (home_bullpen_workload or {}).get("summary", {}).get("pitches_3d")
    )
    add_numeric(
        "bullpen_workload",
        away_workload,
        home_workload,
        higher_is_better=False,
        threshold=15.0,
        strong_at=100.0,
        reason_label="Relief pitches over the previous three days",
    )

    # Context.
    results["home_park_fit"] = _make_result(
        "home_park_fit",
        team=home,
        strength=35.0,
        reason=(
            f"{home} receives a modest home-field score. Park-fit detail is not "
            "yet integrated, so this remains supporting context."
        ),
        available=True,
        supporting_only=True,
    )

    # Fill every unused catalog slot as unavailable so coverage is explicit.
    for key, title, family, max_points in INDICATOR_CATALOG:
        if key not in results:
            results[key] = _make_result(
                key,
                team=None,
                strength=0.0,
                reason=f"{title} data is not integrated yet.",
                available=False,
            )

    return [results[key] for key, *_ in INDICATOR_CATALOG]


def _family_contributions(
    indicators: list[dict[str, Any]],
    away_team: str,
    home_team: str,
) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}

    for family, cap in FAMILY_CAPS.items():
        family_items = [
            item
            for item in indicators
            if item["family"] == family and item.get("active")
        ]
        away_raw = sum(
            item["points"]
            for item in family_items
            if item.get("team") == away_team
        )
        home_raw = sum(
            item["points"]
            for item in family_items
            if item.get("team") == home_team
        )
        raw_total = away_raw + home_raw

        if raw_total > cap and raw_total > 0:
            scale = cap / raw_total
        else:
            scale = 1.0

        output[family] = {
            "cap": cap,
            "away": away_raw * scale,
            "home": home_raw * scale,
            "used": raw_total * scale,
        }

    return output


def score_matchup(
    indicators: list[dict[str, Any]],
    away_team: str,
    home_team: str,
) -> dict[str, Any]:
    families = _family_contributions(indicators, away_team, home_team)

    away_points = sum(item["away"] for item in families.values())
    home_points = sum(item["home"] for item in families.values())
    available_points = away_points + home_points

    # Score is centered at 50 and measures relative weighted support.
    # It is not a win probability.
    if available_points <= 0:
        away_score = home_score = 50.0
    else:
        away_share = away_points / available_points
        away_score = round(away_share * 100.0, 1)
        home_score = round(100.0 - away_score, 1)

    total_catalog_points = sum(meta["max_points"] for meta in CATALOG_BY_KEY.values())
    available_catalog_points = sum(
        item["max_points"] for item in indicators if item.get("available")
    )
    coverage = (
        round(available_catalog_points / total_catalog_points * 100.0, 1)
        if total_catalog_points
        else 0.0
    )

    top_five = sorted(
        [item for item in indicators if item.get("active")],
        key=lambda item: (item["points"], item["strength"]),
        reverse=True,
    )[:5]

    leader = None
    if away_score > home_score:
        leader = away_team
    elif home_score > away_score:
        leader = home_team

    return {
        "away_team": away_team,
        "home_team": home_team,
        "away_score": away_score,
        "home_score": home_score,
        "leader": leader,
        "coverage": coverage,
        "active_count": sum(1 for item in indicators if item.get("active")),
        "available_count": sum(1 for item in indicators if item.get("available")),
        "total_count": len(indicators),
        "families": families,
        "top_five": top_five,
    }
