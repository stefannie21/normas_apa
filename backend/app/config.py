from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# raiz del repositorio (backend/app/config.py -> ../../)
BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Cascada por defecto si el .env no define GEMINI_MODELS:
#   1) Gemini 3.8 Flash        (mejor calidad)
#   2) Gemini 3.5 Flash-Lite   (mas rapido)
#   3) Gemma 4 26B             (open source, ultimo recurso)
MODEL_CASCADE = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemma-4-26b-a4b-it",
]


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
    # lista de modelos separados por coma (cascada). Ej: GEMINI_MODELS=a,b,c
    gemini_models: str = ""
    # si es true, se usa la cascada de modelos en vez de un unico modelo
    ai_cascade: bool = True

    max_upload_mb: int = Field(default=25, ge=1, le=500)

    @property
    def resolved_key(self) -> str:
        return (self.ai_api_key or self.gemini_api_key or "").strip()

    @property
    def provider(self) -> str:
        """Normaliza el proveedor: 'google'/'gemini' -> 'gemini'.

        Si no se declara proveedor pero hay una clave o modelos de Gemini en el
        .env, se usa Gemini automaticamente (permite reutilizar un .env existente
        sin tocar la configuracion).
        """
        p = (self.ai_provider or "openai").strip().lower()
        if p in {"google", "gemini", "google-genai"}:
            return "gemini"
        # sin proveedor explicito: Gemini gana si hay credenciales de Gemini
        if p == "openai" and not self.ai_api_key and (
            self.gemini_api_key or self.gemini_models or self.gemini_model
        ):
            return "gemini"
        return p

    @property
    def resolved_model(self) -> str:
        if self.ai_model and self.ai_model != "gpt-4o-mini":
            return self.ai_model
        return self.gemini_model or self.ai_model

    @property
    def model_cascade(self) -> list[str]:
        """Lista de modelos a intentar en orden (cascada de respaldo).

        Prioridad:
          1. GEMINI_MODELS (lista separada por comas del .env)
          2. GEMINI_MODEL / AI_MODEL (un unico modelo)
          3. Cascada por defecto (solo para el proveedor Gemini)
        """
        listed = [
            m.strip() for m in (self.gemini_models or "").split(",") if m.strip()
        ]
        if listed:
            return listed
        explicit = (self.gemini_model or "").strip()
        if explicit:
            return [explicit]
        if self.ai_model and self.ai_model != "gpt-4o-mini":
            return [self.ai_model]
        if self.provider == "gemini":
            return list(MODEL_CASCADE)
        return [self.ai_model]

    @property
    def base_url(self) -> str:
        if self.ai_base_url:
            return self.ai_base_url.rstrip("/")
        if self.provider == "gemini":
            return GEMINI_BASE_URL
        return "https://api.openai.com/v1"

    @property
    def ai_available(self) -> bool:
        """Hay IA disponible si hay una clave, independientemente de AI_ENABLED.

        Antes exigia AI_ENABLED=true; ahora basta con que exista una clave en el
        .env, de modo que reutilizar una configuracion existente funciona sin
        pasos extra.
        """
        return bool(self.resolved_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()