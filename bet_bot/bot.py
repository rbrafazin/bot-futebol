from __future__ import annotations

from datetime import datetime
import time
from typing import Any
from zoneinfo import ZoneInfo

from .analysis import SuggestionEngine, format_suggestion_card, sort_and_limit
from .config import Settings
from .espn import EspnClient
from .http import HttpClient
from .models import MatchSuggestion


REFRESH_CALLBACK = "refresh_today"


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
    ) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
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
        suggestion_engine: SuggestionEngine,
    ) -> None:
        self.settings = settings
        self.telegram = telegram_client
        self.espn = espn_client
        self.suggestion_engine = suggestion_engine
        self.timezone = ZoneInfo(settings.timezone)

    @classmethod
    def from_env(cls) -> "BetAdvisorBot":
        settings = Settings.from_env()
        http_client = HttpClient()
        espn_client = EspnClient(http_client=http_client, timezone_name=settings.timezone)
        telegram_client = TelegramClient(token=settings.telegram_bot_token, http_client=http_client)
        suggestion_engine = SuggestionEngine(espn_client=espn_client)
        return cls(settings, telegram_client, espn_client, suggestion_engine)

    def run(self) -> None:
        offset: int | None = None
        print("Bet bot em execução. Pressione Ctrl+C para encerrar.")

        while True:
            try:
                updates = self.telegram.get_updates(offset=offset, timeout=self.settings.poll_seconds)
                for update in updates:
                    offset = update["update_id"] + 1
                    self._handle_update(update)
            except KeyboardInterrupt:
                print("Bot encerrado.")
                return
            except TimeoutError:
                continue
            except Exception as exc:
                print(f"Falha ao processar atualizações: {exc}")
                time.sleep(3)

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

        if text.startswith("/start"):
            self._send_daily_suggestions(chat_id=chat_id, include_greeting=True)
            return

        self.telegram.send_message(
            chat_id=chat_id,
            text="Use /start para receber os palpites do dia.",
            reply_markup=self._refresh_keyboard(),
        )

    def _handle_callback(self, callback_query: dict[str, Any]) -> None:
        callback_id = callback_query.get("id")
        data = callback_query.get("data")
        message = callback_query.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if callback_id:
            self.telegram.answer_callback_query(callback_id, text="Atualizando os palpites...")

        if chat_id is None:
            return

        if data == REFRESH_CALLBACK:
            self._send_daily_suggestions(chat_id=chat_id, include_greeting=False)

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

        chunks = self._chunk_cards(suggestions)
        for index, chunk in enumerate(chunks):
            keyboard = self._refresh_keyboard() if index == len(chunks) - 1 else None
            self.telegram.send_message(chat_id=chat_id, text=chunk, reply_markup=keyboard)

    def _collect_suggestions(self, now: datetime) -> list[MatchSuggestion]:
        all_suggestions: list[MatchSuggestion] = []
        for league_slug in self.settings.leagues:
            try:
                events = self.espn.fetch_games(league_slug=league_slug, target_date=now)
                if not events:
                    continue
                league_suggestions = self.suggestion_engine.build_suggestions(league_slug, events)
                all_suggestions.extend(league_suggestions)
            except Exception as exc:
                print(f"Liga ignorada ({league_slug}): {exc}")

        return sort_and_limit(all_suggestions, limit=self.settings.suggestion_limit, now=now)

    def _chunk_cards(self, suggestions: list[MatchSuggestion]) -> list[str]:
        chunks: list[str] = []
        current_cards: list[str] = []
        current_length = 0

        for suggestion in suggestions:
            card = format_suggestion_card(suggestion)
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
