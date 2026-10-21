from __future__ import annotations

from backend.app.rules import (
    cite_format,
    citations,
    formatting,
    headings,
    matching,
    ref_format,
    references,
    tables,
)
from backend.app.rules.base import Rule

ALL_RULES: list[Rule] = [
    *formatting.RULES,
    *headings.RULES,
    *citations.RULES,
    *references.RULES,
    *ref_format.RULES,
    *cite_format.RULES,
    *matching.RULES,
    *tables.RULES,
]


def get_rules() -> list[Rule]:
    return list(ALL_RULES)
