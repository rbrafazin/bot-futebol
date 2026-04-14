from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from .espn import EspnClient
from .models import BetOption, MatchSuggestion


class SuggestionEngine:
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

        notes = self._collect_notes(event, competition)
        home_record = self._extract_record(home)
        away_record = self._extract_record(away)
        odds_blob = self._collect_odds_blob(competition)
        odds_snapshot = self._extract_odds_snapshot(competition)

        ranked_markets, confidence, rationale = self._pick_markets(
            home_team=home_team,
            away_team=away_team,
            home_record=home_record,
            away_record=away_record,
            notes=notes,
            odds_blob=odds_blob,
            odds_snapshot=odds_snapshot,
        )

        return MatchSuggestion(
            league_name=league_name,
            home_team=home_team,
            away_team=away_team,
            kickoff=kickoff,
            markets=ranked_markets,
            confidence=confidence,
            rationale=rationale,
        )

    @staticmethod
    def _find_competitor(competitors: list[dict[str, Any]], home_away: str) -> dict[str, Any] | None:
        for competitor in competitors:
            if (competitor.get("homeAway") or "").lower() == home_away:
                return competitor
        return None

    @staticmethod
    def _extract_league_name(
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

    @staticmethod
    def _collect_notes(event: dict[str, Any], competition: dict[str, Any]) -> str:
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

    @staticmethod
    def _collect_odds_blob(competition: dict[str, Any]) -> str:
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

    @staticmethod
    def _extract_odds_snapshot(competition: dict[str, Any]) -> dict[str, float | str | None]:
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
        home_price = SuggestionEngine._extract_american_price((moneyline.get("home") or {}).get("close"))
        away_price = SuggestionEngine._extract_american_price((moneyline.get("away") or {}).get("close"))
        draw_price = SuggestionEngine._extract_american_price((moneyline.get("draw") or {}).get("close"))
        normalized_moneyline = SuggestionEngine._normalize_probabilities(
            [
                ("home", SuggestionEngine._american_to_probability(home_price) if home_price is not None else None),
                ("away", SuggestionEngine._american_to_probability(away_price) if away_price is not None else None),
                ("draw", SuggestionEngine._american_to_probability(draw_price) if draw_price is not None else None),
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
        over_price = SuggestionEngine._extract_american_price((total.get("over") or {}).get("close"))
        under_price = SuggestionEngine._extract_american_price((total.get("under") or {}).get("close"))
        normalized_total = SuggestionEngine._normalize_probabilities(
            [
                ("over", SuggestionEngine._american_to_probability(over_price) if over_price is not None else None),
                ("under", SuggestionEngine._american_to_probability(under_price) if under_price is not None else None),
            ]
        )

        over_probability = normalized_total.get("over")
        under_probability = normalized_total.get("under")
        if isinstance(over_probability, float):
            snapshot["over_25_probability"] = over_probability
        if isinstance(under_probability, float):
            snapshot["under_25_probability"] = under_probability

        return snapshot

    @staticmethod
    def _extract_record(competitor: dict[str, Any]) -> dict[str, int]:
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

        return {
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "games": games,
        }

    def _pick_markets(
        self,
        home_team: str,
        away_team: str,
        home_record: dict[str, int],
        away_record: dict[str, int],
        notes: str,
        odds_blob: str,
        odds_snapshot: dict[str, float | str | None],
    ) -> tuple[tuple[BetOption, BetOption, BetOption], int, str]:
        home_strength = self._strength_score(home_record)
        away_strength = self._strength_score(away_record)
        strength_gap = home_strength - away_strength
        home_form = self._form_score(home_record)
        away_form = self._form_score(away_record)
        combined_context = f"{notes} | {odds_blob}".lower()

        favorite_side = odds_snapshot.get("favorite_side")
        favorite_gap = odds_snapshot.get("favorite_gap")
        home_win_probability = odds_snapshot.get("home_win_probability")
        away_win_probability = odds_snapshot.get("away_win_probability")
        over_under = odds_snapshot.get("over_under")
        over_25_probability = odds_snapshot.get("over_25_probability")

        over_25_signal = self._has_goal_signal(combined_context, "2.5")
        over_15_signal = self._has_goal_signal(combined_context, "1.5")
        btts_signal = any(
            token in combined_context
            for token in (
                "both teams to score",
                "btts",
                "ambas marcam",
                "teams to score",
            )
        )
        equilibrium = any(
            token in combined_context
            for token in (
                "pick'em",
                "pick em",
                "equilibr",
                "tight",
                "close matchup",
                "draw",
            )
        ) or (
            isinstance(favorite_gap, float) and favorite_gap < 0.09
        ) or abs(strength_gap) <= 2

        home_win_estimate = self._estimate_side_probability(home_win_probability, home_form)
        away_win_estimate = self._estimate_side_probability(away_win_probability, away_form)
        over_25_estimate = self._estimate_over_25_probability(over_25_probability, over_under, over_25_signal)
        over_15_estimate = self._estimate_over_15_probability(over_25_estimate, over_15_signal)
        btts_estimate = self._estimate_btts_probability(
            over_25_estimate=over_25_estimate,
            equilibrium=equilibrium,
            favorite_gap=favorite_gap,
            btts_signal=btts_signal,
        )

        scores = {
            "Vitória Casa": self._to_percent(home_win_estimate),
            "Vitória Visitante": self._to_percent(away_win_estimate),
            "Over 1.5": self._to_percent(over_15_estimate),
            "Over 2.5": self._to_percent(over_25_estimate),
            "Ambas Marcam": self._to_percent(btts_estimate),
        }

        if strength_gap >= 7:
            scores["Vitória Casa"] = min(92, scores["Vitória Casa"] + 4)
        elif strength_gap <= -7:
            scores["Vitória Visitante"] = min(92, scores["Vitória Visitante"] + 4)

        ranked = sorted(
            (BetOption(market=market, confidence=score) for market, score in scores.items()),
            key=lambda item: (-item.confidence, item.market),
        )
        top_three = tuple(ranked[:3])

        if len(top_three) < 3:
            fallback_order = ("Over 1.5", "Ambas Marcam", "Over 2.5", "Vitória Casa", "Vitória Visitante")
            existing = {item.market for item in top_three}
            extra: list[BetOption] = list(top_three)
            for market in fallback_order:
                if market in existing:
                    continue
                extra.append(BetOption(market=market, confidence=60))
                existing.add(market)
                if len(extra) == 3:
                    break
            top_three = tuple(extra[:3])

        rationale = self._build_rationale(
            home_team=home_team,
            away_team=away_team,
            favorite_side=favorite_side,
            favorite_gap=favorite_gap,
            strength_gap=strength_gap,
            equilibrium=equilibrium,
            over_under=over_under,
        )

        return (
            (top_three[0], top_three[1], top_three[2]),
            top_three[0].confidence,
            rationale,
        )

    @staticmethod
    def _build_rationale(
        home_team: str,
        away_team: str,
        favorite_side: float | str | None,
        favorite_gap: float | str | None,
        strength_gap: int,
        equilibrium: bool,
        over_under: float | str | None,
    ) -> str:
        if isinstance(favorite_gap, float) and favorite_gap >= 0.16:
            if favorite_side == "home":
                return f"{home_team} aparece como favorito claro nas odds da ESPN."
            if favorite_side == "away":
                return f"{away_team} aparece como favorito claro nas odds da ESPN."

        if strength_gap >= 5:
            return f"{home_team} apresenta sinal mais forte que {away_team}."

        if strength_gap <= -5:
            return f"{away_team} apresenta sinal mais forte que {home_team}."

        if isinstance(over_under, float) and over_under >= 2.5:
            return "A linha principal de gols da ESPN sugere uma partida aberta."

        if equilibrium:
            return "Confronto equilibrado, com boa base para mercados conservadores."

        return "Os mercados foram ranqueados com base em odds e retrospecto recente disponíveis na ESPN."

    @staticmethod
    def _strength_score(record: dict[str, int]) -> int:
        games = record["games"]
        if games <= 0:
            return 0
        return (record["wins"] * 3) + record["draws"] - record["losses"]

    @staticmethod
    def _form_score(record: dict[str, int]) -> float:
        games = record["games"]
        if games <= 0:
            return 0.5
        return ((record["wins"] * 1.0) + (record["draws"] * 0.5)) / games

    @staticmethod
    def _has_goal_signal(blob: str, threshold: str) -> bool:
        tokens = (
            f"over {threshold}",
            f"o {threshold}",
            f"{threshold} goals",
            f"{threshold.replace('.', ',')}",
        )
        return any(token in blob for token in tokens)

    @staticmethod
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

    @staticmethod
    def _american_to_probability(price: int) -> float:
        if price < 0:
            return abs(price) / (abs(price) + 100)
        return 100 / (price + 100)

    @staticmethod
    def _normalize_probabilities(
        entries: list[tuple[str, float | None]],
    ) -> dict[str, float]:
        valid_entries = [(label, value) for label, value in entries if isinstance(value, float)]
        total = sum(value for _, value in valid_entries)
        if total <= 0:
            return {}
        return {label: value / total for label, value in valid_entries}

    @staticmethod
    def _estimate_side_probability(book_probability: float | str | None, form_score: float) -> float:
        form_probability = 0.22 + (form_score * 0.56)
        if isinstance(book_probability, float):
            estimate = (book_probability * 0.72) + (form_probability * 0.28)
        else:
            estimate = form_probability
        return max(0.18, min(0.88, estimate))

    @staticmethod
    def _estimate_over_25_probability(
        over_25_probability: float | str | None,
        over_under: float | str | None,
        over_25_signal: bool,
    ) -> float:
        if isinstance(over_25_probability, float):
            estimate = over_25_probability
        elif isinstance(over_under, float):
            estimate = 0.54 if over_under >= 2.5 else 0.46
        else:
            estimate = 0.5

        if over_25_signal:
            estimate += 0.05

        return max(0.35, min(0.82, estimate))

    @staticmethod
    def _estimate_over_15_probability(
        over_25_estimate: float,
        over_15_signal: bool,
    ) -> float:
        estimate = over_25_estimate + 0.18
        if over_15_signal:
            estimate += 0.04
        return max(0.55, min(0.9, estimate))

    @staticmethod
    def _estimate_btts_probability(
        over_25_estimate: float,
        equilibrium: bool,
        favorite_gap: float | str | None,
        btts_signal: bool,
    ) -> float:
        estimate = 0.24 + (over_25_estimate * 0.52)
        if equilibrium:
            estimate += 0.08
        if isinstance(favorite_gap, float):
            estimate -= min(0.09, favorite_gap * 0.45)
        if btts_signal:
            estimate += 0.08
        return max(0.32, min(0.78, estimate))

    @staticmethod
    def _to_percent(probability: float) -> int:
        return max(35, min(93, int(round(probability * 100))))


def format_suggestion_card(suggestion: MatchSuggestion) -> str:
    hour = suggestion.kickoff.strftime("%H:%M")
    markets_text = "\n".join(
        f"{index}. {option.market} ({option.confidence}%)"
        for index, option in enumerate(suggestion.markets, start=1)
    )
    return (
        f"🏟 {suggestion.league_name}\n"
        f"⚽️ {suggestion.home_team} x {suggestion.away_team}\n"
        f"⏰ Horário: {hour}\n"
        f"📈 Sugestões:\n{markets_text}\n"
        "ℹ️ Análise baseada em dados recentes da ESPN."
    )


def sort_and_limit(
    suggestions: list[MatchSuggestion],
    limit: int,
    now: datetime,
) -> list[MatchSuggestion]:
    ordered = sorted(
        suggestions,
        key=lambda item: (item.kickoff, -item.confidence, item.league_name, item.home_team),
    )
    return [item for item in ordered if item.kickoff >= now][:limit]
