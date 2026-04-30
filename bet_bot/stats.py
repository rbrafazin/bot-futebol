from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any

from .models import BetOption, MatchSuggestion


STATS_FILE = "bet_bot_history.json"
MAX_HISTORY_DAYS = 30


@dataclass
class TrackedSuggestion:
    home_team: str
    away_team: str
    league_name: str
    kickoff: str
    top_market: str
    top_confidence: int
    top_n_markets: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "league_name": self.league_name,
            "kickoff": self.kickoff,
            "top_market": self.top_market,
            "top_confidence": self.top_confidence,
            "top_n_markets": self.top_n_markets,
        }


class StatsTracker:
    def __init__(self, file_path: str = STATS_FILE) -> None:
        self.file_path = Path(file_path)
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def log_suggestions(self, suggestions: list[MatchSuggestion]) -> None:
        entries: list[dict[str, Any]] = []
        try:
            entries = json.loads(self.file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

        for suggestion in suggestions:
            entries.append(
                TrackedSuggestion(
                    home_team=suggestion.home_team,
                    away_team=suggestion.away_team,
                    league_name=suggestion.league_name,
                    kickoff=suggestion.kickoff.isoformat(),
                    top_market=suggestion.markets[0].market if suggestion.markets else "",
                    top_confidence=suggestion.confidence,
                    top_n_markets=[
                        {"market": m.market, "confidence": m.confidence}
                        for m in suggestion.markets[:5]
                    ],
                ).to_dict()
            )

        cutoff = datetime.now().astimezone() - timedelta(days=MAX_HISTORY_DAYS)
        recent = [e for e in entries if e.get("kickoff", "") >= cutoff.isoformat()]

        self.file_path.write_text(
            json.dumps(recent, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_recent(self, days: int = 7) -> list[dict[str, Any]]:
        try:
            entries = json.loads(self.file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        cutoff = datetime.now().astimezone() - timedelta(days=days)
        return [e for e in entries if e.get("kickoff", "") >= cutoff.isoformat()]

    def get_summary(self) -> str:
        entries = self.get_recent(days=MAX_HISTORY_DAYS)
        if not entries:
            return "Nenhum palpite registrado nos últimos 30 dias."

        total = len(entries)
        by_confidence = {
            "alta (>=70%)": sum(1 for e in entries if e.get("top_confidence", 0) >= 70),
            "média (50-69%)": sum(1 for e in entries if 50 <= e.get("top_confidence", 0) < 70),
            "baixa (<50%)": sum(1 for e in entries if e.get("top_confidence", 0) < 50),
        }

        top_markets: dict[str, int] = {}
        for e in entries:
            market = e.get("top_market", "N/A")
            top_markets[market] = top_markets.get(market, 0) + 1

        sorted_markets = sorted(top_markets.items(), key=lambda x: -x[1])[:5]
        top_markets_text = "\n".join(
            f"  {m}: {c} palpites" for m, c in sorted_markets
        )

        return (
            "<b>Historico de palpites</b> (30d)\n\n"
            f"Total de jogos analisados: {total}\n\n"
            "Distribuicao por confianca:\n"
            f"  Alta (&gt;=70%): {by_confidence['alta (>=70%)']}\n"
            f"  Media (50-69%): {by_confidence['média (50-69%)']}\n"
            f"  Baixa (&lt;50%): {by_confidence['baixa (<50%)']}\n\n"
            "Mercados mais sugeridos:\n"
            f"{top_markets_text}"
        )
