"""Central configuration for AI Career Co-Pilot.

Every tunable value lives here so nothing is hard-coded across the codebase.
Any setting can be overridden with an environment variable or a `.env` file
placed in `backend/` — see `.env.example`.

Design note for the viva: the model name is a *setting*, not a constant, which
is what lets the app swap models per hardware tier (SOW Section 11, risk register)
without touching any feature code.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# career-copilot/backend/app/config.py -> parents[0]=app, [1]=backend, [2]=career-copilot
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings, loaded from environment / .env with sane defaults."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Identity ---
    APP_NAME: str = "AI Career Co-Pilot"
    APP_VERSION: str = "0.1.0"

    # --- Server (SOW Section 6.4: bind to loopback only, never 0.0.0.0) ---
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # --- Ollama (local LLM runtime) ---
    # 127.0.0.1 rather than "localhost": on Windows, "localhost" can resolve to
    # IPv6 ::1 first and add a connection delay on every request.
    OLLAMA_URL: str = "http://127.0.0.1:11434"

    # Name of the remote provider answering chat, when one is in use. Empty means
    # generation runs locally through Ollama, which is the default everywhere
    # except the hosted deployment — the Ollama-compatible shim sets it so the UI
    # can say where inference actually happens instead of claiming "local"
    # unconditionally. Embeddings, voice and storage stay local either way.
    INFERENCE_PROVIDER: str = ""

    # Default chat model. 3B keeps the app usable on 8 GB RAM with no GPU.
    # Never raise this above 4B as a default without re-checking the hardware.
    CHAT_MODEL: str = "llama3.2:3b"

    # Question-bank generation uses a smaller, faster model: on an 8 GB CPU box a
    # 3B model needs a couple of minutes for a full bank, and the questions are
    # templated and grounded enough that a 1B model produces usable output in
    # ~30 s. Answer scoring stays on CHAT_MODEL, where quality matters more.
    QUESTION_MODEL: str = "llama3.2:1b"

    # Embedding model used by the RAG pipeline (SOW Section 6.2).
    EMBED_MODEL: str = "nomic-embed-text"

    # Vector width of EMBED_MODEL. nomic-embed-text emits 768 floats; the
    # sqlite-vec table is declared float[EMBED_DIM], so changing the embedding
    # model means dropping that table and re-embedding.
    EMBED_DIM: int = 768

    # --- Generation parameters (SOW Section 11: low temp for scoring consistency) ---
    TEMPERATURE_SCORING: float = 0.2  # resume critique, rubric scoring, gap analysis
    TEMPERATURE_CREATIVE: float = 0.7  # bullet rewrites, outreach drafts, roadmaps

    # --- Timeouts (seconds) ---
    HEALTH_TIMEOUT: float = 3.0  # quick liveness probe, must not hang the UI
    OLLAMA_TIMEOUT: float = 120.0  # generation on CPU-only hardware is slow

    # Structuring a whole resume emits far more tokens than a chat reply, and at
    # roughly 3 tokens/second on this hardware that overruns OLLAMA_TIMEOUT.
    STRUCTURE_TIMEOUT: float = 600.0

    # --- Uploads ---
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5 MB; a text resume is far smaller
    MAX_AUDIO_BYTES: int = 25 * 1024 * 1024  # a couple of minutes of 16 kHz WAV

    # --- Voice: whisper.cpp (STT) and Piper (TTS) ---
    # Optional feature. When the binaries/models below are absent the app runs in
    # text-only mode (SOW Section 7: voice degrades gracefully). Paths default
    # under voice/ (git-ignored) and are overridable via .env for other layouts.
    VOICE_DIR: Path = PROJECT_ROOT / "voice"
    WHISPER_BIN: Path = PROJECT_ROOT / "voice" / "whisper" / "whisper-cli.exe"
    WHISPER_MODEL: Path = PROJECT_ROOT / "voice" / "whisper" / "ggml-tiny.en.bin"
    PIPER_BIN: Path = PROJECT_ROOT / "voice" / "piper" / "piper.exe"
    # A warm female voice for the greeting and voice mode. Swap the filename to
    # any other installed Piper voice (both the .onnx and .onnx.json must exist).
    PIPER_VOICE: Path = PROJECT_ROOT / "voice" / "piper" / "en_US-amy-medium.onnx"

    STT_TIMEOUT: float = 120.0  # transcribing a short answer on CPU
    TTS_TIMEOUT: float = 60.0

    # --- Storage ---
    DB_PATH: Path = PROJECT_ROOT / "data" / "career_copilot.db"
    PROMPTS_DIR: Path = PROJECT_ROOT / "prompts"
    AUDIO_TMP_DIR: Path = PROJECT_ROOT / "data" / "audio_tmp"

    # --- Frontend origins allowed to call the API (Vite dev server) ---
    CORS_ORIGINS: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    @property
    def database_url(self) -> str:
        """SQLAlchemy connection string for the local SQLite file."""
        return f"sqlite:///{self.DB_PATH}"

    def ensure_dirs(self) -> None:
        """Create the directories the app writes to, if they do not exist yet."""
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        self.AUDIO_TMP_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached, so .env is read once)."""
    return Settings()
