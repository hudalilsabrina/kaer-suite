# QUICKSTART — Kaer AI Suite

## 0. Isi paket

```
kaer-suite/
├── kaer_client.py    # HTTP client (OTP auth, key minting, chat)
├── kaer_farm.py      # batch registrar + 9router injector
├── main.py           # CLI
├── mailbox.py        # abstraksi provider inbox
├── tempmail_lol.py   # tempmail.lol client (default, publik)
├── tempmail.py       # client Tempik (opsional, untuk instance sendiri)
├── install.sh
├── requirements.txt
├── README.md
└── QUICKSTART.md
```

Tidak ada credential di dalam paket — `accounts.txt` / `keys.txt` sengaja kosong
dan otomatis dibuat saat kamu menjalankan farm sendiri.

## 1. Install

```bash
unzip kaer-suite.zip && cd kaer-suite
chmod +x install.sh main.py kaer_farm.py
./install.sh
```

Butuh Python 3.10+ (stdlib saja, tanpa dependency eksternal).

## 2. Konfigurasi

Default-nya pakai **tempmail.lol** — tanpa daftar, tanpa captcha, langsung jalan.

| Env | Default | Fungsi |
|---|---|---|
| `MAIL_PROVIDER` | `tempmail_lol` | `tempmail_lol` (publik) atau `tempik` (host sendiri) |
| `KAER_PROXY` | *(kosong)* | proxy keluar untuk signup. **Wajib** untuk volume — tanpa rotasi IP, server balas `429 signup_velocity` setelah ~3 akun per jaringan per hari |
| `KAER_BRIDGE` | `http://127.0.0.1:10801` | endpoint `/__new_session` untuk rotasi rotating-proxy |
| `9ROUTER_DB` | `/var/lib/9router/db/data.sqlite` | path database 9router |
| `TEMPIK_BASE` | — | hanya untuk `MAIL_PROVIDER=tempik` |
| `TEMPIK_DOMAINS` | — | domain untuk tempik, dipisah koma |

Pakai proxy:

```bash
export KAER_PROXY=http://127.0.0.1:10801
python3 kaer_farm.py -n 10
```

Pakai tempik sendiri:

```bash
export MAIL_PROVIDER=tempik
export TEMPIK_BASE=https://host-kamu/api
export TEMPIK_DOMAINS=domainmu.tld
python3 kaer_farm.py -n 10
```

## 3. Farm akun

```bash
python3 kaer_farm.py -n 10 --gap 4
```

Tiap akun menghasilkan `$10` free credit + satu key `kaer_live_…`, langsung
diinjeksi ke 9router di bawah prefix `kaer`.

## 4. Perintah lain

```bash
./main.py register          # 1 akun interaktif (tempmail.lol, tanpa proxy pun bisa)
./main.py login -e <email>  # minta OTP ulang, mint key baru
./main.py balance           # daftar akun + credit
./main.py models            # status live semua model (OK / off)
./main.py sync              # push semua key di accounts.txt ke 9router
./main.py test -m janus-1-pro
```

## 5. Pakai key-nya

```bash
curl https://api.kaer.ai/v1/chat/completions \
  -H "Authorization: Bearer kaer_live_..." \
  -H "Content-Type: application/json" \
  -d '{"model":"janus-1-pro","messages":[{"role":"user","content":"Halo"}]}'
```

Lewat 9router:

```bash
curl http://127.0.0.1:20127/v1/chat/completions \
  -H "Authorization: Bearer <9ROUTER_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"kaer/janus-1-pro","messages":[{"role":"user","content":"Halo"}]}'
```

## 6. Troubleshooting

| Gejala | Sebab | Solusi |
|---|---|---|
| `403 origin required` | header `Origin` hilang | pakai `kaer_client.py`, jangan request manual tanpa `Origin: https://api.kaer.ai` |
| `429 signup_velocity` | terlalu banyak akun dari 1 IP | rotasi proxy sebelum tiap signup |
| `503 model_unavailable` | model sedang di-pause upstream | ganti model; cek `./main.py models` |
| `no OTP` | inbox lambat / email ditolak | tempmail.lol kadang lambat; ulangi. Kalau tetap gagal, coba provider lain lewat `MAIL_PROVIDER` |
| key hilang | `secret` hanya tampil sekali | `./main.py login -e <email>` untuk mint key baru |

## 7. Batas Free tier

$10 credit (90 hari) · 20 req/menit · 2 stream bersamaan · maks 3 key aktif · hanya layanan `models`.
