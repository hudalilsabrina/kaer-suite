#!/usr/bin/env python3
"""
Kaer AI (api.kaer.ai) client.
Auth: email OTP -> session cookie. $10 free credit per account.
"""

import json
import re
import time
import urllib.request
import urllib.error

BASE = "https://api.kaer.ai"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")

BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": BASE,
    "Referer": f"{BASE}/login?mode=signup",
}


class KaerError(Exception):
    def __init__(self, msg, code=None, status=None):
        super().__init__(msg)
        self.code = code
        self.status = status


class KaerClient:
    def __init__(self, proxy: str | None = None):
        self.cookies: dict[str, str] = {}
        self.proxy = proxy
        self._opener = self._build_opener(proxy)

    @staticmethod
    def _build_opener(proxy: str | None):
        handlers = []
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        return urllib.request.build_opener(*handlers)

    def _cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    def _absorb_cookies(self, headers):
        for raw in headers.get_all("Set-Cookie") or []:
            first = raw.split(";")[0]
            if "=" in first:
                k, v = first.split("=", 1)
                self.cookies[k.strip()] = v.strip()

    def _post(self, path: str, payload: dict, timeout: int = 25) -> dict:
        headers = dict(BASE_HEADERS)
        if self.cookies:
            headers["Cookie"] = self._cookie_header()
        req = urllib.request.Request(
            f"{BASE}{path}", data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        try:
            with self._opener.open(req, timeout=timeout) as r:
                self._absorb_cookies(r.headers)
                body = r.read().decode()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                data = json.loads(body)
            except Exception:
                data = {"message": body[:300]}
            self._absorb_cookies(e.headers)
            raise KaerError(
                data.get("message") or body[:300],
                code=data.get("code"),
                status=e.code,
            )

    def _get(self, path: str, timeout: int = 25) -> dict:
        headers = dict(BASE_HEADERS)
        headers.pop("Content-Type", None)
        if self.cookies:
            headers["Cookie"] = self._cookie_header()
        req = urllib.request.Request(f"{BASE}{path}", headers=headers, method="GET")
        try:
            with self._opener.open(req, timeout=timeout) as r:
                self._absorb_cookies(r.headers)
                body = r.read().decode()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                data = json.loads(body)
            except Exception:
                data = {"message": body[:300]}
            raise KaerError(data.get("message") or body[:300],
                            code=data.get("code"), status=e.code)

    # ---------- auth ----------
    def send_code(self, email: str) -> dict:
        return self._post("/api/apiplat/auth/code", {"email": email})

    def verify(self, email: str, code: str, agreed: bool = True) -> dict:
        return self._post(
            "/api/apiplat/auth/verify",
            {"email": email, "code": code, "agreed": agreed},
        )

    def me(self) -> dict:
        return self._get("/api/apiplat/me")

    # ---------- keys ----------
    def list_keys(self) -> dict:
        return self._get("/api/apiplat/keys")

    def create_key(self, name: str, scopes: list[str] | None = None,
                   allowed_cidrs: list[str] | None = None,
                   monthly_budget_usd=None, expires_in_days=None) -> dict:
        payload = {
            "name": name,
            "scopes": scopes or ["models"],
            "allowed_cidrs": allowed_cidrs or [],
            "monthly_budget_usd": monthly_budget_usd,
            "expires_in_days": expires_in_days,
        }
        return self._post("/api/apiplat/keys", payload)

    # ---------- openai ----------
    def chat(self, api_key: str, model: str, messages: list, stream=False, **kw):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        }
        body = {"model": model, "messages": messages, "stream": stream, **kw}
        req = urllib.request.Request(
            f"{BASE}/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read().decode()
        except urllib.error.HTTPError as e:
            raise KaerError(e.read().decode()[:400], status=e.code)


def extract_otp(text: str):
    """Pull a 6-digit OTP from a subject or body."""
    if not text:
        return None
    m = re.search(r"\b(\d{6})\b", text)
    return m.group(1) if m else None


if __name__ == "__main__":
    c = KaerClient()
    print(c.send_code("demo_probe_1122@websurf.web.id"))
