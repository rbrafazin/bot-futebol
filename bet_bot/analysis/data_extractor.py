from __future__ import annotations

import re
from typing import Any

from .constants import (
    DEFAULT_DRAW_RATE,
    DNB_BOOST,
    FORM_BASE,
    FORM_DEFAULT,
    FORM_MULTIPLIER,
    STRENGTH_BOOST,
    STRENGTH_CLEAR_GAP,
    STRENGTH_DRAW_PTS,
    STRENGTH_WIN_PTS,
)


def find_competitor(competitors: list[dict[str, Any]], home_away: str) -> dict[str, Any] | None:
    for competitor in competitors:
        if (competitor.get("homeAway") or "").lower() == home_away:
            return competitor
    return None


def extract_league_name(
    event: dict[str, Any],
    competition: dict[str, Any],
    league_slug: str,
) -> str:
    event_leagues = event.get("leagues") or []
    if event_leagues:
        name = event_leagues[0].get("name")
        if name:
            return name

    comp_league = (competition.get("league") or {}).get("name")
    if comp_league:
        return comp_league

    return league_slug


def collect_notes(event: dict[str, Any], competition: dict[str, Any]) -> str:
    chunks: list[str] = []

    for note in event.get("notes") or []:
        text = note.get("headline") or note.get("text")
        if text:
            chunks.append(text)

    comp_note = competition.get("note")
    if isinstance(comp_note, str) and comp_note:
        chunks.append(comp_note)

    notes = competition.get("notes")
    if isinstance(notes, list):
        for note in notes:
            if isinstance(note, dict):
                text = note.get("headline") or note.get("text")
                if text:
                    chunks.append(text)
            elif isinstance(note, str) and note:
                chunks.append(note)

    for headline in competition.get("headlines") or []:
        if not isinstance(headline, dict):
            continue
        text = headline.get("description") or headline.get("shortLinkText")
        if text:
            chunks.append(text)

    return " | ".join(chunks)


def collect_odds_blob(competition: dict[str, Any]) -> str:
    fragments: list[str] = []
    for odd in competition.get("odds") or []:
        if not isinstance(odd, dict):
            continue
        for key in ("details", "overUnder", "spread", "awayTeamOdds", "homeTeamOdds", "drawOdds"):
            value = odd.get(key)
            if value is not None:
                fragments.append(str(value))
        total = odd.get("total") or {}
        moneyline = odd.get("moneyline") or {}
        point_spread = odd.get("pointSpread") or {}
        for container in (total, moneyline, point_spread):
            fragments.append(str(container))
    return " | ".join(fragments)


def extract_odds_snapshot(competition: dict[str, Any]) -> dict[str, float | str | None]:
    snapshot: dict[str, float | str | None] = {
        "favorite_side": None,
        "favorite_probability": None,
        "favorite_gap": None,
        "over_under": None,
        "home_win_probability": None,
        "away_win_probability": None,
        "draw_probability": None,
        "over_25_probability": None,
        "under_25_probability": None,
    }

    odds_entries = competition.get("odds") or []
    odd = next((item for item in odds_entries if isinstance(item, dict)), None)
    if odd is None:
        return snapshot

    over_under = odd.get("overUnder")
    if isinstance(over_under, (int, float)):
        snapshot["over_under"] = float(over_under)

    moneyline = odd.get("moneyline") or {}
    home_price = _extract_american_price((moneyline.get("home") or {}).get("close"))
    away_price = _extract_american_price((moneyline.get("away") or {}).get("close"))
    draw_price = _extract_american_price((moneyline.get("draw") or {}).get("close"))

    normalized_moneyline = _normalize_probabilities(
        [
            ("home", _american_to_probability(home_price) if home_price is not None else None),
            ("away", _american_to_probability(away_price) if away_price is not None else None),
            ("draw", _american_to_probability(draw_price) if draw_price is not None else None),
        ]
    )

    home_probability = normalized_moneyline.get("home")
    away_probability = normalized_moneyline.get("away")
    draw_probability = normalized_moneyline.get("draw")
    if isinstance(home_probability, float):
        snapshot["home_win_probability"] = home_probability
    if isinstance(away_probability, float):
        snapshot["away_win_probability"] = away_probability
    if isinstance(draw_probability, float):
        snapshot["draw_probability"] = draw_probability

    if isinstance(home_probability, float) and isinstance(away_probability, float):
        if home_probability >= away_probability:
            snapshot["favorite_side"] = "home"
            snapshot["favorite_probability"] = home_probability
            snapshot["favorite_gap"] = home_probability - away_probability
        else:
            snapshot["favorite_side"] = "away"
            snapshot["favorite_probability"] = away_probability
            snapshot["favorite_gap"] = away_probability - home_probability

    total = odd.get("total") or {}
    over_price = _extract_american_price((total.get("over") or {}).get("close"))
    under_price = _extract_american_price((total.get("under") or {}).get("close"))
    normalized_total = _normalize_probabilities(
        [
            ("over", _american_to_probability(over_price) if over_price is not None else None),
            ("under", _american_to_probability(under_price) if under_price is not None else None),
        ]
    )

    over_probability = normalized_total.get("over")
    under_probability = normalized_total.get("under")
    if isinstance(over_probability, float):
        snapshot["over_25_probability"] = over_probability
    if isinstance(under_probability, float):
        snapshot["under_25_probability"] = under_probability

    return snapshot


def extract_record(competitor: dict[str, Any]) -> dict[str, int]:
    records = competitor.get("records") or []
    summary = ""
    for record in records:
        name = (record.get("name") or record.get("type") or "").lower()
        if name in {"overall", "all"}:
            summary = record.get("summary", "")
            break
    if not summary and records:
        summary = records[0].get("summary", "")

    numbers = [int(value) for value in re.findall(r"\d+", summary)]
    wins = numbers[0] if len(numbers) >= 1 else 0
    draws = numbers[1] if len(numbers) >= 2 else 0
    losses = numbers[2] if len(numbers) >= 3 else 0
    games = wins + losses + draws

    return {"wins": wins, "losses": losses, "draws": draws, "games": games}


def strength_score(record: dict[str, int]) -> int:
    games = record["games"]
    if games <= 0:
        return 0
    return (record["wins"] * STRENGTH_WIN_PTS) + record["draws"] - record["losses"]


def form_score(record: dict[str, int]) -> float:
    games = record["games"]
    if games <= 0:
        return FORM_DEFAULT
    return ((record["wins"] * 1.0) + (record["draws"] * 0.5)) / games


def draw_rate(record: dict[str, int]) -> float:
    games = record["games"]
    if games <= 0:
        return DEFAULT_DRAW_RATE
    return record["draws"] / games


def average_draw_rate(home_record: dict[str, int], away_record: dict[str, int]) -> float:
    return (draw_rate(home_record) + draw_rate(away_record)) / 2


def _extract_american_price(price_payload: Any) -> int | None:
    if not isinstance(price_payload, dict):
        return None
    odds = price_payload.get("odds")
    if odds is None:
        return None
    try:
        return int(str(odds))
    except ValueError:
        return None


def _american_to_probability(price: int) -> float:
    if price < 0:
        return abs(price) / (abs(price) + 100)
    return 100 / (price + 100)


def _normalize_probabilities(
    entries: list[tuple[str, float | None]],
) -> dict[str, float]:
    valid_entries = [(label, value) for label, value in entries if isinstance(value, float)]
    total = sum(value for _, value in valid_entries)
    if total <= 0:
        return {}
    return {label: value / total for label, value in valid_entries}

