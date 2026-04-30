from __future__ import annotations

from datetime import datetime
from typing import Any
import html

from ..espn import EspnClient
from ..models import BetOption, MatchSuggestion

# NBA market identifiers
NBA_ML_HOME = "ML Casa"
NBA_ML_AWAY = "ML Visitante"
NBA_OVER = "Over Total"
NBA_UNDER = "Under Total"
NBA_SPREAD_HOME = "Spread Casa"
NBA_SPREAD_AWAY = "Spread Visitante"

# Confidence clamping
NBA_CONFIDENCE_FLOOR = 12
NBA_CONFIDENCE_CEILING = 93

# Probability clamping
NBA_SIDE_PROB_MIN = 0.15
NBA_SIDE_PROB_MAX = 0.88
NBA_TOTAL_PROB_MIN = 0.18
NBA_TOTAL_PROB_MAX = 0.85

# Blending weights
NBA_BOOK_WEIGHT = 0.68
NBA_FORM_WEIGHT = 0.32

# Form constants
NBA_FORM_DEFAULT = 0.50
NBA_FORM_MULTIPLIER = 0.52
NBA_FORM_BASE = 0.24

# Strength score
NBA_STRENGTH_WIN_PTS = 2
NBA_STRENGTH_LOSS_PTS = 1
NBA_STRENGTH_CLEAR_GAP = 6
NBA_STRENGTH_BOOST = 4
NBA_ML_BOOST = 2

# Spread
NBA_SPREAD_EDGE_THRESHOLD = 1.5

# Edge / value
NBA_VALUE_THRESHOLD = 5
NBA_VALUE_STRONG = 12


class NbaSuggestionEngine:
    """Analyses NBA game data from ESPN and produces ranked betting suggestions."""

    def __init__(self, espn_client: EspnClient) -> None:
        self.espn_client = espn_client

    def build_suggestions(
        self,
        league_slug: str,
        events: list[dict[str, Any]],
    ) -> list[MatchSuggestion]:
        suggestions: list[MatchSuggestion] = []
        for event in events:
            suggestion = self._build_single(league_slug, event)
            if suggestion is not None:
                suggestions.append(suggestion)
        return suggestions

    def _build_single(
        self,
        league_slug: str,
        event: dict[str, Any],
    ) -> MatchSuggestion | None:
        status = (((event.get("status") or {}).get("type") or {}).get("state") or "").lower()
        if status != "pre":
            return None

        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        home = self._find_competitor(competitors, "home")
        away = self._find_competitor(competitors, "away")
        if not home or not away:
            return None

        raw_date = event.get("date")
        if not raw_date:
            return None

        home_team = home.get("team", {}).get("displayName", "Casa")
        away_team = away.get("team", {}).get("displayName", "Visitante")
        kickoff = self.espn_client.parse_kickoff(raw_date)
        league_name = self._extract_league_name(event, competition, league_slug)

        home_record = self._extract_basketball_record(home)
        away_record = self._extract_basketball_record(away)
        odds_data = self._extract_nba_odds(competition)

        ranked_markets, confidence, rationale = self._pick_markets(
            home_team=home_team,
            away_team=away_team,
            home_record=home_record,
            away_record=away_record,
            odds_data=odds_data,
        )

        return MatchSuggestion(
            league_name=league_name,
            home_team=home_team,
            away_team=away_team,
            kickoff=kickoff,
            markets=ranked_markets,
            confidence=confidence,
            rationale=rationale,
            sport="basketball",
        )

    @staticmethod
    def _find_competitor(competitors: list[dict[str, Any]], home_away: str) -> dict[str, Any] | None:
        for competitor in competitors:
            if (competitor.get("homeAway") or "").lower() == home_away:
                return competitor
        return None

    @staticmethod
    def _extract_league_name(event: dict[str, Any], competition: dict[str, Any], league_slug: str) -> str:
        event_leagues = event.get("leagues") or []
        if event_leagues:
            name = event_leagues[0].get("name")
            if name:
                return name
        comp_league = (competition.get("league") or {}).get("name")
        if comp_league:
            return comp_league
        return league_slug

    @staticmethod
    def _extract_basketball_record(competitor: dict[str, Any]) -> dict[str, int]:
        records = competitor.get("records") or []
        summary = ""
        for record in records:
            name = (record.get("name") or record.get("type") or "").lower()
            if name in {"overall", "all", "total"}:
                summary = record.get("summary", "")
                break
        if not summary and records:
            summary = records[0].get("summary", "")

        parts = summary.split("-")
        wins = int(parts[0]) if len(parts) >= 1 and parts[0].strip().isdigit() else 0
        losses = int(parts[1]) if len(parts) >= 2 and parts[1].strip().isdigit() else 0
        games = wins + losses

        return {"wins": wins, "losses": losses, "games": games}

    @staticmethod
    def _extract_nba_odds(competition: dict[str, Any]) -> dict[str, Any]:
        odds_entries = competition.get("odds") or []
        odd = next((item for item in odds_entries if isinstance(item, dict)), None)
        if odd is None:
            return {"moneyline": {}, "spread": {}, "total": {}, "over_under_line": None}

        total = odd.get("total") or {}
        over_price = _extract_american_price((total.get("over") or {}).get("close"))
        under_price = _extract_american_price((total.get("under") or {}).get("close"))

        moneyline = odd.get("moneyline") or {}
        home_price = _extract_american_price((moneyline.get("home") or {}).get("close"))
        away_price = _extract_american_price((moneyline.get("away") or {}).get("close"))

        spread = odd.get("spread") or {}
        spread_line = spread.get("line")
        spread_home_price = _extract_american_price((spread.get("home") or {}).get("close"))
        spread_away_price = _extract_american_price((spread.get("away") or {}).get("close"))

        over_under_line = odd.get("overUnder")

        return {
            "moneyline": {
                "home_price": home_price,
                "away_price": away_price,
                "home_implied": _american_to_probability(home_price) if home_price is not None else None,
                "away_implied": _american_to_probability(away_price) if away_price is not None else None,
            },
            "spread": {
                "line": float(spread_line) if isinstance(spread_line, (int, float)) else None,
                "home_price": spread_home_price,
                "away_price": spread_away_price,
            },
            "total": {
                "over_price": over_price,
                "under_price": under_price,
                "over_implied": _american_to_probability(over_price) if over_price is not None else None,
                "under_implied": _american_to_probability(under_price) if under_price is not None else None,
            },
            "over_under_line": float(over_under_line) if isinstance(over_under_line, (int, float)) else None,
        }

    def _pick_markets(
        self,
        home_team: str,
        away_team: str,
        home_record: dict[str, int],
        away_record: dict[str, int],
        odds_data: dict[str, Any],
    ) -> tuple[tuple[BetOption, ...], int, str]:
        home_strength = self._strength_score(home_record)
        away_strength = self._strength_score(away_record)
        strength_gap = home_strength - away_strength
        home_form = self._form_score(home_record)
        away_form = self._form_score(away_record)

        ml = odds_data["moneyline"]
        home_implied = ml.get("home_implied")
        away_implied = ml.get("away_implied")
        normalized_ml = _normalize_pair(home_implied, away_implied)
        home_book_prob = normalized_ml.get("home")
        away_book_prob = normalized_ml.get("away")

        tot = odds_data["total"]
        over_implied = tot.get("over_implied")
        under_implied = tot.get("under_implied")
        normalized_tot = _normalize_pair(over_implied, under_implied)
        over_book_prob = normalized_tot.get("home")
        under_book_prob = normalized_tot.get("away")

        home_win_estimate = self._estimate_side_prob(home_book_prob, home_form)
        away_win_estimate = self._estimate_side_prob(away_book_prob, away_form)
        over_estimate = self._estimate_total_prob(over_book_prob, strength_gap)
        under_estimate = 1.0 - over_estimate
        under_estimate = max(NBA_TOTAL_PROB_MIN, min(NBA_TOTAL_PROB_MAX, under_estimate))

        home_edge = round((home_win_estimate - (home_book_prob or 0.0)) * 100) if home_book_prob else 0
        away_edge = round((away_win_estimate - (away_book_prob or 0.0)) * 100) if away_book_prob else 0
        over_edge = round((over_estimate - (over_book_prob or 0.0)) * 100) if over_book_prob else 0
        under_edge = round((under_estimate - (under_book_prob or 0.0)) * 100) if under_book_prob else 0

        spread_line = odds_data["spread"]["line"]
        spread_home_estimate = home_win_estimate
        spread_away_estimate = away_win_estimate
        if isinstance(spread_line, float) and isinstance(home_book_prob, float):
            if spread_line < 0:
                spread_home_estimate = home_win_estimate + 0.06
                spread_away_estimate = away_win_estimate - 0.02
            elif spread_line > 0:
                spread_home_estimate = home_win_estimate - 0.02
                spread_away_estimate = away_win_estimate + 0.06
        spread_home_edge = 0
        spread_away_edge = 0

        scores: dict[str, int] = {
            NBA_ML_HOME: _to_nba_percent(home_win_estimate),
            NBA_ML_AWAY: _to_nba_percent(away_win_estimate),
            NBA_OVER: _to_nba_percent(over_estimate),
            NBA_UNDER: _to_nba_percent(under_estimate),
            NBA_SPREAD_HOME: _to_nba_percent(spread_home_estimate),
            NBA_SPREAD_AWAY: _to_nba_percent(spread_away_estimate),
        }

        edges: dict[str, int] = {
            NBA_ML_HOME: home_edge,
            NBA_ML_AWAY: away_edge,
            NBA_OVER: over_edge,
            NBA_UNDER: under_edge,
            NBA_SPREAD_HOME: spread_home_edge,
            NBA_SPREAD_AWAY: spread_away_edge,
        }

        if strength_gap >= NBA_STRENGTH_CLEAR_GAP:
            scores[NBA_ML_HOME] = min(NBA_CONFIDENCE_CEILING, scores[NBA_ML_HOME] + NBA_STRENGTH_BOOST)
            scores[NBA_SPREAD_HOME] = min(NBA_CONFIDENCE_CEILING, scores[NBA_SPREAD_HOME] + NBA_ML_BOOST)
        elif strength_gap <= -NBA_STRENGTH_CLEAR_GAP:
            scores[NBA_ML_AWAY] = min(NBA_CONFIDENCE_CEILING, scores[NBA_ML_AWAY] + NBA_STRENGTH_BOOST)
            scores[NBA_SPREAD_AWAY] = min(NBA_CONFIDENCE_CEILING, scores[NBA_SPREAD_AWAY] + NBA_ML_BOOST)

        ranked = sorted(
            (
                BetOption(market=market, confidence=score, edge=edges.get(market, 0))
                for market, score in scores.items()
            ),
            key=lambda item: (-item.confidence, item.market),
        )
        ranked_tuple = tuple(ranked)

        rationale = self._build_rationale(home_team, away_team, home_book_prob, away_book_prob, strength_gap)

        return ranked_tuple, ranked_tuple[0].confidence, rationale

    def _estimate_side_prob(self, book_prob: float | None, form_score: float) -> float:
        form_prob = NBA_FORM_BASE + (form_score * NBA_FORM_MULTIPLIER)
        if isinstance(book_prob, float):
            estimate = (book_prob * NBA_BOOK_WEIGHT) + (form_prob * NBA_FORM_WEIGHT)
        else:
            estimate = form_prob
        return max(NBA_SIDE_PROB_MIN, min(NBA_SIDE_PROB_MAX, estimate))

    def _estimate_total_prob(self, book_prob: float | None, strength_gap: int) -> float:
        if isinstance(book_prob, float):
            estimate = book_prob
        else:
            estimate = 0.48
        estimate += min(0.04, abs(strength_gap) * 0.003)
        return max(NBA_TOTAL_PROB_MIN, min(NBA_TOTAL_PROB_MAX, estimate))

    @staticmethod
    def _strength_score(record: dict[str, int]) -> int:
        games = record["games"]
        if games <= 0:
            return 0
        return (record["wins"] * NBA_STRENGTH_WIN_PTS) - (record["losses"] * NBA_STRENGTH_LOSS_PTS)

    @staticmethod
    def _form_score(record: dict[str, int]) -> float:
        games = record["games"]
        if games <= 0:
            return NBA_FORM_DEFAULT
        return record["wins"] / games

    @staticmethod
    def _build_rationale(
        home_team: str,
        away_team: str,
        home_book_prob: float | None,
        away_book_prob: float | None,
        strength_gap: int,
    ) -> str:
        if isinstance(home_book_prob, float) and isinstance(away_book_prob, float):
            if home_book_prob >= 0.60:
                return f"{home_team} aparece como favorito nas odds da ESPN."
            if away_book_prob >= 0.60:
                return f"{away_team} aparece como favorito nas odds da ESPN."

        if strength_gap >= NBA_STRENGTH_CLEAR_GAP:
            return f"{home_team} apresenta campanha mais forte que {away_team}."

        if strength_gap <= -NBA_STRENGTH_CLEAR_GAP:
            return f"{away_team} apresenta campanha mais forte que {home_team}."

        return "Mercados ranqueados com base em odds e retrospecto da temporada."


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


def _normalize_pair(first: float | None, second: float | None) -> dict[str, float]:
    values = []
    if isinstance(first, float):
        values.append(("home", first))
    if isinstance(second, float):
        values.append(("away", second))
    total = sum(v for _, v in values)
    if total <= 0:
        return {}
    return {label: v / total for label, v in values}


def _to_nba_percent(probability: float) -> int:
    return max(NBA_CONFIDENCE_FLOOR, min(NBA_CONFIDENCE_CEILING, int(round(probability * 100))))


def format_nba_suggestion_card(suggestion: MatchSuggestion) -> str:
    hour = suggestion.kickoff.strftime("%H:%M")
    home = html.escape(suggestion.home_team)
    away = html.escape(suggestion.away_team)
    league = html.escape(suggestion.league_name)

    lines: list[str] = []
    lines.append(f"<b>{league}</b>")
    lines.append(f"<b>{home}</b>  x  <b>{away}</b>")
    lines.append(f"{hour}")

    for index, option in enumerate(suggestion.markets, start=1):
        lines.append(f"  {index}. {option.market}: <b>{option.confidence}%</b>")

    lines.append(f"\n{suggestion.rationale}")

    return "\n".join(lines)


def sort_and_limit_nba(
    suggestions: list[MatchSuggestion],
    limit: int,
    now: datetime,
) -> list[MatchSuggestion]:
    ordered = sorted(
        suggestions,
        key=lambda item: (item.kickoff, -item.confidence, item.league_name, item.home_team),
    )
    return [item for item in ordered if item.kickoff >= now][:limit]
