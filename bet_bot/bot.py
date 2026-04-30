from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time
from typing import Any
from zoneinfo import ZoneInfo

from .analysis import (
    NbaSuggestionEngine,
    SuggestionEngine,
    format_nba_suggestion_card,
    format_suggestion_card,
    sort_and_limit,
    sort_and_limit_nba,
)
from .config import Settings, get_league_sport
from .espn import EspnClient
from .http import HttpClient
from .logging_config import get_logger, setup_logging
from .models import MatchSuggestion
from .stats import StatsTracker

REFRESH_CALLBACK = "refresh_today"
MAX_WORKERS = 4

logger = setup_logging()


class TelegramClient:
    def __init__(self, token: str, http_client: HttpClient) -> None:
        self._token = token
        self._http = http_client

    def get_updates(self, offset: int | None, timeout: int) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            payload["offset"] = offset

        response = self._http.get_json(
            self._url("getUpdates"),
            params=payload,
            timeout=timeout + 10,
        )
        return response.get("result", [])

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode
        self._http.post_json(self._url("sendMessage"), payload)

    def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        self._http.post_json(self._url("answerCallbackQuery"), payload)

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self._token}/{method}"


class BetAdvisorBot:
    def __init__(
        self,
        settings: Settings,
        telegram_client: TelegramClient,
        espn_client: EspnClient,
        soccer_engine: SuggestionEngine,
        nba_engine: NbaSuggestionEngine,
    ) -> None:
        self.settings = settings
        self.telegram = telegram_client
        self.espn = espn_client
        self.soccer_engine = soccer_engine
        self.nba_engine = nba_engine
        self.timezone = ZoneInfo(settings.timezone)
        self.stats_tracker = StatsTracker()

    @classmethod
    def from_env(cls) -> "BetAdvisorBot":
        settings = Settings.from_env()
        http_client = HttpClient()
        espn_client = EspnClient(http_client=http_client, timezone_name=settings.timezone)
        telegram_client = TelegramClient(token=settings.telegram_bot_token, http_client=http_client)
        soccer_engine = SuggestionEngine(espn_client=espn_client)
        nba_engine = NbaSuggestionEngine(espn_client=espn_client)
        return cls(settings, telegram_client, espn_client, soccer_engine, nba_engine)

    def run(self) -> None:
        offset: int | None = None
        logger.info("Bet bot iniciado. Pressione Ctrl+C para encerrar.")

        while True:
            try:
                updates = self.telegram.get_updates(offset=offset, timeout=self.settings.poll_seconds)
                for update in updates:
                    offset = update["update_id"] + 1
                    self._handle_update(update)
            except KeyboardInterrupt:
                logger.info("Bot encerrado pelo usuário.")
                return
            except TimeoutError:
                continue
            except Exception:
                logger.exception("Falha ao processar atualizações")
                time.sleep(5)

    def _handle_update(self, update: dict[str, Any]) -> None:
        if "message" in update:
            self._handle_message(update["message"])
            return

        if "callback_query" in update:
            self._handle_callback(update["callback_query"])

    def _handle_message(self, message: dict[str, Any]) -> None:
        text = (message.get("text") or "").strip()
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return

        command = text.partition(" ")[0].lower()

        if command == "/start":
            self._send_daily_suggestions(chat_id=chat_id, include_greeting=True)
            return

        if command == "/stats":
            self._send_stats(chat_id=chat_id)
            return

        self.telegram.send_message(
            chat_id=chat_id,
            text="Comandos disponíveis:\n/start — Palpites do dia\n/stats — Histórico de palpites",
            reply_markup=self._refresh_keyboard(),
        )

    def _handle_callback(self, callback_query: dict[str, Any]) -> None:
        callback_id = callback_query.get("id")
        data = callback_query.get("data")
        message = callback_query.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if callback_id:
            try:
                self.telegram.answer_callback_query(callback_id, text="Atualizando os palpites...")
            except Exception:
                logger.debug("Callback query expirado ou invalido (%s)", callback_id)

        if chat_id is None:
            return

        if data == REFRESH_CALLBACK:
            self._send_daily_suggestions(chat_id=chat_id, include_greeting=False)

    def _send_stats(self, chat_id: int) -> None:
        summary = self.stats_tracker.get_summary()
        self.telegram.send_message(chat_id=chat_id, text=summary, parse_mode="HTML")

    def _send_daily_suggestions(self, chat_id: int, include_greeting: bool) -> None:
        now = datetime.now(self.timezone)
        suggestions = self._collect_suggestions(now)

        if include_greeting:
            greeting = (
                "Olá! Consultei as ligas monitoradas na ESPN e separei os melhores "
                f"jogos com os mercados ranqueados para {now.strftime('%d/%m/%Y')}."
            )
            self.telegram.send_message(chat_id=chat_id, text=greeting, reply_markup=self._refresh_keyboard())

        if not suggestions:
            self.telegram.send_message(
                chat_id=chat_id,
                text=(
                    "Nenhum jogo pré-live elegível foi encontrado hoje nas ligas monitoradas. "
                    "Use o botão abaixo para tentar novamente mais tarde."
                ),
                reply_markup=self._refresh_keyboard(),
            )
            return

        try:
            self.stats_tracker.log_suggestions(suggestions)
        except Exception:
            logger.exception("Falha ao registrar histórico de palpites")

        chunks = self._chunk_cards(suggestions)
        for index, chunk in enumerate(chunks):
            keyboard = self._refresh_keyboard() if index == len(chunks) - 1 else None
            self.telegram.send_message(chat_id=chat_id, text=chunk, reply_markup=keyboard, parse_mode="HTML")

    def _collect_suggestions(self, now: datetime) -> list[MatchSuggestion]:
        all_suggestions: list[MatchSuggestion] = []

        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(self.settings.leagues))) as executor:
            future_to_league = {
                executor.submit(self._fetch_league_suggestions, league_slug, now): league_slug
                for league_slug in self.settings.leagues
            }

            for future in as_completed(future_to_league):
                league_slug = future_to_league[future]
                try:
                    league_suggestions = future.result()
                    all_suggestions.extend(league_suggestions)
                except Exception:
                    logger.exception("Liga ignorada (%s)", league_slug)

        return sort_and_limit(all_suggestions, limit=self.settings.suggestion_limit, now=now)

    def _fetch_league_suggestions(self, league_slug: str, now: datetime) -> list[MatchSuggestion]:
        sport = get_league_sport(league_slug)
        events = self.espn.fetch_games(league_slug=league_slug, target_date=now, sport=sport)
        if not events:
            return []
        if sport == "basketball":
            return self.nba_engine.build_suggestions(league_slug, events)
        return self.soccer_engine.build_suggestions(league_slug, events)

    def _chunk_cards(self, suggestions: list[MatchSuggestion]) -> list[str]:
        chunks: list[str] = []
        current_cards: list[str] = []
        current_length = 0

        for suggestion in suggestions:
            card = (
                format_nba_suggestion_card(suggestion)
                if suggestion.sport == "basketball"
                else format_suggestion_card(suggestion)
            )
            projected = current_length + len(card) + (2 if current_cards else 0)
            if projected > 3500 and current_cards:
                chunks.append("\n\n".join(current_cards))
                current_cards = [card]
                current_length = len(card)
                continue

            current_cards.append(card)
            current_length = projected

        if current_cards:
            chunks.append("\n\n".join(current_cards))

        return chunks

    @staticmethod
    def _refresh_keyboard() -> dict[str, Any]:
        return {
            "inline_keyboard": [
                [{"text": "Atualizar palpites", "callback_data": REFRESH_CALLBACK}]
            ]
        }
