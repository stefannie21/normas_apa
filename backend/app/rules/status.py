"""Modelo interno de resultado de validacion (seccion 6 del proyecto CEA).

Toda regla termina en uno de estos cuatro estados. Solo FAIL puede convertirse
en una observacion del informe: PASS, UNCERTAIN y NOT_APPLICABLE se registran
para auditoria pero NUNCA llegan al editor ni al informe Word.

    PASS            -> la condicion verificable se evaluo y se cumple.
    FAIL            -> existe un fragmento/propiedad del documento que demuestra
                       el incumplimiento de una norma APA identificable.
    UNCERTAIN       -> no hay evidencia suficiente (p. ej. no se puede modelar
                       un encabezado de pagina desde el .docx). No se comenta.
    NOT_APPLICABLE  -> la regla no corresponde al elemento analizado (no hay
                       tablas, no hay figuras, no existe lista de referencias...).

Esta distincion es la que permite reducir falsos positivos sin perder traza de
lo que el motor reviso.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


REPORTABLE_STATUSES = frozenset({ValidationStatus.FAIL})


@dataclass
class Assessment:
    rule_id: str
    status: ValidationStatus
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "status": self.status.value,
            "reason": self.reason,
        }


@dataclass
class ValidationLedger:
    """Traza de auditoria: que decidio cada regla y por que."""

    assessments: list[Assessment] = field(default_factory=list)

    def add(self, rule_id: str, status: ValidationStatus, reason: str = "") -> None:
        self.assessments.append(Assessment(rule_id, status, reason))

    def counts(self) -> dict[str, int]:
        out = {s.value: 0 for s in ValidationStatus}
        for a in self.assessments:
            out[a.status.value] += 1
        return out

    def to_dict(self) -> dict:
        return {
            "statuses": self.counts(),
            "assessments": [a.to_dict() for a in self.assessments],
        }
