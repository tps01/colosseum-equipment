"""HTTP GET transport for ControlByWeb-style instruments."""

from __future__ import annotations

import base64
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from colosseum_equipment.exceptions import EquipmentConnectionError, EquipmentTimeoutError
from colosseum_equipment.transports.base import Transport


class HttpTransport(Transport):
    """Issue HTTP GET requests against a base URL.

    ControlByWeb WebRelay / X-410 control is GET-only. ``write`` and ``query``
    both GET ``base + path``; ``query`` returns the response body as text.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 5.0,
        username: str = "",
        password: str = "",
    ) -> None:
        base = base_url.strip().rstrip("/") + "/"
        if not base.startswith(("http://", "https://")):
            raise EquipmentConnectionError(
                f"HTTP transport requires an http(s) URL, got `{base_url}`",
            )
        self._base = base
        self._timeout = timeout
        self._auth_header = ""
        if username or password:
            token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
            self._auth_header = f"Basic {token}"

    def _get(self, path: str) -> str:
        relative = path.lstrip("/")
        url = urljoin(self._base, relative)
        headers: dict[str, str] = {}
        if self._auth_header:
            headers["Authorization"] = self._auth_header
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                raw: Any = response.read()
        except TimeoutError as exc:
            raise EquipmentTimeoutError(f"HTTP GET timed out: {url}") from exc
        except HTTPError as exc:
            raise EquipmentConnectionError(
                f"HTTP GET failed ({exc.code}): {url}",
            ) from exc
        except URLError as exc:
            raise EquipmentConnectionError(f"HTTP GET failed: {url}: {exc.reason}") from exc
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return str(raw)

    def write(self, data: str) -> None:
        self._get(data)

    def read(self) -> str:
        raise EquipmentConnectionError("HttpTransport has no standalone read; use query()")

    def query(self, data: str) -> str:
        return self._get(data)

    def close(self) -> None:
        return None
