"""Conversion fiel .docx -> .pdf usando Microsoft Word (COM).

El visor HTML recompone el documento con sus propias reglas de paginacion; eso
permite editar y marcar hallazgos, pero nunca reproduce al 100% el salto de
pagina de Word. Para la revision visual fiel se ofrece esta conversion: Word
abre el archivo original y lo guarda como PDF, de modo que el contenido no se
mueve.

Solo funciona en Windows con Microsoft Word instalado. Si Word no esta
disponible, la funcion devuelve un error explicito y el frontend sigue usando el
visor HTML.
"""
from __future__ import annotations

import logging
import os
import tempfile

logger = logging.getLogger(__name__)

WORD_FORMAT_PDF = 17  # wdFormatPDF


class PdfConversionError(RuntimeError):
    """No se pudo convertir el documento a PDF."""


def is_available() -> bool:
    """True si hay Microsoft Word instalado (COM disponible)."""
    try:
        import win32com.client  # noqa: F401
    except Exception:
        return False
    return os.name == "nt"


def convert_docx_to_pdf(data: bytes) -> bytes:
    """Convierte el .docx a PDF con Word y devuelve los bytes del PDF."""
    if not data:
        raise PdfConversionError("El documento esta vacio.")
    if os.name != "nt":
        raise PdfConversionError("La conversion a PDF solo esta disponible en Windows.")

    try:
        import pythoncom
        import win32com.client
    except Exception as exc:  # pragma: no cover - depende del entorno
        raise PdfConversionError(
            "Falta pywin32 para convertir con Word. Instalar: pip install pywin32"
        ) from exc

    tmp_dir = tempfile.mkdtemp(prefix="apa_pdf_")
    docx_path = os.path.join(tmp_dir, "documento.docx")
    pdf_path = os.path.join(tmp_dir, "documento.pdf")
    with open(docx_path, "wb") as fh:
        fh.write(data)

    word = None
    doc = None
    try:
        pythoncom.CoInitialize()
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(
            docx_path,
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
        )
        doc.SaveAs(pdf_path, FileFormat=WORD_FORMAT_PDF)
    except Exception as exc:  # pragma: no cover - depende del entorno
        logger.warning("Word no pudo convertir el documento: %s", exc)
        raise PdfConversionError(f"Word no pudo convertir el documento: {exc}") from exc
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

    if not os.path.exists(pdf_path):
        raise PdfConversionError("Word no genero el PDF.")
    with open(pdf_path, "rb") as fh:
        pdf_bytes = fh.read()

    for path in (docx_path, pdf_path):
        try:
            os.remove(path)
        except OSError:
            pass
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass
    return pdf_bytes
