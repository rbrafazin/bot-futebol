from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BetOption:
    market: str
    confidence: int


@dataclass(frozen=True)
class MatchSuggestion:
    league_name: str
    home_team: str
    away_team: str
    kickoff: datetime
    markets: tuple[BetOption, BetOption, BetOption]
    confidence: int
    rationale: str
