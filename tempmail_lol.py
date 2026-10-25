#!/usr/bin/env python3
"""
tempmail.lol client — public disposable inboxes, no signup, no captcha.

API (v2):
  POST https://api.tempmail.lol/v2/inbox/create   {"domain": null, "prefix": null}
       -> {"address": "...", "token": "..."}
  GET  https://api.tempmail.lol/v2/inbox?token=...
       -> {"emails": [{"from","subject","body","html","date"}], "expired": bool}
  GET  https://api.tempmail.lol/generate
       -> {"address": "...", "token": "..."}

Inboxes live ~1 hour. The token is the only handle, so keep it.
"""

from __future__ import annotations

import json
import random
import re
import string
import time
import urllib.error
import urllib.request
from typing import Any

API = "https://api.tempmail.lol"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")


class TempmailLolError(Exception):
    pass


class TempmailLol:
    """One inbox per instance. Call create() once, then poll messages()."""

    def __init__(self, proxy: str | None = None, timeout: int = 25):
        self.proxy = proxy
        self.timeout = timeout
        self.address: str | None = None
        self.token: str | None = None
        self._opener = self._build(proxy)

    @staticmethod
    def _build(proxy: str | None):
        handlers = []
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        return urllib.request.build_opener(*handlers)

    def _request(self, url: str, payload: dict | None = None) -> Any:
        headers = {"User-Agent": UA, "Accept": "application/json"}
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method="POST" if data else "GET")
        try:
            with self._opener.open(req, timeout=self.timeout) as r:
                body = r.read().decode()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            raise TempmailLolError(f"HTTP {e.code}: {e.read().decode()[:200]}")
        except Exception as e:
            raise TempmailLolError(str(e))

    # ---------- lifecycle ----------
    def create(self, domain: str | None = None, prefix: str | None = None) -> str:
        """Mint a fresh inbox and return its address."""
        payload: dict[str, Any] = {}
        if domain:
            payload["domain"] = domain
        if prefix:
            payload["prefix"] = prefix
        try:
            res = self._request(f"{API}/v2/inbox/create", payload)
        except TempmailLolError:
            res = self._request(f"{API}/generate")
        self.address = res.get("address")
        self.token = res.get("token")
        if not self.address or not self.token:
            raise TempmailLolError(f"unexpected create response: {res}")
        return self.address

    def messages(self) -> list[dict]:
        if not self.token:
            raise TempmailLolError("call create() first")
        res = self._request(f"{API}/v2/inbox?token={self.token}")
        if res.get("expired"):
            raise TempmailLolError("inbox expired")
        return res.get("emails") or []

    # ---------- OTP helper ----------
    def wait_for_otp(self, timeout: int = 90, interval: int = 4,
                     pattern: str = r"\b(\d{6})\b") -> str | None:
        """Poll until a 6-digit code shows up in a subject or body."""
        deadline = time.time() + timeout
        rx = re.compile(pattern)
        while time.time() < deadline:
            try:
                for m in self.messages():
                    blob = " ".join(
                        str(m.get(k) or "") for k in ("subject", "body", "html", "from")
                    )
                    hit = rx.search(blob)
                    if hit:
                        return hit.group(1) if hit.groups() else hit.group(0)
            except TempmailLolError:
                pass
            time.sleep(interval)
        return None

    # ---------- convenience ----------
    @staticmethod
    def random_prefix(n: int = 10) -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def quick_inbox(proxy: str | None = None) -> TempmailLol:
    tm = TempmailLol(proxy=proxy)
    tm.create()
    return tm


if __name__ == "__main__":
    box = quick_inbox()
    print("address:", box.address)
    print("waiting 30s for mail (send something to it now)…")
    print("otp:", box.wait_for_otp(timeout=30))
