from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Normas APA - Revisión de tesis",
    description="Verifica el cumplimiento de las normas APA (7.a edición) en documentos .docx.",
    version="0.1.0",
)

app.include_router(router)

if FRONTEND_DIR.exists():
    class NoCacheStatic(StaticFiles):
        """En desarrollo no se cachean los estaticos: los cambios se ven al recargar."""

        def file_response(self, *args, **kwargs):
            response = super().file_response(*args, **kwargs)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return response

    app.mount("/static", NoCacheStatic(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        response = FileResponse(FRONTEND_DIR / "index.html")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
