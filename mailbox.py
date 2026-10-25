#!/usr/bin/env python3
"""
Mailbox abstraction — one interface, two providers.

  MAIL_PROVIDER=tempmail_lol   (default, public)  -> tempmail.lol, no signup/captcha
  MAIL_PROVIDER=tempik         (private)          -> your own Tempik instance
                                                    requires TEMPIK_BASE

Both expose:
  .address                     -> str
  .wait_for_otp(timeout, ...)  -> str | None
"""

from __future__ import annotations

import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


class MailboxError(Exception):
    pass


# ---------------------------------------------------------------- tempmail.lol
class LolBox:
    def __init__(self, proxy: str | None = None, domain: str | None = None):
        from tempmail_lol import TempmailLol
        self._c = TempmailLol(proxy=proxy)
        self.address = self._c.create(domain=domain)

    def wait_for_otp(self, timeout: int = 90, interval: int = 4) -> str | None:
        return self._c.wait_for_otp(timeout=timeout, interval=interval)


# ---------------------------------------------------------------------- tempik
class TempikBox:
    def __init__(self, proxy: str | None = None, domain: str | None = None):
        base = os.environ.get("TEMPIK_BASE")
        if not base:
            raise MailboxError(
                "MAIL_PROVIDER=tempik needs TEMPIK_BASE, e.g. "
                "TEMPIK_BASE=https://your-tempik-host/api"
            )
        from tempmail import TempikClient
        self._c = TempikClient(base_url=base)
        self.address = self._c.create_inbox(domain=domain)

    def wait_for_otp(self, timeout: int = 90, interval: int = 4) -> str | None:
        deadline = time.time() + timeout
        rx = re.compile(r"\b(\d{6})\b")
        while time.time() < deadline:
            try:
                for m in self._c.get_messages(self.address) or []:
                    blob = str(m.get("subject") or "")
                    try:
                        d = self._c.get_message_detail(self.address, m["id"])
                        blob += " " + str(d.get("body_text") or d.get("body_html") or "")
                    except Exception:
                        pass
                    hit = rx.search(blob)
                    if hit:
                        return hit.group(1)
            except Exception:
                pass
            time.sleep(interval)
        return None


# ------------------------------------------------------------------- factory
def open_mailbox(proxy: str | None = None, domain: str | None = None,
                 provider: str | None = None):
    """Return a mailbox with .address and .wait_for_otp()."""
    prov = (provider or os.environ.get("MAIL_PROVIDER") or "tempmail_lol").lower()

    if prov in ("tempmail_lol", "lol", "tempmail.lol", "public"):
        return LolBox(proxy=proxy, domain=domain)
    if prov in ("tempik", "private"):
        return TempikBox(proxy=proxy, domain=domain)

    raise MailboxError(f"unknown MAIL_PROVIDER={prov!r} (use tempmail_lol or tempik)")


if __name__ == "__main__":
    box = open_mailbox()
    print("provider:", os.environ.get("MAIL_PROVIDER", "tempmail_lol"))
    print("address :", box.address)
    print("otp     :", box.wait_for_otp(timeout=20))
