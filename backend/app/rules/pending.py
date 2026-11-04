"""Registro de criterios normativos PENDIENTES DE VERIFICACION.

Regla del proyecto CEA (seccion 3): cuando exista incertidumbre normativa

    - No inventar una regla.
    - No generar un incumplimiento.
    - Registrar la regla como pendiente de verificacion.
    - Documentar la fuente y el criterio utilizado.

Ninguna entrada de este modulo produce un Finding. El registro se expone en
GET /api/rules/pending para que la decision sea auditable. La guia local
"Guia-Normas-APA-7ma-edicion (1).pdf" (elaborada con contenido de
normas-apa.org) se usa solo para identificar ambitos; la fuente normativa es
https://apastyle.apa.org/style-grammar-guidelines.

`criterion` explica por que NO se implemento una observacion. `source` es la
pagina oficial consultada (o la ausencia de ella).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

OFFICIAL_ROOT = "https://apastyle.apa.org/style-grammar-guidelines"
LOCAL_GUIDE = "inf/Guia-Normas-APA-7ma-edicion (1).pdf (normas-apa.org)"


@dataclass(frozen=True)
class PendingCriterion:
    id: str
    family: str
    topic: str
    guide_statement: str
    source: str
    criterion: str


PENDING: list[PendingCriterion] = [
    PendingCriterion(
        id="PEND-001",
        family="FORMAT",
        topic="Tamano de papel obligatorio (Carta 8.5 x 11 in)",
        guide_statement="La guia local exige papel Carta 21.59 x 27.94 cm.",
        source=f"{OFFICIAL_ROOT}/paper-format (no declara tamano de papel)",
        criterion=(
            "La pagina oficial de formato indica que se pueden usar los ajustes "
            "predeterminados del procesador y no fija un tamano de papel. No se "
            "puede demostrar una obligacion universal de Carta; marcar A4 como "
            "error seria un falso positivo. No se emite observacion."
        ),
    ),
    PendingCriterion(
        id="PEND-002",
        family="FORMAT",
        topic="Numeracion de paginas y running head",
        guide_statement=(
            "La guia local exige numero de pagina arriba a la derecha y, en "
            "trabajos profesionales, un running head de maximo 50 caracteres."
        ),
        source=(
            f"{OFFICIAL_ROOT}/paper-format/page-numbers-running-heads -> "
            "Page Not Found; /paper-format/page-numbers -> Page Not Found"
        ),
        criterion=(
            "No se obtuvo pagina oficial vigente. Ademas el parser DOCX no modela "
            "encabezados/pies (w:hdr, w:ftr, w:pgNum, fldChar), por lo que no hay "
            "propiedad verificable. Requiere ampliar el parser y confirmar la "
            "fuente oficial antes de crear una regla."
        ),
    ),
    PendingCriterion(
        id="PEND-003",
        family="FORMAT",
        topic="Excepciones completas de interlineado y sangria",
        guide_statement=(
            "La guia local enumera excepciones: portada, titulos, resumen, cita "
            "en bloque, tablas/figuras, referencias y apendices."
        ),
        source=f"{OFFICIAL_ROOT}/paper-format (pagina de indice)",
        criterion=(
            "El motor ya exime portada, tablas y referencias, pero no puede "
            "distinguir con evidencia todas las excepciones (p. ej. resumen o "
            "apendices sin estilo propio). Las zonas dudosas se dejan sin "
            "observacion en lugar de aplicar la regla general."
        ),
    ),
    PendingCriterion(
        id="PEND-004",
        family="CIT",
        topic="Numero de pagina obligatorio en TODAS las parafasis",
        guide_statement=(
            "La guia local afirma que siempre que se cita se debe informar autor, "
            "ano y numero de pagina."
        ),
        source=(
            f"{OFFICIAL_ROOT}/citations/quotations/page-numbers (exige pagina "
            "solo para citas textuales directas)"
        ),
        criterion=(
            "Conflicto entre la guia local y la documentacion oficial, que exige "
            "localizador para citas directas y no lo impone a la parafasis. Se "
            "respeta el criterio oficial y del proyecto: no se exige pagina a "
            "citas parafraseadas. Registrado, no implementado."
        ),
    ),
    PendingCriterion(
        id="PEND-005",
        family="CIT",
        topic="Citas secundarias ('citado en')",
        guide_statement="La guia local describe la cita secundaria.",
        source=f"{OFFICIAL_ROOT}/citations (pagina de indice)",
        criterion=(
            "No se verifico pagina oficial de detalle ni hay evidencia estructural "
            "suficiente para distinguir una cita secundaria de una cita narrativa "
            "cualquiera. Riesgo alto de falso positivo."
        ),
    ),
    PendingCriterion(
        id="PEND-006",
        family="CIT",
        topic="Comunicaciones personales",
        guide_statement="La guia local las describe como citas solo en el texto.",
        source=f"{OFFICIAL_ROOT}/references/missing-information",
        criterion=(
            "La pagina oficial confirma el formato y que NO llevan entrada en "
            "Referencias, pero identificarlas con fiabilidad exige distinguir "
            "nombres de personas de apellidos de autores. Se protege el caso en "
            "el cruce (no se exige referencia) sin crear una regla nueva."
        ),
    ),
    PendingCriterion(
        id="PEND-007",
        family="CIT",
        topic="Sufijos a, b, c para el mismo autor y ano",
        guide_statement="La guia local menciona obras del mismo autor y ano.",
        source=f"{OFFICIAL_ROOT}/citations/basic-principles/same-year-author (no consultada en detalle)",
        criterion=(
            "Se conoce la existencia de la pagina oficial pero no se verifico su "
            "contenido completo; implementar la regla sin ese contraste "
            "contradice la seccion 3 del proyecto."
        ),
    ),
    PendingCriterion(
        id="PEND-008",
        family="CIT",
        topic="Orden de multiples citas dentro de un mismo parentesis",
        guide_statement="La guia local muestra ejemplos de multiples obras.",
        source=f"{OFFICIAL_ROOT}/citations/basic-principles/multiple-works (no consultada en detalle)",
        criterion=(
            "El orden depende de criterios (alfabetico, cronologico para el mismo "
            "autor) que requieren contraste oficial y una segmentacion fiable de "
            "la bibliografia. No se genera observacion."
        ),
    ),
    PendingCriterion(
        id="PEND-009",
        family="REF",
        topic="Tipos de fuente: documentos legales y material audiovisual",
        guide_statement="La guia local no desarrolla estos tipos con detalle.",
        source=f"{OFFICIAL_ROOT}/references/examples (pagina de indice)",
        criterion=(
            "El motor reconoce articulo, libro, capitulo, tesis, informe y web. "
            "Aplicar una estructura unica a tipos no modelados produciria falsos "
            "positivos; se ampliara con tipologia verificada."
        ),
    ),
    PendingCriterion(
        id="PEND-010",
        family="REF",
        topic="Referencias duplicadas",
        guide_statement="No consta en la guia local.",
        source="Sin pagina oficial consultada",
        criterion=(
            "No se verifico fundamento oficial explicito ni se definio un criterio "
            "de igualdad seguro (variantes de DOI, mayusculas, s.f.). Regla no "
            "implementada."
        ),
    ),
    PendingCriterion(
        id="PEND-011",
        family="TABLE / FIG",
        topic="Notas generales, especificas y de probabilidad obligatorias",
        guide_statement="La guia local las describe como componentes.",
        source=(
            f"{OFFICIAL_ROOT}/tables-figures/tables y .../figures: "
            "'Include table notes only as needed' / 'Include figure notes only as needed'"
        ),
        criterion=(
            "La fuente oficial es explicita: las notas son opcionales. NO se crea "
            "ninguna regla que las exija. Registro documental de una NO-regla."
        ),
    ),
    PendingCriterion(
        id="PEND-012",
        family="FIG",
        topic="Umbral de atribucion de derechos de autor",
        guide_statement=(
            "La guia local exige atribucion para figuras reproducidas o adaptadas "
            "y la exime para elaboracion propia."
        ),
        source=f"{OFFICIAL_ROOT}/tables-figures/figures (menciona copyright attribution en las notas)",
        criterion=(
            "Solo se valida cuando el propio documento declara de forma explicita "
            "'Adaptado de' / 'Reproducido de' / 'Tomado de'. Sin esa declaracion "
            "no hay evidencia de que la figura sea ajena: NOT_APPLICABLE, nunca "
            "error. El umbral legal completo sigue pendiente de contraste."
        ),
    ),
    PendingCriterion(
        id="PEND-013",
        family="FIG",
        topic="Leyenda obligatoria",
        guide_statement="La guia local la enumera entre los componentes.",
        source=f"{OFFICIAL_ROOT}/tables-figures/figures: 'A figure legend, or key, if present...'",
        criterion="La leyenda es condicional ('if present'). No se exige.",
    ),
    PendingCriterion(
        id="PEND-014",
        family="DOC",
        topic="Resumen, Abstract, palabras clave y portada como obligatorios",
        guide_statement="La guia local describe la estructura del trabajo.",
        source=f"{OFFICIAL_ROOT}/paper-format (distingue trabajos estudiantiles y profesionales)",
        criterion=(
            "Estos elementos dependen del tipo de trabajo y de la institucion. "
            "Exigirlos en todos los documentos convertiria elementos opcionales "
            "en errores. Ademas la seccion 2 excluye perfiles universitarios."
        ),
    ),
    PendingCriterion(
        id="PEND-015",
        family="HEAD",
        topic="Numeracion de capitulos de tesis",
        guide_statement="La guia local no contempla capitulos de tesis.",
        source=f"{OFFICIAL_ROOT}/paper-format/headings: 'Do not label headings with numbers or letters'",
        criterion=(
            "Existe conflicto aparente con la numeracion institucional de "
            "capitulos. El proyecto excluye plantillas universitarias en esta "
            "etapa, por lo que los titulos de capitulo se tratan como "
            "UNCERTAIN/NOT_APPLICABLE y no se marcan como error."
        ),
    ),
    PendingCriterion(
        id="PEND-016",
        family="STYLE",
        topic="Numeros, porcentajes, unidades, abreviaturas, comillas, listas",
        guide_statement="La guia local dedica apartados a estilo de redaccion.",
        source=f"{OFFICIAL_ROOT}/style-grammar-guidelines (paginas de detalle no contrastadas)",
        criterion=(
            "Son preferencias de redaccion academicas en gran parte; sin una "
            "condicion verificable y una excepcion documentada se corre un riesgo "
            "alto de falsos positivos. No se implementan reglas de esta familia."
        ),
    ),
]


def as_dicts() -> list[dict]:
    return [asdict(p) for p in PENDING]


def by_family() -> dict[str, int]:
    out: dict[str, int] = {}
    for p in PENDING:
        out[p.family] = out.get(p.family, 0) + 1
    return out
