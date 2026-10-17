"""HTTP GET transport for ControlByWeb-style instruments."""

from __future__ import annotations

import base64
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit

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
        parsed = _require_http_url(base, purpose="HTTP transport base URL")
        self._base = parsed
        self._timeout = timeout
        self._auth_header = ""
        if username or password:
            token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
            self._auth_header = f"Basic {token}"

    def _get(self, path: str) -> str:
        target = _instrument_url(self._base, path)
        url = urlunsplit(target)
        headers: dict[str, str] = {}
        if self._auth_header:
            headers["Authorization"] = self._auth_header
        request_target = target.path or "/"
        if target.query:
            request_target = f"{request_target}?{target.query}"
        connection_cls = HTTPSConnection if target.scheme == "https" else HTTPConnection
        port = target.port or (443 if target.scheme == "https" else 80)
        try:
            connection = connection_cls(target.hostname or "", port, timeout=self._timeout)
            try:
                connection.request("GET", request_target, headers=headers)
                response = connection.getresponse()
                raw = response.read()
                status = int(response.status)
            finally:
                connection.close()
        except TimeoutError as exc:
            raise EquipmentTimeoutError(f"HTTP GET timed out: {url}") from exc
        except (HTTPException, OSError) as exc:
            raise EquipmentConnectionError(f"HTTP GET failed: {url}: {exc}") from exc
        if status >= 400:
            raise EquipmentConnectionError(f"HTTP GET failed ({status}): {url}")
        return raw.decode("utf-8", errors="replace")

    def write(self, data: str) -> None:
        self._get(data)

    def read(self) -> str:
        raise EquipmentConnectionError("HttpTransport has no standalone read; use query()")

    def query(self, data: str) -> str:
        return self._get(data)

    def close(self) -> None:
        return None


def _require_http_url(url: str, *, purpose: str) -> SplitResult:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise EquipmentConnectionError(
            f"{purpose} requires an http(s) URL, got `{url}`",
        )
    return parsed


def _instrument_url(base: SplitResult, path: str) -> SplitResult:
    """Resolve ``path`` on the instrument origin. Absolute URLs to other hosts fail."""
    joined = urljoin(urlunsplit(base), path.lstrip("/"))
    target = _require_http_url(joined, purpose="HTTP instrument URL")
    if (
        target.scheme != base.scheme
        or target.hostname != base.hostname
        or (target.port or 0) != (base.port or 0)
    ):
        raise EquipmentConnectionError(
            f"HTTP path must stay on {base.hostname}, got `{path}`",
        )
    return target
