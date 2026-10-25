#!/usr/bin/env python3
"""
Kaer AI farm — registers api.kaer.ai accounts ($10 free credit each),
creates an API key per account, and injects them into 9router.

Flow (reverse-engineered from api.kaer.ai):
  1. POST /api/apiplat/auth/code    {"email": ...}
  2. read 6-digit OTP from the tempik inbox (subject carries the code)
  3. POST /api/apiplat/auth/verify  {"email","code","agreed":true}  -> cookies
  4. POST /api/apiplat/keys         {"name","scopes":["models"],...} -> kaer_live_...

Residential proxy rotation is required: the verify step enforces
`signup_velocity` per network (3 new accounts/network/day).

Usage:
  python3 kaer_farm.py -n 10 --gap 4
  python3 kaer_farm.py --sync            # push accounts.txt keys into 9router
"""

import argparse
import json
import os
import random
import sqlite3
import string
import sys
import time
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if os.path.isdir("/root/respan-suite"):
    sys.path.insert(0, "/root/respan-suite")

from kaer_client import KaerClient, KaerError, extract_otp
from tempmail import TempikClient

PROXY = os.environ.get("KAER_PROXY", "http://127.0.0.1:10801")
BRIDGE = "http://127.0.0.1:10801"
DOMAINS = ["websurf.web.id", "holysmp.me", "fantech.tech", "mcgg.me", "xentranetwork.me"]

ACCOUNTS = os.path.join(HERE, "accounts.txt")
KEYS = os.path.join(HERE, "keys.txt")
LOG = os.path.join(HERE, "farm.log")

ROUTER_DB = "/var/lib/9router/db/data.sqlite"
NODE_ID = "openai-compatible-chat-kaer"
NODE_NAME = "Kaer"
NODE_PREFIX = "kaer"
NODE_BASE = "https://api.kaer.ai/v1"


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def rotate():
    try:
        urllib.request.urlopen(BRIDGE + "/__new_session", timeout=10).read()
        return True
    except Exception:
        return False


def rand_local(n=10):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


# ---------------- 9router ----------------
def ensure_node(cur, now):
    cur.execute("SELECT id FROM providerNodes WHERE id = ?;", (NODE_ID,))
    if cur.fetchone():
        return
    data = {
        "prefix": NODE_PREFIX,
        "apiType": "chat",
        "baseUrl": NODE_BASE,
        "nodeName": NODE_NAME,
        "logo": "",
        "createdAt": now,
        "updatedAt": now,
    }
    cur.execute(
        "INSERT INTO providerNodes (id, type, name, data, createdAt, updatedAt) VALUES (?,?,?,?,?,?);",
        (NODE_ID, "openai-compatible", NODE_NAME, json.dumps(data), now, now),
    )


def inject(email, api_key, name=None, model="janus-1-pro"):
    if not os.path.exists(ROUTER_DB):
        return False
    try:
        conn = sqlite3.connect(ROUTER_DB, timeout=25.0)
        cur = conn.cursor()
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        ensure_node(cur, now)

        # skip duplicates
        cur.execute(
            "SELECT id FROM providerConnections WHERE provider = ? AND json_extract(data,'$.apiKey') = ?;",
            (NODE_ID, api_key),
        )
        if cur.fetchone():
            conn.close()
            return False

        conn_id = str(uuid.uuid4())
        conn_data = {
            "apiKey": api_key,
            "defaultModel": f"{NODE_PREFIX}/{model}",
            "testStatus": "active",
            "errorCode": None,
            "backoffLevel": 0,
            "providerSpecificData": {
                "prefix": NODE_PREFIX,
                "apiType": "chat",
                "baseUrl": NODE_BASE,
                "nodeName": NODE_NAME,
                "connectionProxyEnabled": False,
                "connectionProxyUrl": "",
                "connectionNoProxy": "",
            },
        }
        cur.execute(
            "INSERT INTO providerConnections (id, provider, authType, name, email, priority, isActive, data, createdAt, updatedAt) "
            "VALUES (?,?,?,?,?,?,?,?,?,?);",
            (conn_id, NODE_ID, "apikey", name or email, email, 1, 1, json.dumps(conn_data), now, now),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log(f"  inject error: {e}")
        return False


def save_record(email, key, balance):
    with open(ACCOUNTS, "a") as f:
        f.write(
            f"=== {email} ===\n"
            f"email     : {email}\n"
            f"apikey    : {key}\n"
            f"free_usd  : {balance}\n"
            f"base_url  : {NODE_BASE}\n"
            f"timestamp : {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
    with open(KEYS, "a") as f:
        f.write(key + "\n")


# ---------------- register ----------------
def register_one(idx):
    rotate()
    domain = random.choice(DOMAINS)
    tm = TempikClient()
    email = tm.create_inbox(domain=domain)
    log(f"[{idx}] {email}")

    c = KaerClient(proxy=PROXY)

    try:
        c.send_code(email)
    except KaerError as e:
        return {"email": email, "status": f"code_fail:{e.status}:{e.code}"}

    code = None
    for _ in range(14):
        time.sleep(3)
        try:
            msgs = tm.get_messages(email)
        except Exception:
            msgs = []
        for m in msgs:
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
        return {"email": email, "status": "no_otp"}

    try:
        v = c.verify(email, code, agreed=True)
    except KaerError as e:
        return {"email": email, "status": f"verify_fail:{e.status}:{e.code}"}

    if not v.get("created"):
        return {"email": email, "status": "not_created"}

    # create key
    try:
        k = c.create_key("9router", scopes=["models"])
    except KaerError as e:
        return {"email": email, "status": f"key_fail:{e.status}:{e.code}"}

    api_key = k.get("secret") or k.get("apiKey")
    if not api_key:
        return {"email": email, "status": "no_secret", "raw": str(k)[:200]}

    # balance
    bal = None
    try:
        acc = c._get("/api/apiplat/account")
        bal = acc.get("balance", {}).get("freeCreditUsd")
    except Exception:
        pass

    save_record(email, api_key, bal)
    ok = inject(email, api_key)
    log(f"  KEY {api_key[:22]}…  credit=${bal}  9router={'yes' if ok else 'no'}")
    return {"email": email, "key": api_key, "credit": bal, "status": "ok"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--count", type=int, default=1)
    ap.add_argument("--gap", type=float, default=4.0)
    ap.add_argument("--sync", action="store_true")
    args = ap.parse_args()

    if args.sync:
        n = 0
        if os.path.exists(ACCOUNTS):
            for block in open(ACCOUNTS).read().split("=== "):
                d = {}
                for line in block.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        d[k.strip()] = v.strip()
                if d.get("email") and d.get("apikey"):
                    if inject(d["email"], d["apikey"]):
                        n += 1
        log(f"synced {n} keys into 9router")
        return

    ok = fail = 0
    for i in range(1, args.count + 1):
        try:
            r = register_one(i)
        except Exception as e:
            r = {"status": f"exception:{e}"}
        if r.get("status") == "ok":
            ok += 1
        else:
            fail += 1
            log(f"  FAIL {r.get('status')}")
        if i < args.count:
            time.sleep(args.gap + random.uniform(0, 2))

    log(f"DONE  ok={ok}  fail={fail}")


if __name__ == "__main__":
    main()
