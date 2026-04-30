from __future__ import annotations

from dataclasses import dataclass
import json
import socket
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class HttpError(RuntimeError):
    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {body}")


@dataclass
class HttpClient:
    timeout: int = 20
    max_retries: int = 2
    retry_delay: float = 1.0

    def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        final_url = url
        if params:
            final_url = f"{url}?{urlencode(params)}"

        request = Request(
            final_url,
            headers={
                "Accept": "application/json",
                "User-Agent": "bet-bot/2.0",
            },
        )
        return self._request_with_retry(request, timeout=timeout)

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "bet-bot/2.0",
            },
            method="POST",
        )
        return self._request_with_retry(request, timeout=timeout)

    def _should_retry(self, exc: Exception) -> bool:
        if isinstance(exc, TimeoutError):
            return True
        if isinstance(exc, URLError):
            return True
        if isinstance(exc, ConnectionError):
            return True
        if isinstance(exc, HttpError) and exc.status_code >= 500:
            return True
        return False

    def _request_with_retry(self, request: Request, timeout: int | None = None) -> dict[str, Any]:
        last_exception: Exception | None = None
        effective_timeout = timeout or self.timeout

        for attempt in range(self.max_retries + 1):
            try:
                return self._read_json(request, timeout=effective_timeout)
            except HttpError:
                raise
            except Exception as exc:
                if not self._should_retry(exc):
                    raise
                last_exception = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * (attempt + 1))

        raise RuntimeError(
            f"Requisição falhou após {self.max_retries + 1} tentativas: {last_exception}"
        ) from last_exception

    def _read_json(self, request: Request, timeout: int) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=timeout) as response:
                raw_body = response.read().decode("utf-8")
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            raise HttpError(exc.code, details) from exc
        except socket.timeout as exc:
            raise TimeoutError("Tempo limite excedido na requisição.") from exc
        except URLError as exc:
            raise RuntimeError(f"Falha de rede: {exc.reason}") from exc

        if not raw_body:
            return {}
        return json.loads(raw_body)
