from __future__ import annotations

from dataclasses import dataclass
import json
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass
class HttpClient:
    timeout: int = 20

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
                "User-Agent": "bet-bot/1.0",
            },
        )
        return self._read_json(request, timeout=timeout)

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
                "User-Agent": "bet-bot/1.0",
            },
            method="POST",
        )
        return self._read_json(request, timeout=timeout)

    def _read_json(self, request: Request, timeout: int | None = None) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=timeout or self.timeout) as response:
                raw_body = response.read().decode("utf-8")
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code}: {details}") from exc
        except socket.timeout as exc:
            raise TimeoutError("Tempo limite excedido na requisição.") from exc
        except URLError as exc:
            raise RuntimeError(f"Falha de rede: {exc.reason}") from exc

        if not raw_body:
            return {}
        return json.loads(raw_body)
