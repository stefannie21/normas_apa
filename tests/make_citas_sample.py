"""Documento de prueba para la Fase 1: citas y referencias.

Incluye a proposito cada caso que las reglas nuevas deben detectar:
 CRUCE-001 cita sin referencia | CRUCE-002 referencia sin citar
 CRUCE-003 ano inconsistente  | REF-006 falta de cursiva
 REF-007 demasiados autores | REF-008 autor corporativo sin sigla
 CIT-005 cita de 3+ autores sin 'et al.' | CIT-006 cita en bloque entrecomillada
 CIT-008 'et al.' usado con una obra de 2 autores (prohibido en APA 7)
"""
from io import BytesIO

from docx import Document
from docx.shared import Inches, Pt


def build_citas_sample() -> bytes:
    doc = Document()

    for section in doc.sections:
        section.top_margin = section.bottom_margin = Inches(1)
        section.left_margin = section.right_margin = Inches(1)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 2.0
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.space_before = Pt(0)

    def body(text, indent=True):
        p = doc.add_paragraph(text)
        p.alignment = 0  # izquierda
        if indent:
            p.paragraph_format.first_line_indent = Inches(0.5)
        return p

    doc.add_heading("Marco teórico", level=1)

    # CRUCE-003: el ano de la cita no existe en referencias (la referencia es 2019)
    body("Como se observa en la literatura (Soto, 2021), el fenomeno es relevante.")
    # CRUCE-001: autor que no esta en la lista de referencias
    body("Otros autores coinciden en esto (Delgado, 2018), tal como se discutio antes.")
    # CIT-005: obra de 3+ autores citada sin 'et al.'
    body("La evidencia es contradictoria (Ramos, Soto, y Vega, 2019).")
    # CIT-008: obra de 2 autores citada con 'et al.' (incorrecto en APA 7)
    body("Diversos estudios lo confirman (Perez et al., 2023) en el mismo sentido.")
    # CRUCE-001: cita institucional sin referencia
    body("Segun la OMS (2020) la situacion mejoro, pero no se registro en la lista.")
    # CIT-004: cita textual sin numero de pagina
    body(
        'El autor afirma que "la educacion superior exige nuevas competencias" (Molina, 2019). '
        "Este enunciado resume su argumento principal."
    )
    # CIT-006: cita de 40+ palabras entrecomilladas (deberia ir en bloque)
    body(
        'Un analisis extenso demuestra que "la transformacion digital de la educacion superior '
        "no es un proceso opcional sino una necesidad estructural que reimagina la relacion "
        'entre docente y estudiante, y que exige politicas publicas coherentes con los nuevos '
        'ecosistemas digitales" (Ramos et al., 2019). Este es un caso claro.'
    )

    # ---------------- Referencias ----------------
    doc.add_paragraph()
    doc.add_heading("Referencias", level=1)

    def ref(texto, cursiva=None):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.5)
        p.paragraph_format.first_line_indent = Inches(-0.5)
        p.paragraph_format.line_spacing = 2.0
        if cursiva:
            for parte, it in zip(texto, cursiva):
                r = p.add_run(parte)
                r.italic = it
                r.font.size = Pt(12)
                r.font.name = "Times New Roman"
        else:
            r = p.add_run(texto)
            r.font.size = Pt(12)
            r.font.name = "Times New Roman"
        return p

    # CRUCE-002 + REF-006: sin citar en el cuerpo y sin cursiva
    ref("Zapata, R. (2019). Fundamentos de la investigacion educativa. Editorial Moderna.")
    # CRUCE-002: sin citar, con cursiva correcta (no debe dar REF-006)
    ref(
        [
            "Alvarez, N. (2018). ",
            "Metodologia de la investigacion cuantitativa",
            ". Revista de Educacion, 12(3), 45-67.",
        ],
        [False, True, False],
    )
    # CIT-005: referencia con 3 autores
    ref(
        "Ramos, L., Soto, M., y Vega, P. (2019). Aprendizaje digital en la universidad. "
        "Revista de Innovacion, 8(2), 11-29."
    )
    # CRUCE-003: Soto es de 2019 pero se cita como 2021
    ref("Soto, M. (2019). Metas educativas y evaluacion. Springer.")
    # REF-007: 21 autores (deben truncarse a 19 + ... + ultimo)
    autores = ", ".join(f"Autor{i}, A." for i in range(1, 22))
    ref(
        f"{autores} (2020). Un estudio con muchos autores. "
        "Revista Multidisciplinaria, 5(1), 1-10."
    )
    # REF-008: autor corporativo sin sigla en las citas
    ref("Organizacion Mundial de la Salud. (2020). Informe sobre salud mental. OMS.")
    # citada en el cuerpo, pero la cita textual no trae pagina
    ref("Molina, R. (2019). Competencias digitales en la educacion. Universidad Central.")
    # CIT-008: referencia de 2 autores que se cita con 'et al.' en el cuerpo
    ref("Perez, J., y Gomez, M. (2023). Analisis de la calidad educativa. Editorial Sur.")

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


if __name__ == "__main__":
    with open("tests/sample_citas.docx", "wb") as fh:
        fh.write(build_citas_sample())
    print("ok")