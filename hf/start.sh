#!/usr/bin/env bash
# Start the Ollama-compatible shim on 11434, then the app on the platform's port.
#
# Render injects $PORT; Hugging Face Spaces expect 7860. Honouring $PORT with a
# 7860 fallback makes the same image work on both without a rebuild.
set -e

python -m uvicorn ollama_shim:app --host 127.0.0.1 --port 11434 --log-level warning &

for _ in $(seq 1 40); do
  if python -c "import socket,sys; s=socket.socket(); sys.exit(s.connect_ex(('127.0.0.1',11434)))" 2>/dev/null; then
    break
  fi
  sleep 0.5
done

exec python -m uvicorn server:app --host 0.0.0.0 --port "${PORT:-7860}"
