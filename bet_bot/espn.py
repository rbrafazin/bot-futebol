from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from .http import HttpClient


ESPN_SCOREBOARD_URL = "http://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"


class EspnClient:
    def __init__(self, http_client: HttpClient, timezone_name: str) -> None:
        self.http_client = http_client
        self.timezone = ZoneInfo(timezone_name)

    def fetch_games(self, league_slug: str, target_date: datetime) -> list[dict[str, Any]]:
        payload = self.http_client.get_json(
            ESPN_SCOREBOARD_URL.format(league=league_slug),
            params={"dates": target_date.strftime("%Y%m%d")},
        )
        return payload.get("events", [])

    def parse_kickoff(self, raw_date: str) -> datetime:
        normalized = raw_date.replace("Z", "+00:00")
        kickoff = datetime.fromisoformat(normalized)
        return kickoff.astimezone(self.timezone)
