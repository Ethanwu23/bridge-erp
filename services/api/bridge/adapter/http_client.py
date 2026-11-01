"""ERPNext REST adapter.

Only the read paths V1 needs: list resources with filters + paging.
Auth: per-user API token (api_key:api_secret), header `Authorization: token ...`.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Iterable


class ERPError(RuntimeError):
    pass


class HttpERPClient:
    def __init__(self, base_url: str, api_key: str, api_secret: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"token {self.api_key}:{self.api_secret}",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # noqa: PERF203
            body = exc.read().decode("utf-8", "ignore")[:300]
            raise ERPError(f"HTTP {exc.code} {path}: {body}") from exc
        except Exception as exc:  # network, timeout
            raise ERPError(f"request failed {path}: {exc}") from exc

    def ping(self) -> bool:
        data = self._get("/api/method/ping", {})
        return data.get("message") == "pong"

    def list_resource(
        self,
        doctype: str,
        filters: Iterable[list] = (),
        fields: Iterable[str] = ("name",),
        limit_start: int = 0,
        limit_page_length: int = 100,
    ) -> list[dict]:
        params = {
            "filters": json.dumps(list(filters), ensure_ascii=False),
            "fields": json.dumps(list(fields), ensure_ascii=False),
            "limit_start": limit_start,
            "limit_page_length": limit_page_length,
        }
        data = self._get(f"/api/resource/{urllib.parse.quote(doctype)}", params)
        if "data" not in data:
            raise ERPError(f"unexpected payload for {doctype}: {str(data)[:200]}")
        return data["data"]
