from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from backend.app.rules.status import ValidationStatus

if TYPE_CHECKING:
    from backend.app.services.docx_parser import ParsedDocument


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Category(str, Enum):
    FORMATO = "Formato de página y texto"
    TITULOS = "Títulos y jerarquía"
    CITAS = "Citas en el texto"
    REFERENCIAS = "Lista de referencias"
    TABLAS = "Tablas"
    FIGURAS = "Figuras"
    ESTRUCTURA = "Estructura del documento"
    ESTILO = "Estilo APA"
    GENERAL = "Aspectos generales"


@dataclass
class Finding:
    """Hallazgo uniforme del motor (seccion 8 del proyecto CEA).

    Se conservan TODAS las claves historicas (rule_id ... extra) para no romper
    el editor, los marcadores, el informe Word ni las reglas existentes. Las
    cuatro nuevas (title, page, evidence, validation_status) son aditivas: los
    consumidores actuales ignoran las claves que no conocen.

    validation_status solo puede ser FAIL en un hallazgo entregado. Los estados
    PASS / UNCERTAIN / NOT_APPLICABLE se registran en el ValidationLedger y
    la puerta de precision descarta cualquier hallazgo que los traiga.
    """

    rule_id: str
    category: Category
    severity: Severity
    message: str
    suggestion: str = ""
    paragraph_index: int | None = None
    location: str = ""
    excerpt: str = ""
    extra: dict = field(default_factory=dict)

    # -- campos uniformes nuevos -------------------------------------------
    title: str = ""
    page: int | None = None
    evidence: str = ""
    validation_status: ValidationStatus = ValidationStatus.FAIL
    anchor: dict | None = None
    origin: str = "apa7"

    def __post_init__(self) -> None:
        # Permite que una regla pase el estado como cadena sin romper to_dict().
        if not isinstance(self.validation_status, ValidationStatus):
            try:
                self.validation_status = ValidationStatus(
                    str(self.validation_status).strip().upper()
                )
            except ValueError:
                # Un estado desconocido NUNCA puede convertirse en un error.
                self.validation_status = ValidationStatus.UNCERTAIN

    def to_dict(self) -> dict:
        return {
            # compatibilidad: claves historicas, mismo orden
            "rule_id": self.rule_id,
            "category": self.category.value if hasattr(self.category, "value") else str(self.category),
            "severity": self.severity.value if hasattr(self.severity, "value") else str(self.severity),
            "message": self.message,
            "suggestion": self.suggestion,
            "paragraph_index": self.paragraph_index,
            "location": self.location,
            "excerpt": self.excerpt,
            "extra": self.extra,
            # estructura uniforme nueva
            "title": self.title,
            "page": self.page,
            "evidence": self.evidence,
            "validation_status": self.validation_status.value,
            "anchor": self.anchor,
            "origin": self.origin,
        }


@dataclass
class Rule:
    id: str
    name: str
    category: Category
    description: str
    default_severity: Severity = Severity.WARNING
    origin: str = "apa7"
    # Fundamento normativo y excepciones documentadas (auditoria, /api/rules).
    norm_source: str = ""
    exceptions: str = ""

    def check(self, document: "ParsedDocument") -> list[Finding]:  # pragma: no cover
        raise NotImplementedError

    def finding(self, message: str, **kwargs) -> Finding:
        kwargs.setdefault("severity", self.default_severity)
        kwargs.setdefault("title", self.name)
        kwargs.setdefault("origin", self.origin)
        return Finding(
            rule_id=self.id,
            category=self.category,
            message=message,
            **kwargs,
        )

    def uncertain(self, reason: str, **kwargs) -> Finding:
        """Registra evidencia insuficiente: NUNCA llega al informe."""
        kwargs.pop("validation_status", None)
        return self.finding(
            reason,
            validation_status=ValidationStatus.UNCERTAIN,
            **kwargs,
        )
