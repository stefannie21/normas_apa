from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.services.docx_parser import ParsedDocument


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Category(str, Enum):
    FORMATO = "Formato de pagina y texto"
    TITULOS = "Titulos y jerarquia"
    CITAS = "Citas en el texto"
    REFERENCIAS = "Lista de referencias"
    GENERAL = "Aspectos generales"


@dataclass
class Finding:
    rule_id: str
    category: Category
    severity: Severity
    message: str
    suggestion: str = ""
    paragraph_index: int | None = None
    location: str = ""
    excerpt: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "suggestion": self.suggestion,
            "paragraph_index": self.paragraph_index,
            "location": self.location,
            "excerpt": self.excerpt,
            "extra": self.extra,
        }


@dataclass
class Rule:
    id: str
    name: str
    category: Category
    description: str
    default_severity: Severity = Severity.WARNING

    def check(self, document: "ParsedDocument") -> list[Finding]:  # pragma: no cover
        raise NotImplementedError

    def finding(self, message: str, **kwargs) -> Finding:
        kwargs.setdefault("severity", self.default_severity)
        return Finding(
            rule_id=self.id,
            category=self.category,
            message=message,
            **kwargs,
        )
