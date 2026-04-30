from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo
from typing import Any

from .http import HttpClient

ESPN_SCOREBOARD_URL = "http://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"


class EspnClient:
    def __init__(self, http_client: HttpClient, timezone_name: str) -> None:
        self.http_client = http_client
        self.timezone = ZoneInfo(timezone_name)
        self._history_cache: dict[str, list[dict[str, Any]]] = {}

    def fetch_games(
        self,
        league_slug: str,
        target_date: datetime,
        sport: str = "soccer",
    ) -> list[dict[str, Any]]:
        payload = self.http_client.get_json(
            ESPN_SCOREBOARD_URL.format(sport=sport, league=league_slug),
            params={"dates": target_date.strftime("%Y%m%d")},
        )
        return payload.get("events", [])

    def fetch_historical_events(
        self,
        league_slug: str,
        sport: str,
        days_back: int = 60,
    ) -> list[dict[str, Any]]:
        cache_key = f"{sport}:{league_slug}"
        if cache_key in self._history_cache:
            return self._history_cache[cache_key]

        all_events: list[dict[str, Any]] = []
        today = datetime.now(self.timezone).date()

        for offset in range(0, days_back, 6):
            date_from = today - timedelta(days=min(offset + 6, days_back))
            date_to = today - timedelta(days=offset)
            for day_offset in range((date_to - date_from).days + 1):
                target = date_from + timedelta(days=day_offset)
                try:
                    events = self.fetch_games(league_slug, target, sport=sport)
                    all_events.extend(events)
                except Exception:
                    continue

        self._history_cache[cache_key] = all_events
        return all_events

    def get_team_recent_form(
        self,
        team_id: str,
        league_slug: str,
        sport: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        events = self.fetch_historical_events(league_slug, sport, days_back=60)
        team_matches: list[dict[str, Any]] = []

        for event in events:
            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors") or []
            for competitor in competitors:
                team = competitor.get("team") or {}
                if str(team.get("id")) == str(team_id):
                    status = (((event.get("status") or {}).get("type") or {}).get("state") or "")
                    if status == "post":
                        team_matches.append(event)
                    break

        team_matches.sort(key=lambda e: e.get("date", ""), reverse=True)
        return team_matches[:limit]

    def parse_kickoff(self, raw_date: str) -> datetime:
        normalized = raw_date.replace("Z", "+00:00")
        kickoff = datetime.fromisoformat(normalized)
        return kickoff.astimezone(self.timezone)
