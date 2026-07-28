# AI Career Co-Pilot — Hugging Face Space (Docker SDK)
#
# Build context is the repository root, so paths below are repo-relative.
# Stage 1 compiles the React app, stage 2 builds whisper.cpp, and stage 3 runs
# the API, the UI and the Ollama-compatible shim on the single port a Space
# exposes.
#
# Voice works here: whisper.cpp is compiled for Linux and Piper's Linux build is
# downloaded, then WHISPER_BIN / PIPER_BIN are pointed at them. The application
# code is untouched — those paths are settings (see backend/app/config.py), and
# stt.py / tts.py invoke the binaries with the same flags on every platform.

# ---------- stage 1: build the frontend ----------
FROM node:20-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- stage 2: build whisper.cpp ----------
FROM debian:bookworm-slim AS whisper
RUN apt-get update && apt-get install -y --no-install-recommends \
        git build-essential cmake ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git \
 && cd whisper.cpp \
 && cmake -B build -DCMAKE_BUILD_TYPE=Release \
 && cmake --build build --config Release -j"$(nproc)"
# ggml-tiny.en is ~75 MB and fast enough for short spoken answers on CPU.
RUN curl -fsSL -o /src/ggml-tiny.en.bin \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin

# ---------- stage 3: runtime ----------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libgomp1 is whisper.cpp's OpenMP runtime; curl/tar fetch the Piper release.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ---- Piper (text-to-speech): prebuilt Linux binary + the Amy voice ----
RUN mkdir -p /opt/piper \
 && curl -fsSL -o /tmp/piper.tar.gz \
      https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz \
 && tar -xzf /tmp/piper.tar.gz -C /opt \
 && rm /tmp/piper.tar.gz \
 && curl -fsSL -o /opt/piper/en_US-amy-medium.onnx \
      https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx \
 && curl -fsSL -o /opt/piper/en_US-amy-medium.onnx.json \
      https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json

# ---- whisper.cpp (speech-to-text) from stage 2 ----
RUN mkdir -p /opt/whisper
COPY --from=whisper /src/whisper.cpp/build/bin/whisper-cli /opt/whisper/whisper-cli
COPY --from=whisper /src/ggml-tiny.en.bin /opt/whisper/ggml-tiny.en.bin

# Spaces run as uid 1000 with only $HOME writable, so keep state out of /app.
ENV HOME=/home/user \
    DB_PATH=/home/user/data/career_copilot.db \
    AUDIO_TMP_DIR=/home/user/data/audio_tmp \
    PROMPTS_DIR=/app/prompts \
    OLLAMA_URL=http://127.0.0.1:11434 \
    FRONTEND_DIST=/app/frontend/dist \
    PYTHONPATH=/app/backend \
    WHISPER_BIN=/opt/whisper/whisper-cli \
    WHISPER_MODEL=/opt/whisper/ggml-tiny.en.bin \
    PIPER_BIN=/opt/piper/piper \
    PIPER_VOICE=/opt/piper/en_US-amy-medium.onnx \
    LD_LIBRARY_PATH=/opt/piper

# bge-small (~33 MB, 384 dims) rather than bge-base (~110 MB, 768 dims): Render's
# free tier caps memory at 512 MB, shared with whisper and Piper. EMBED_DIM is a
# setting in app/config.py, so the sqlite-vec table follows automatically.
ENV HF_EMBED_MODEL=BAAI/bge-small-en-v1.5 \
    EMBED_DIM=384

COPY backend/requirements.txt /tmp/requirements.txt
COPY hf/requirements-hf.txt /tmp/requirements-hf.txt
RUN pip install -r /tmp/requirements.txt -r /tmp/requirements-hf.txt

COPY backend/ /app/backend/
COPY prompts/ /app/prompts/
COPY hf/ollama_shim.py hf/server.py hf/start.sh /app/
COPY --from=ui /ui/dist /app/frontend/dist

# Bake the embedding model into the image so a cold start does not download it.
RUN python -c "import os; from fastembed import TextEmbedding; TextEmbedding(model_name=os.environ['HF_EMBED_MODEL'])" \
 && chmod +x /app/start.sh /opt/whisper/whisper-cli /opt/piper/piper \
 && mkdir -p /home/user/data/audio_tmp \
 && chown -R 1000:1000 /home/user /app

USER 1000

EXPOSE 7860
CMD ["/app/start.sh"]
