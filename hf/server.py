"""Hugging Face Space entrypoint: serves the built UI and the API together.

On a laptop the Vite dev server hosts the UI on :5173 and proxies /api and
/health to uvicorn on :8000. A Space exposes exactly one port, so here FastAPI
serves the compiled frontend itself and the API keeps its existing routes.

`app/main.py` is imported unchanged — the static mount is added from the
outside. Mounting at "/" last is safe: Starlette matches routes in order, and
every API router was registered during the import above, so they win.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.main import app  # noqa: E402  (import order is deliberate)

DIST = Path(os.environ.get("FRONTEND_DIST", "/app/frontend/dist"))

# Optional shared password. Spaces are public, and this app has no login of its
# own, so without this anyone who finds the URL can read uploaded resumes.
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
APP_USER = os.environ.get("APP_USER", "examiner")


if APP_PASSWORD:

    @app.middleware("http")
    async def basic_auth(request, call_next):
        # /health stays open so uptime checks work without credentials.
        if request.url.path == "/health":
            return await call_next(request)

        header = request.headers.get("authorization", "")
        expected = base64.b64encode(f"{APP_USER}:{APP_PASSWORD}".encode()).decode()
        if header == f"Basic {expected}":
            return await call_next(request)

        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="AI Career Co-Pilot"'},
            content="Authentication required",
        )


if DIST.is_dir():
    # app/main.py registers GET "/" as a JSON service banner. Starlette matches
    # routes in registration order, so that banner would win over the mount below
    # and a visitor opening the site would get JSON instead of the app. Drop it
    # here (the banner stays reachable at /api) and keep every other API route.
    app.router.routes = [
        route
        for route in app.router.routes
        if not (getattr(route, "path", None) == "/" and "GET" in getattr(route, "methods", set()))
    ]

    @app.get("/api", tags=["system"], summary="Service banner")
    async def api_banner() -> dict[str, str]:
        return {"app": app.title, "version": app.version, "docs": "/docs", "health": "/health"}

    # html=True makes unknown paths fall back to index.html, which the SPA needs
    # for client-side routing and deep links.
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="ui")
