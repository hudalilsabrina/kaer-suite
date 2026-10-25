#!/usr/bin/env bash
set -e
echo "=== Kaer Suite install ==="
python3 -m pip install -q --upgrade urllib3 >/dev/null 2>&1 || true
chmod +x main.py kaer_farm.py
mkdir -p data
touch accounts.txt keys.txt
echo "Done. Try:  python3 kaer_farm.py -n 5"
