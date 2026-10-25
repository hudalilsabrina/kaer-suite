#!/usr/bin/env python3
"""
Kaer AI CLI — register, harvest keys, inspect balances, sync to 9router.

  ./main.py register                 # interactive single signup
  ./main.py login  -e <email>        # re-issue OTP for an existing account
  ./main.py balance                  # show saved accounts + free credit
  ./main.py models                   # list live Kaer models
  ./main.py test   -m janus-1-pro    # smoke-test a key through 9router
  ./main.py sync                     # push every saved key into 9router
"""

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if os.path.isdir("/root/respan-suite"):
    sys.path.insert(0, "/root/respan-suite")

from kaer_client import KaerClient, KaerError, extract_otp, BASE
from tempmail import TempikClient

import kaer_farm

ACCOUNTS = kaer_farm.ACCOUNTS


def _read_accounts():
    out = []
    if not os.path.exists(ACCOUNTS):
        return out
    for block in open(ACCOUNTS).read().split("=== "):
        d = {}
        for line in block.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                d[k.strip()] = v.strip()
        if d.get("email"):
            out.append(d)
    return out


def cmd_register(args):
    domain = args.domain or "websurf.web.id"
    tm = TempikClient()
    email = tm.create_inbox(domain=domain)
    print(f"[mail] {email}")

    c = KaerClient(proxy=args.proxy)
    print("[code]", c.send_code(email))

    code = None
    for _ in range(16):
        time.sleep(3)
        for m in tm.get_messages(email) or []:
            subj = m.get("subject") or ""
            body = ""
            try:
                d = tm.get_message_detail(email, m["id"])
                body = d.get("body_text") or d.get("body_html") or ""
            except Exception:
                pass
            cand = extract_otp(subj) or extract_otp(body)
            if cand:
                code = cand
                break
        if code:
            break

    if not code:
        print("[-] no OTP received")
        return 1

    print("[verify]", c.verify(email, code, agreed=True))
    k = c.create_key("9router", scopes=["models"])
    key = k.get("secret")
    print(f"[key] {key}")

    acc = c._get("/api/apiplat/account")
    bal = acc.get("balance", {}).get("freeCreditUsd")
    kaer_farm.save_record(email, key, bal)
    if not args.no_9router:
        print("[9router]", "injected" if kaer_farm.inject(email, key) else "skipped")
    print(f"\nDone. credit=${bal}  base_url={BASE}/v1")
    return 0


def cmd_login(args):
    c = KaerClient(proxy=args.proxy)
    print("[code]", c.send_code(args.email))
    code = input("6-digit code: ").strip()
    print("[verify]", c.verify(args.email, code, agreed=True))
    k = c.create_key("9router", scopes=["models"])
    key = k.get("secret")
    print(f"[key] {key}")
    acc = c._get("/api/apiplat/account")
    bal = acc.get("balance", {}).get("freeCreditUsd")
    kaer_farm.save_record(args.email, key, bal)
    if not args.no_9router:
        kaer_farm.inject(args.email, key)
    return 0


def cmd_balance(args):
    rows = _read_accounts()
    print(f"{'email':38} {'free_usd':>9}  key")
    print("-" * 78)
    for d in rows:
        print(f"{d.get('email',''):38} {d.get('free_usd','-'):>9}  {(d.get('apikey') or '')[:24]}…")
    print(f"\n{len(rows)} accounts")


def cmd_models(args):
    import urllib.request
    req = urllib.request.Request(
        f"{BASE}/v1/models",
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    data = json.loads(urllib.request.urlopen(req, timeout=20).read())
    for m in data.get("data", []):
        k = m.get("kaer", {})
        pr = k.get("pricing", {})
        flag = "OK " if k.get("available") else "off"
        print(f"{flag} {m['id']:24} in=${pr.get('input_usd_per_m')} out=${pr.get('output_usd_per_m')}")


def cmd_test(args):
    import sqlite3, urllib.request
    conn = sqlite3.connect(kaer_farm.ROUTER_DB)
    key = conn.execute("SELECT key FROM apiKeys WHERE isActive = 1 LIMIT 1").fetchone()[0]
    conn.close()
    body = json.dumps({
        "model": f"kaer/{args.model}",
        "messages": [{"role": "user", "content": "Reply with one word: OK"}],
        "max_tokens": 16,
    }).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:20127/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        r = urllib.request.urlopen(req, timeout=90)
        print(r.status, r.read().decode()[:400])
    except Exception as e:
        print("ERR", e)


def main():
    ap = argparse.ArgumentParser(description="Kaer AI suite")
    sub = ap.add_subparsers(dest="cmd")

    r = sub.add_parser("register")
    r.add_argument("--domain")
    r.add_argument("--proxy", default=None)
    r.add_argument("--no-9router", action="store_true")
    r.set_defaults(fn=cmd_register)

    l = sub.add_parser("login")
    l.add_argument("-e", "--email", required=True)
    l.add_argument("--proxy", default=None)
    l.add_argument("--no-9router", action="store_true")
    l.set_defaults(fn=cmd_login)

    sub.add_parser("balance").set_defaults(fn=cmd_balance)
    sub.add_parser("models").set_defaults(fn=cmd_models)
    sub.add_parser("sync").set_defaults(fn=lambda a: (kaer_farm.main.__globals__, None)[1])

    t = sub.add_parser("test")
    t.add_argument("-m", "--model", default="janus-1-pro")
    t.set_defaults(fn=cmd_test)

    args = ap.parse_args()
    if not getattr(args, "fn", None):
        ap.print_help()
        return 0

    if args.cmd == "sync":
        sys.argv = ["kaer_farm.py", "--sync"]
        kaer_farm.main()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
