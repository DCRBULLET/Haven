#!/bin/zsh

cd "$(dirname "$0")"

AUTO_SETUP="${HAVEN_AUTOMATED_SETUP:-0}"

PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  fi
done

if [[ -z "$PYTHON_BIN" ]]; then
  echo "Haven requires Python 3.10 or newer."
  echo "Install a compatible Python 3 release, then run this setup again."
  read "?Press Return to close…"
  exit 1
fi

echo "Using $($PYTHON_BIN --version 2>&1)"
"$PYTHON_BIN" -m venv .venv || exit 1
.venv/bin/python -m pip install --upgrade pip || exit 1
.venv/bin/python -m pip install -r requirements.txt || exit 1

echo "Haven is ready. Opening Haven…"
if [[ "$AUTO_SETUP" != "1" ]]; then
  read "?Press Return to close…"
fi
