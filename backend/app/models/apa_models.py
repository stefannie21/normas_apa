"""Modelos Pydantic estrictos para hallazgos y anclajes (Fase 3 y 4 del proyecto CEA).

Garantiza validación estricta de esquemas, offsets válidos, evidencia comprobable,
hashes SHA-256 y compatibilidad con el motor de reglas existente.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator


EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class AnchorModel(BaseModel):
    """Metadatos de anclaje de una observación a un fragmento exacto del documento."""

    document_id: str = Field(..., description="Identificador único del documento")
    document_version: str = Field(..., description="Versión del documento analizado")
    paragraph_id: str = Field(..., description="Identificador único y persistente del párrafo")
    paragraph_index: int = Field(..., ge=0, description="Índice secuencial 0-based del párrafo")
    paragraph_hash: str = Field(default="", description="Hash SHA-256 del texto completo del párrafo")
    start_offset: int = Field(..., ge=0, description="Posición inicial del fragmento dentro del párrafo")
    end_offset: int = Field(..., ge=0, description="Posición final (no inclusiva) del fragmento")
    matched_text: str = Field(..., min_length=1, description="Texto exacto del fragmento señalado")
    fragment_hash: str = Field(..., min_length=8, description="Hash SHA-256 del fragmento normalizado")
    context_before: str = Field(default="", description="Contexto textual previo para desambiguación")
    context_after: str = Field(default="", description="Contexto textual posterior para desambiguación")
    run_indices: list[int] = Field(default_factory=list, description="Índices de runs en python-docx abarcados")
    is_ambiguous: bool = Field(default=False, description="True si existen múltiples coincidencias idénticas")
    is_obsolete: bool = Field(default=False, description="True si el fragmento ya no existe en la versión actual")

    @model_validator(mode="after")
    def validate_offsets(self) -> AnchorModel:
        if self.start_offset >= self.end_offset:
            raise ValueError(
                f"start_offset ({self.start_offset}) debe ser menor que end_offset ({self.end_offset})"
            )
        if self.fragment_hash == EMPTY_SHA256:
            raise ValueError(
                "fragment_hash no puede ser el hash de una cadena vacía (e3b0c442...). "
                "El anclaje debe vincularse a un fragmento de texto real o elemento comprobable."
            )
        return self


class EvidenceModel(BaseModel):
    """Evidencia comprobable del incumplimiento."""

    original_text: str = Field(..., min_length=1, description="Fragmento exacto extraído del documento")
    reason: str = Field(..., min_length=1, description="Fundamento normativo de la observación")


class StructuredFindingModel(BaseModel):
    """Hallazgo estructurado conforme a la especificación de CEA Group."""

    task_id: str = Field(..., description="Identificador de la tarea que generó el hallazgo")
    rule_id: str = Field(..., description="Código oficial de la regla (ej. CIT-001, HEAD-004)")
    category: str = Field(..., description="Categoría de la regla (Formato, Títulos, Citas, Referencias, Tablas)")
    status: str = Field(default="FAIL", description="Solo FAIL es reportable al editor")
    severity: str = Field(default="warning", description="Gravedad: error, warning, info")
    title: str = Field(..., min_length=1, description="Título breve y claro de la observación")
    message: str = Field(..., min_length=1, description="Descripción detallada del incumplimiento")
    suggestion: str = Field(default="", description="Propuesta de corrección")
    evidence: EvidenceModel = Field(..., description="Evidencia textual y fundamento")
    anchor: AnchorModel = Field(..., description="Anclaje exacto en el documento")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Nivel de confianza entre 0 y 1")
    extra: dict[str, Any] = Field(default_factory=dict, description="Metadatos complementarios")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        s = v.strip().upper()
        if s not in {"FAIL", "PASS", "UNCERTAIN", "NOT_APPLICABLE"}:
            raise ValueError(f"Estado de validación inválido: {v}")
        return s

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        s = v.strip().lower()
        if s not in {"error", "warning", "info"}:
            raise ValueError(f"Severidad inválida: {v}")
        return s

    def to_legacy_finding_dict(self) -> dict[str, Any]:
        """Convierte al diccionario compatible con el Finding histórico del editor."""
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "suggestion": self.suggestion,
            "paragraph_index": self.anchor.paragraph_index,
            "location": f"Párrafo {self.anchor.paragraph_index + 1}",
            "excerpt": self.anchor.matched_text,
            "extra": {
                **self.extra,
                "task_id": self.task_id,
                "confidence": self.confidence,
                "anchor": self.anchor.model_dump(),
            },
            "title": self.title,
            "page": None,
            "evidence": self.evidence.original_text,
            "validation_status": self.status,
            "anchor": self.anchor.model_dump(),
        }
