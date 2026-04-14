from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


DEFAULT_LEAGUES = (
    "eng.1",
    "esp.1",
    "ita.1",
    "ger.1",
    "fra.1",
    "bra.1",
    "uefa.champions",
    "conmebol.libertadores",
    "conmebol.sudamericana",
)


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    leagues: tuple[str, ...]
    timezone: str
    suggestion_limit: int
    poll_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(Path(".env"))

        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "A variável TELEGRAM_BOT_TOKEN não foi definida. "
                "Configure-a no ambiente ou em um arquivo .env."
            )

        leagues_raw = os.getenv("BETBOT_LEAGUES", ",".join(DEFAULT_LEAGUES))
        leagues = tuple(slug.strip() for slug in leagues_raw.split(",") if slug.strip())

        return cls(
            telegram_bot_token=token,
            leagues=leagues,
            timezone=os.getenv("BETBOT_TIMEZONE", "America/Sao_Paulo").strip(),
            suggestion_limit=max(1, int(os.getenv("BETBOT_SUGGESTION_LIMIT", "20"))),
            poll_seconds=max(5, int(os.getenv("BETBOT_POLL_SECONDS", "25"))),
        )
