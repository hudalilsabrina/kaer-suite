# Kaer AI Suite 💠

Automated account registration, `$10` free-credit harvesting, API-key minting, and **9router** integration for **Kaer AI** ([api.kaer.ai](https://api.kaer.ai)).

Public build — inboxes come from **[tempmail.lol](https://tempmail.lol)**, so it runs with zero setup and no private infrastructure.

---

## What it does

- **Email-OTP signup** — no password, no captcha: `POST /api/apiplat/auth/code` → read the 6-digit code from a disposable inbox → `POST /api/apiplat/auth/verify`.
- **Auto key minting** — `POST /api/apiplat/keys` with `scopes: ["models"]`, then captures the one-time `kaer_live_…` secret.
- **Pluggable mailboxes** — `tempmail.lol` by default; point `MAIL_PROVIDER=tempik` at your own host if you have one.
- **Proxy rotation** — the verify step rate-limits per network (`signup_velocity`), so each signup can rotate its exit IP.
- **9router injection** — registers a `Kaer` provider node (prefix `kaer`) and drops every harvested key into the pool.

---

## Reverse-engineered API

| Step | Endpoint | Payload |
|---|---|---|
| 1 | `POST /api/apiplat/auth/code` | `{"email": "..."}` |
| 2 | *(inbox)* | OTP lives in the **subject**: `123456 is your api.kaer.ai sign-in code` |
| 3 | `POST /api/apiplat/auth/verify` | `{"email","code","agreed":true}` → sets `kaer_api_device` + `kaer_api_portal` cookies |
| 4 | `POST /api/apiplat/keys` | `{"name","scopes":["models"],"allowed_cidrs":[],"monthly_budget_usd":null,"expires_in_days":null}` → `{"secret":"kaer_live_…"}` |
| 5 | `GET /api/apiplat/account` | balance, tier, free-credit expiry |

Requests must carry `Origin: https://api.kaer.ai` — without it the API answers `403 {"message":"origin required"}`.

---

## Free tier facts

| Item | Value |
|---|---|
| Signup credit | **$10**, expires in 90 days |
| Monthly cap | $10 |
| Rate limit | 20 req/min per key |
| Concurrent streams | 2 |
| Max active keys | 3 |
| Services | `models` only (search/maps need $5 top-up, mail needs $50) |

Because a key is billed per call from that credit, `$10` is worth roughly **4–7M tokens** on the cheap models (`janus-1-flash`, `step-3.5-flash`) and ~1M on the pricier ones.

---

## Install

```bash
git clone https://github.com/hudalilsabrina/kaer-suite.git
cd kaer-suite
chmod +x install.sh
./install.sh
```

Python 3.10+. Standard library only — nothing to `pip install`.

---

## Mailbox providers

| `MAIL_PROVIDER` | Needs | Notes |
|---|---|---|
| `tempmail_lol` *(default)* | nothing | `api.tempmail.lol`, no signup, no captcha. Inbox lives ~1 hour |
| `tempik` | `TEMPIK_BASE` (+ `TEMPIK_DOMAINS`) | your own self-hosted instance |

```bash
# default, public
python3 kaer_farm.py -n 10

# your own tempik instance
export MAIL_PROVIDER=tempik
export TEMPIK_BASE=https://your-host/api
export TEMPIK_DOMAINS=yourdomain.tld,other.tld
python3 kaer_farm.py -n 10
```

---

## Environment

| Var | Default | Purpose |
|---|---|---|
| `MAIL_PROVIDER` | `tempmail_lol` | `tempmail_lol` or `tempik` |
| `KAER_PROXY` | *(none)* | outbound proxy for signup, e.g. `http://127.0.0.1:10801`. Needed for volume |
| `KAER_BRIDGE` | `http://127.0.0.1:10801` | endpoint hit with `/__new_session` to rotate a rotating-proxy bridge |
| `9ROUTER_DB` | `/var/lib/9router/db/data.sqlite` | 9router database path |
| `TEMPIK_BASE` / `TEMPIK_DOMAINS` | — | only for `MAIL_PROVIDER=tempik` |

Without a proxy you get ~3 accounts per network per day before `429 signup_velocity`.

---

## Usage

### Farm a batch

```bash
python3 kaer_farm.py -n 20 --gap 4
```

Each success prints the key and injects it into 9router immediately.

### Single interactive signup

```bash
./main.py register
```

### Re-login to an existing account (mint a fresh key)

```bash
./main.py login -e you@domain.tld
```

### Inspect / sync / test

```bash
./main.py balance
./main.py models
./main.py sync
./main.py test -m janus-1-pro
```

---

## Using the keys

### Direct (OpenAI-compatible)

```python
from openai import OpenAI

client = OpenAI(base_url="https://api.kaer.ai/v1", api_key="kaer_live_...")
r = client.chat.completions.create(
    model="janus-1-pro",
    messages=[{"role": "user", "content": "Halo"}],
)
print(r.choices[0].message.content, r.kaer["cost_usd"])
```

### Through 9router

```bash
curl http://127.0.0.1:20127/v1/chat/completions \
  -H "Authorization: Bearer <9ROUTER_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"kaer/janus-1-pro","messages":[{"role":"user","content":"Halo"}]}'
```

---

## Model notes

Only models the rate card marks `available: true` answer reliably. At time of writing:

| Serving | Temporarily unavailable (`503 model_unavailable`) |
|---|---|
| `janus-1-flash`, `janus-1-pro` | `deepseek-v4.1-flash` |
| `step-3.5-flash`, `step-3.7-flash`, `step-5-preview` | `qwen3.8-flash`, `qwen3.8-max` |
| `minimax-m3`, `hy3`, `hy-mt2-plus` | `glm-5.3-flash`, `glm-5.2`, `kimi-k3` |
| `laguna-s-2.1`, `laguna-xs-2.1` | `kimi-k2.6` (502 upstream) |

Availability flips — check `./main.py models` before wiring a combo.

---

## Files

```
kaer_client.py    # HTTP client: OTP auth, key minting, chat
kaer_farm.py      # batch registrar + 9router injector
main.py           # CLI
mailbox.py        # provider abstraction (tempmail_lol | tempik)
tempmail_lol.py   # api.tempmail.lol client
tempmail.py       # optional self-hosted tempik client
accounts.txt      # harvested accounts (gitignored)
keys.txt          # one key per line (gitignored)
farm.log          # run log
```

---

## Disclaimer

For research and personal experimentation. You are responsible for complying with
Kaer's Terms of Service and any applicable law. Free credit is one-per-person by
their rules; mass account creation may get accounts suspended.
