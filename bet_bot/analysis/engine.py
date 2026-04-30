from __future__ import annotations

from datetime import datetime
from typing import Any

from ..espn import EspnClient
from ..models import BetOption, MatchSuggestion
from . import constants as c
from .data_extractor import (
    average_draw_rate,
    collect_notes,
    collect_odds_blob,
    extract_league_name,
    extract_odds_snapshot,
    extract_record,
    find_competitor,
    form_score,
    strength_score,
)
from .h2h import (
    analyze_h2h_matches,
    compute_h2h_adjustments,
    extract_h2h_text_signals,
)
from .market_estimator import (
    estimate_btts_probability,
    estimate_double_chance_12,
    estimate_double_chance_1x,
    estimate_double_chance_x2,
    estimate_draw_no_bet_probability,
    estimate_draw_probability,
    estimate_over_15_probability,
    estimate_over_25_probability,
    estimate_side_probability,
    estimate_under_probability,
    to_percent,
)


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
        home = find_competitor(competitors, "home")
        away = find_competitor(competitors, "away")
        if not home or not away:
            return None

        raw_date = event.get("date")
        if not raw_date:
            return None

        home_team = home.get("team", {}).get("displayName", "Casa")
        away_team = away.get("team", {}).get("displayName", "Visitante")
        kickoff = self.espn_client.parse_kickoff(raw_date)
        league_name = extract_league_name(event, competition, league_slug)

        notes = collect_notes(event, competition)
        home_record = extract_record(home)
        away_record = extract_record(away)
        odds_blob = collect_odds_blob(competition)
        odds_snapshot = extract_odds_snapshot(competition)

        home_team_id = str(home.get("team", {}).get("id", ""))
        away_team_id = str(away.get("team", {}).get("id", ""))
        h2h_data: dict[str, Any] = {"h2h_total_matches": 0}
        if home_team_id and away_team_id:
            try:
                home_recent = self.espn_client.get_team_recent_form(
                    home_team_id, league_slug, "soccer", limit=5
                )
                away_recent = self.espn_client.get_team_recent_form(
                    away_team_id, league_slug, "soccer", limit=5
                )
                h2h_data = analyze_h2h_matches(home_team_id, away_team_id, home_recent, away_recent)
            except Exception:
                pass

        ranked_markets, confidence, rationale = self._pick_markets(
            home_team=home_team,
            away_team=away_team,
            home_record=home_record,
            away_record=away_record,
            notes=notes,
            odds_blob=odds_blob,
            odds_snapshot=odds_snapshot,
            h2h_data=h2h_data,
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

    def _pick_markets(
        self,
        home_team: str,
        away_team: str,
        home_record: dict[str, int],
        away_record: dict[str, int],
        notes: str,
        odds_blob: str,
        odds_snapshot: dict[str, float | str | None],
        h2h_data: dict[str, Any],
    ) -> tuple[tuple[BetOption, ...], int, str]:
        home_strength = strength_score(home_record)
        away_strength = strength_score(away_record)
        strength_gap = home_strength - away_strength
        home_form = form_score(home_record)
        away_form = form_score(away_record)
        draw_rate = average_draw_rate(home_record, away_record)
        form_gap = abs(home_form - away_form)
        combined_context = f"{notes} | {odds_blob}".lower()
        notes_lower = notes.lower()

        favorite_side = odds_snapshot.get("favorite_side")
        favorite_gap = odds_snapshot.get("favorite_gap")
        home_win_probability = odds_snapshot.get("home_win_probability")
        away_win_probability = odds_snapshot.get("away_win_probability")
        draw_probability = odds_snapshot.get("draw_probability")
        over_under = odds_snapshot.get("over_under")
        over_25_probability = odds_snapshot.get("over_25_probability")
        under_25_probability = odds_snapshot.get("under_25_probability")

        # --- Signal detection ---
        over_25_signal = _has_goal_signal(combined_context, c.GOAL_SIGNAL_OVER_25_TOKENS)
        over_15_signal = _has_goal_signal(combined_context, c.GOAL_SIGNAL_OVER_15_TOKENS)
        under_25_signal = _has_goal_signal(combined_context, c.UNDER_25_TOKENS)
        under_15_signal = _has_goal_signal(combined_context, c.UNDER_15_TOKENS)
        btts_signal = _has_any_token(combined_context, c.BTTS_TOKENS)

        # Text-based form signals
        home_positive_text = _has_any_token(notes_lower, c.HOME_FORM_POSITIVE_TOKENS)
        home_negative_text = _has_any_token(notes_lower, c.HOME_FORM_NEGATIVE_TOKENS)
        away_positive_text = _has_any_token(notes_lower, c.AWAY_FORM_POSITIVE_TOKENS)
        away_negative_text = _has_any_token(notes_lower, c.AWAY_FORM_NEGATIVE_TOKENS)

        # Adjusted form with text signals
        adjusted_home_form = home_form
        adjusted_away_form = away_form
        if home_positive_text:
            adjusted_home_form = min(1.0, home_form + 0.06)
        elif home_negative_text:
            adjusted_home_form = max(0.0, home_form - 0.06)
        if away_positive_text:
            adjusted_away_form = min(1.0, away_form + 0.06)
        elif away_negative_text:
            adjusted_away_form = max(0.0, away_form - 0.06)

        # Equilibrium detection (multifactor)
        equilibrium = _detect_equilibrium(
            combined_context=combined_context,
            favorite_gap=favorite_gap,
            strength_gap=strength_gap,
            home_win_probability=home_win_probability,
            away_win_probability=away_win_probability,
            draw_probability=draw_probability,
        )

        # H2H analysis
        h2h_text_signals = extract_h2h_text_signals(notes, home_team, away_team)
        h2h_adjustments = compute_h2h_adjustments(h2h_data, h2h_text_signals)

        # --- Probability estimates ---
        home_win_estimate = estimate_side_probability(home_win_probability, adjusted_home_form)
        away_win_estimate = estimate_side_probability(away_win_probability, adjusted_away_form)
        draw_estimate = estimate_draw_probability(
            draw_probability=draw_probability,
            equilibrium=equilibrium,
            home_form=adjusted_home_form,
            away_form=adjusted_away_form,
            favorite_gap=favorite_gap,
            draw_rate=draw_rate,
        )
        over_25_estimate = estimate_over_25_probability(
            over_25_probability=over_25_probability,
            over_under=over_under,
            over_25_signal=over_25_signal,
            equilibrium=equilibrium,
            draw_rate=draw_rate,
            strength_gap=strength_gap,
        )
        over_15_estimate = estimate_over_15_probability(
            over_25_estimate=over_25_estimate,
            over_15_signal=over_15_signal,
            draw_rate=draw_rate,
        )
        under_25_estimate = estimate_under_probability(under_25_probability, over_25_estimate)
        under_15_estimate = estimate_under_probability(None, over_15_estimate)
        btts_estimate = estimate_btts_probability(
            over_25_estimate=over_25_estimate,
            equilibrium=equilibrium,
            favorite_gap=favorite_gap,
            btts_signal=btts_signal,
            draw_rate=draw_rate,
            form_gap=form_gap,
        )
        home_dnb_estimate = estimate_draw_no_bet_probability(home_win_estimate, away_win_estimate)
        away_dnb_estimate = estimate_draw_no_bet_probability(away_win_estimate, home_win_estimate)

        dc_1x_estimate = estimate_double_chance_1x(home_win_estimate, draw_estimate)
        dc_x2_estimate = estimate_double_chance_x2(away_win_estimate, draw_estimate)
        dc_12_estimate = estimate_double_chance_12(home_win_estimate, away_win_estimate)

        # --- Adjust estimates with text signals ---
        if under_25_signal:
            under_25_estimate = min(0.88, under_25_estimate + 0.05)
            over_25_estimate = max(0.18, over_25_estimate - 0.03)
        if under_15_signal:
            under_15_estimate = min(0.90, under_15_estimate + 0.04)

        # --- Apply H2H adjustments ---
        home_win_estimate = max(0.10, min(0.90, home_win_estimate + h2h_adjustments["home_win_adj"]))
        away_win_estimate = max(0.10, min(0.90, away_win_estimate + h2h_adjustments["away_win_adj"]))
        draw_estimate = max(0.08, min(0.45, draw_estimate + h2h_adjustments["draw_adj"]))
        over_25_estimate = max(0.20, min(0.85, over_25_estimate + h2h_adjustments["over_adj"]))
        over_15_estimate = max(0.35, min(0.92, over_15_estimate + h2h_adjustments["over_adj"] * 0.7))
        under_25_estimate = max(0.10, min(0.85, under_25_estimate + h2h_adjustments["under_adj"]))
        under_15_estimate = max(0.08, min(0.90, under_15_estimate + h2h_adjustments["under_adj"] * 0.5))

        # --- Edge calculation (value bets) ---
        edges: dict[str, int] = {
            c.MARKET_HOME: _calc_edge(home_win_estimate, home_win_probability),
            c.MARKET_DRAW: _calc_edge(draw_estimate, draw_probability),
            c.MARKET_AWAY: _calc_edge(away_win_estimate, away_win_probability),
            c.MARKET_OVER_25: _calc_edge(over_25_estimate, over_25_probability),
            c.MARKET_UNDER_25: _calc_edge(under_25_estimate, under_25_probability),
        }

        if isinstance(home_win_probability, float) and isinstance(draw_probability, float):
            dc_1x_implied = home_win_probability + draw_probability
            edges[c.MARKET_DC_1X] = round((dc_1x_estimate - dc_1x_implied) * 100)
        if isinstance(away_win_probability, float) and isinstance(draw_probability, float):
            dc_x2_implied = away_win_probability + draw_probability
            edges[c.MARKET_DC_X2] = round((dc_x2_estimate - dc_x2_implied) * 100)
        if isinstance(home_win_probability, float) and isinstance(away_win_probability, float):
            dc_12_implied = home_win_probability + away_win_probability
            edges[c.MARKET_DC_12] = round((dc_12_estimate - dc_12_implied) * 100)
        if isinstance(home_win_probability, float) and isinstance(away_win_probability, float):
            total_win = home_win_probability + away_win_probability
            if total_win > 0:
                dnb_home_implied = home_win_probability / total_win
                dnb_away_implied = away_win_probability / total_win
                edges[c.MARKET_DNB_HOME] = round((home_dnb_estimate - dnb_home_implied) * 100)
                edges[c.MARKET_DNB_AWAY] = round((away_dnb_estimate - dnb_away_implied) * 100)

        scores: dict[str, int] = {
            c.MARKET_HOME: to_percent(home_win_estimate),
            c.MARKET_DRAW: to_percent(draw_estimate),
            c.MARKET_AWAY: to_percent(away_win_estimate),
            c.MARKET_OVER_15: to_percent(over_15_estimate),
            c.MARKET_UNDER_15: to_percent(under_15_estimate),
            c.MARKET_OVER_25: to_percent(over_25_estimate),
            c.MARKET_UNDER_25: to_percent(under_25_estimate),
            c.MARKET_DNB_HOME: to_percent(home_dnb_estimate),
            c.MARKET_DNB_AWAY: to_percent(away_dnb_estimate),
            c.MARKET_BTTS: to_percent(btts_estimate),
            c.MARKET_DC_1X: to_percent(dc_1x_estimate),
            c.MARKET_DC_X2: to_percent(dc_x2_estimate),
            c.MARKET_DC_12: to_percent(dc_12_estimate),
        }

        if strength_gap >= c.STRENGTH_CLEAR_GAP:
            scores[c.MARKET_HOME] = min(c.CONFIDENCE_CEILING, scores[c.MARKET_HOME] + c.STRENGTH_BOOST)
            scores[c.MARKET_DNB_HOME] = min(c.CONFIDENCE_CEILING, scores[c.MARKET_DNB_HOME] + c.DNB_BOOST)
            scores[c.MARKET_DC_1X] = min(c.CONFIDENCE_CEILING, scores[c.MARKET_DC_1X] + c.DNB_BOOST)
        elif strength_gap <= -c.STRENGTH_CLEAR_GAP:
            scores[c.MARKET_AWAY] = min(c.CONFIDENCE_CEILING, scores[c.MARKET_AWAY] + c.STRENGTH_BOOST)
            scores[c.MARKET_DNB_AWAY] = min(c.CONFIDENCE_CEILING, scores[c.MARKET_DNB_AWAY] + c.DNB_BOOST)
            scores[c.MARKET_DC_X2] = min(c.CONFIDENCE_CEILING, scores[c.MARKET_DC_X2] + c.DNB_BOOST)

        ranked = sorted(
            (
                BetOption(market=market, confidence=score, edge=edges.get(market, 0))
                for market, score in scores.items()
            ),
            key=lambda item: (-item.confidence, item.market),
        )
        ranked_tuple = tuple(ranked)

        rationale = _build_rationale(
            home_team=home_team,
            away_team=away_team,
            favorite_side=favorite_side,
            favorite_gap=favorite_gap,
            strength_gap=strength_gap,
            equilibrium=equilibrium,
            over_under=over_under,
            h2h_summary=h2h_adjustments.get("h2h_summary", ""),
        )

        return ranked_tuple, ranked_tuple[0].confidence, rationale


def _has_goal_signal(blob: str, tokens: tuple[str, ...]) -> bool:
    return any(token in blob for token in tokens)


def _has_any_token(blob: str, tokens: tuple[str, ...]) -> bool:
    return any(token in blob for token in tokens)


def _detect_equilibrium(
    combined_context: str,
    favorite_gap: float | str | None,
    strength_gap: int,
    home_win_probability: float | str | None,
    away_win_probability: float | str | None,
    draw_probability: float | str | None,
) -> bool:
    text_equilibrium = _has_any_token(combined_context, c.EQUILIBRIUM_TOKENS)

    gap_equilibrium = (
        isinstance(favorite_gap, float) and favorite_gap < c.FAVORITE_GAP_EQUILIBRIUM
    )

    strength_equilibrium = abs(strength_gap) <= c.STRENGTH_GAP_EQUILIBRIUM

    # If both win probabilities are close (within 0.1), it's balanced
    odds_equilibrium = False
    if isinstance(home_win_probability, float) and isinstance(away_win_probability, float):
        odds_equilibrium = abs(home_win_probability - away_win_probability) < 0.10

    # Draw probability above 28% also suggests tight matchup
    draw_equilibrium = isinstance(draw_probability, float) and draw_probability > 0.28

    # Score: need at least 2 signals for equilibrium
    signals = sum([text_equilibrium, gap_equilibrium, strength_equilibrium, odds_equilibrium, draw_equilibrium])
    return signals >= 2


def _calc_edge(estimate: float, book_prob: float | str | None) -> int:
    if isinstance(book_prob, float):
        return round((estimate - book_prob) * 100)
    return 0


def _build_rationale(
    home_team: str,
    away_team: str,
    favorite_side: float | str | None,
    favorite_gap: float | str | None,
    strength_gap: int,
    equilibrium: bool,
    over_under: float | str | None,
    h2h_summary: str = "",
) -> str:
    base = ""
    if isinstance(favorite_gap, float) and favorite_gap >= c.CLEAR_FAVORITE_GAP:
        if favorite_side == "home":
            base = c.RATIONALE_CLEAR_HOME.format(home=home_team)
        elif favorite_side == "away":
            base = c.RATIONALE_CLEAR_AWAY.format(away=away_team)
    elif strength_gap >= c.STRENGTH_CLEAR_FAVORITE:
        base = c.RATIONALE_STRONGER_HOME.format(home=home_team, away=away_team)
    elif strength_gap <= -c.STRENGTH_CLEAR_FAVORITE:
        base = c.RATIONALE_STRONGER_AWAY.format(home=home_team, away=away_team)
    elif isinstance(over_under, float) and over_under >= 2.5:
        base = c.RATIONALE_OPEN_MATCH
    elif equilibrium:
        base = c.RATIONALE_EQUILIBRIUM
    else:
        base = c.RATIONALE_DEFAULT

    if h2h_summary:
        base = f"{base} {h2h_summary}."

    return base
