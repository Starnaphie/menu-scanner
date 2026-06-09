#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env if present (does not override variables already set in the shell)
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -o allexport
  source "$SCRIPT_DIR/.env"
  set +o allexport
fi

# Activate the virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# --- Eval Pipeline ---
# Usage: ./run.sh eval
if [[ "${1:-}" == "eval" ]]; then
  echo "=== Running Eval Pipeline ==="
  cd "$SCRIPT_DIR"

  STEPS=(
    "python eval/match_cases.py"
    "python eval/score_cases.py"
    "python eval/compute_metrics.py"
    "python eval/run_eval.py"
  )

  for i in "${!STEPS[@]}"; do
    step_num=$((i + 1))
    cmd="${STEPS[$i]}"
    script_name="${cmd##* }"
    if ! $cmd; then
      echo "FAILED at step $step_num: $(basename "$script_name")"
      exit 1
    fi
  done

  echo "=== Eval Complete ==="
  exit 0
fi

# --- Server ---
# Verify the API key is present before starting the server
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "Error: OPENAI_API_KEY is not set." >&2
  echo "Add it to .env:  echo 'OPENAI_API_KEY=sk-...' >> .env" >&2
  exit 1
fi

echo "Starting Menu Scanner API on http://localhost:8000"
echo "Frontend: open frontend/index.html in your browser"
echo ""

cd "$SCRIPT_DIR/backend"
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
