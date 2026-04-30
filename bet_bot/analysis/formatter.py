from __future__ import annotations

import html
from datetime import datetime

from ..models import MatchSuggestion


def format_suggestion_card(suggestion: MatchSuggestion) -> str:
    hour = suggestion.kickoff.strftime("%H:%M")
    home = html.escape(suggestion.home_team)
    away = html.escape(suggestion.away_team)
    league = html.escape(suggestion.league_name)

    lines: list[str] = []
    lines.append(f"<b>{league}</b>")
    lines.append(f"<b>{home}</b>  x  <b>{away}</b>")
    lines.append(f"{hour}")

    for index, option in enumerate(suggestion.markets, start=1):
        lines.append(f"  {index}. {html.escape(option.market)}: <b>{option.confidence}%</b>")

    lines.append(f"\n{suggestion.rationale}")

    return "\n".join(lines)


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
