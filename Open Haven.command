#!/bin/zsh

unsetopt BG_NICE

cd "$(dirname "$0")"

ensure_setup() {
  if [[ -x ".venv/bin/python" ]] && .venv/bin/python -c 'import streamlit' >/dev/null 2>&1; then
    return 0
  fi

  if [[ ! -x ".venv/bin/python" ]]; then
    echo "Haven has not been set up yet. Running setup first…"
  else
    echo "Haven setup is incomplete. Running setup again…"
  fi

  HAVEN_AUTOMATED_SETUP=1 "./Setup Haven.command"

  if [[ ! -x ".venv/bin/python" ]] || ! .venv/bin/python -c 'import streamlit' >/dev/null 2>&1; then
    echo
    echo "Haven setup did not complete successfully."
    read "?Press Return to close…"
    return 1
  fi
}

ensure_setup || exit 1

.venv/bin/python -m streamlit run ui/app.py --server.headless true &
STREAMLIT_PID=$!

sleep 3
if kill -0 "$STREAMLIT_PID" >/dev/null 2>&1; then
  open "http://localhost:8501"
fi

wait "$STREAMLIT_PID"
EXIT_CODE=$?
if [[ $EXIT_CODE -ne 0 ]]; then
  echo
  echo "Haven closed with an error."
  read "?Press Return to close…"
fi

exit $EXIT_CODE
