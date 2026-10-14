from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# raiz del repositorio (backend/app/config.py -> ../../)
BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class Settings(BaseSettings):
    # ruta absoluta: si uvicorn se arranca desde otro directorio, el .env sigue leyendose
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore"
    )

    ai_enabled: bool = False
    ai_provider: str = "openai"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_base_url: str = ""
    # alias en cascada: si no hay AI_API_KEY se prueban estas (permite reutilizar
    # un .env ya existente para otro proyecto)
    gemini_api_key: str = ""
    gemini_model: str = ""

    max_upload_mb: int = Field(default=25, ge=1, le=500)

    @property
    def resolved_key(self) -> str:
        return (self.ai_api_key or self.gemini_api_key or "").strip()

    @property
    def provider(self) -> str:
        """Normaliza el proveedor: 'google'/'gemini' -> 'gemini'."""
        p = (self.ai_provider or "openai").strip().lower()
        if p in {"google", "gemini", "google-genai"}:
            return "gemini"
        return p

    @property
    def resolved_model(self) -> str:
        if self.ai_model and self.ai_model != "gpt-4o-mini":
            return self.ai_model
        return self.gemini_model or self.ai_model

    @property
    def base_url(self) -> str:
        if self.ai_base_url:
            return self.ai_base_url.rstrip("/")
        if self.provider == "gemini":
            return GEMINI_BASE_URL
        return "https://api.openai.com/v1"

    @property
    def ai_available(self) -> bool:
        return self.ai_enabled and bool(self.resolved_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()