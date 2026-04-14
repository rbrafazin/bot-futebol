from __future__ import annotations

from .bot import BetAdvisorBot


def main() -> None:
    bot = BetAdvisorBot.from_env()
    bot.run()
