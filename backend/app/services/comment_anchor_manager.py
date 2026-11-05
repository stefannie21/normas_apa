"""Sistema de anclaje preciso de observaciones dentro del documento (Fases 4, 5 y 6).

Responsabilidades:
1. Identificación persistente de párrafos (w14:paraId / hash determinista).
2. Mapeo bidireccional: Texto de párrafo <-> Runs de Word <-> Offsets numéricos.
3. Hash criptográfico SHA-256 de fragmentos y párrafos para verificar integridad.
4. Resolución y recuperación de anclajes jerárquica:
   - Coincidencia exacta por ID y offsets.
   - Verificación de hash y contexto (anterior/posterior).
   - Detección de ambigüedad (no adivina la primera coincidencia).
   - Detección de obsolescencia si el texto fue eliminado.
5. Control de versiones y trazabilidad de análisis.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backend.app.models.apa_models import AnchorModel

if TYPE_CHECKING:
    from backend.app.services.docx_parser import ParagraphInfo, ParsedDocument

logger = logging.getLogger(__name__)

CONTEXT_WINDOW = 30  # Caracteres de contexto previo y posterior para desambiguar


def normalize_text(text: str) -> str:
    """Normaliza texto para comparación y cálculo de hash reproducible."""
    if not text:
        return ""
    # Unicode NFKC + normalización de espacios y saltos
    t = unicodedata.normalize("NFKC", text)
    t = re.sub(r"[\r\n\t]+", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def sha256_hash(text: str) -> str:
    """Calcula hash SHA-256 de un fragmento normalizado."""
    norm = normalize_text(text)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


@dataclass
class RunSpan:
    """Rango de caracteres que abarca un Run dentro del texto del párrafo."""

    run_index: int
    start_offset: int
    end_offset: int
    text: str


@dataclass
class ParagraphAnchorData:
    """Metadatos de un párrafo para el sistema de anclaje."""

    paragraph_id: str
    paragraph_index: int
    text: str
    paragraph_hash: str
    section_index: int = 0
    runs: list[RunSpan] = field(default_factory=list)


@dataclass
class AnchorResolutionResult:
    """Resultado de resolver un anclaje contra un documento actual."""

    is_valid: bool
    is_ambiguous: bool = False
    is_obsolete: bool = False
    paragraph_index: int | None = None
    paragraph_id: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    matched_text: str = ""
    reason: str = ""


@dataclass
class AnalysisVersionRecord:
    """Registro histórico de versión de análisis de un documento."""

    document_id: str
    document_version: str
    analysis_id: str
    analysis_date: str
    document_hash: str
    paragraph_map: dict[str, dict[str, Any]]
    anchors: list[dict[str, Any]]
    rule_version: str = "APA-7.0"
    model_version: str = "CEA-v1.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CommentAnchorManager:
    """Gestor central de anclajes y resolución posicional con persistencia SQLite."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._history: dict[str, list[AnalysisVersionRecord]] = {}
        if db_path is None:
            base_dir = Path(__file__).resolve().parents[2]
            data_dir = base_dir / "data"
            try:
                data_dir.mkdir(parents=True, exist_ok=True)
                self._db_path = str(data_dir / "anchors_history.db")
            except Exception:
                self._db_path = ""
        else:
            self._db_path = str(db_path)
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        if not self._db_path:
            return
        try:
            with sqlite3.connect(self._db_path, timeout=30.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=15000;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS analysis_versions (
                        document_id TEXT,
                        document_version TEXT,
                        analysis_id TEXT PRIMARY KEY,
                        analysis_date TEXT,
                        document_hash TEXT,
                        payload TEXT
                    )
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_doc_id ON analysis_versions(document_id)"
                )
                conn.commit()
        except Exception as e:
            logger.warning("No se pudo inicializar SQLite para anclajes: %s", e)

    @staticmethod
    def get_or_create_paragraph_id(p: ParagraphInfo) -> str:
        """Obtiene el identificador persistente del párrafo o genera uno determinista."""
        if getattr(p, "paragraph_id", None):
            return str(p.paragraph_id)
        # Genera ID reproducible a partir del índice y hash del contenido
        h = sha256_hash(p.text)[:12]
        return f"p_{p.index}_{h}"

    @staticmethod
    def build_run_spans(p: ParagraphInfo) -> list[RunSpan]:
        """Calcula el mapeo de caracteres entre el texto del párrafo y sus runs."""
        spans: list[RunSpan] = []
        cursor = 0
        p_text = p.text
        for idx, r in enumerate(p.runs or []):
            r_text = r.text or ""
            if not r_text:
                continue
            # Localizar el run a partir del cursor
            pos = p_text.find(r_text, cursor)
            if pos != -1:
                start = pos
                end = pos + len(r_text)
                cursor = end
            else:
                start = cursor
                end = cursor + len(r_text)
                cursor = end
            spans.append(RunSpan(run_index=idx, start_offset=start, end_offset=end, text=r_text))
        return spans

    def build_paragraph_map(
        self, document: ParsedDocument, document_id: str = "doc", document_version: str = "1.0"
    ) -> dict[str, ParagraphAnchorData]:
        """Construye el mapa de párrafos del documento con sus runs y hashes."""
        para_map: dict[str, ParagraphAnchorData] = {}
        for p in document.paragraphs:
            pid = self.get_or_create_paragraph_id(p)
            p_hash = getattr(p, "paragraph_hash", "") or sha256_hash(p.text)
            spans = self.build_run_spans(p)
            para_map[pid] = ParagraphAnchorData(
                paragraph_id=pid,
                paragraph_index=p.index,
                text=p.text,
                paragraph_hash=p_hash,
                section_index=p.section_index,
                runs=spans,
            )
        return para_map

    def create_anchor(
        self,
        p: ParagraphInfo,
        matched_text: str,
        start_offset: int | None = None,
        end_offset: int | None = None,
        document_id: str = "doc_default",
        document_version: str = "v1",
    ) -> AnchorModel:
        """Crea un anclaje exacto para un fragmento dentro de un párrafo."""
        p_text = p.text or ""
        pid = self.get_or_create_paragraph_id(p)
        para_hash = getattr(p, "paragraph_hash", "") or sha256_hash(p_text or "[párrafo]")

        matched_clean = matched_text.strip()
        if not matched_clean or not normalize_text(matched_clean):
            # Si no hay texto específico, el anclaje toma el párrafo o etiqueta descriptiva
            matched_clean = normalize_text(p_text) or "[Párrafo sin contenido]"
            start_offset = 0
            end_offset = max(1, len(p_text))

        # Si no se suministraron offsets exactos, buscar en el texto
        if start_offset is None or end_offset is None or start_offset >= end_offset:
            idx = p_text.find(matched_clean)
            if idx != -1:
                start_offset = idx
                end_offset = idx + len(matched_clean)
            else:
                # Búsqueda normalizada
                norm_p = normalize_text(p_text)
                norm_m = normalize_text(matched_clean)
                idx = norm_p.find(norm_m)
                if idx != -1 and len(p_text) > 0:
                    start_offset = max(0, min(idx, len(p_text) - 1))
                    end_offset = min(len(p_text), start_offset + len(matched_clean))
                    if start_offset >= end_offset:
                        end_offset = start_offset + 1
                else:
                    start_offset = 0
                    end_offset = max(1, len(p_text))

        # Asegurar límites válidos
        start_offset = max(0, min(start_offset, max(0, len(p_text) - 1)))
        end_offset = max(start_offset + 1, min(end_offset, max(1, len(p_text))))
        exact_text = p_text[start_offset:end_offset] if p_text else matched_clean
        if not exact_text or not normalize_text(exact_text):
            exact_text = matched_clean or "[Elemento evaluado]"

        # Contextos anterior y posterior
        before_start = max(0, start_offset - CONTEXT_WINDOW)
        after_end = min(len(p_text), end_offset + CONTEXT_WINDOW)
        context_before = p_text[before_start:start_offset] if p_text else ""
        context_after = p_text[end_offset:after_end] if p_text else ""

        # Identificar runs afectados
        spans = self.build_run_spans(p)
        affected_runs: list[int] = []
        for s in spans:
            if max(start_offset, s.start_offset) < min(end_offset, s.end_offset):
                affected_runs.append(s.run_index)

        frag_hash = sha256_hash(exact_text)

        return AnchorModel(
            document_id=document_id,
            document_version=document_version,
            paragraph_id=pid,
            paragraph_index=p.index,
            paragraph_hash=para_hash,
            start_offset=start_offset,
            end_offset=end_offset,
            matched_text=exact_text,
            fragment_hash=frag_hash,
            context_before=context_before,
            context_after=context_after,
            run_indices=affected_runs,
            is_ambiguous=False,
            is_obsolete=False,
        )

    def resolve_anchor(
        self,
        anchor: AnchorModel,
        current_doc: ParsedDocument,
        para_map: dict[str, ParagraphAnchorData] | None = None,
    ) -> AnchorResolutionResult:
        """Resuelve un anclaje existente contra el estado actual del documento."""
        if para_map is None:
            para_map = self.build_paragraph_map(current_doc, anchor.document_id, anchor.document_version)

        # Paso 1: Buscar por paragraph_id original
        target_p = para_map.get(anchor.paragraph_id)
        if target_p is not None:
            res = self._check_paragraph_match(anchor, target_p)
            if res.is_valid:
                return res

        # Paso 1.5: Si no se encontró por ID (o cambió de índice en fallback p_i_h),
        # buscar por hash exacto del párrafo si el anclaje tiene paragraph_hash
        if anchor.paragraph_hash:
            same_hash_paras = [
                pdata for pdata in para_map.values()
                if pdata.paragraph_hash == anchor.paragraph_hash
            ]
            if len(same_hash_paras) == 1:
                res = self._check_paragraph_match(anchor, same_hash_paras[0])
                if res.is_valid:
                    return res

        # Paso 2: Si el paragraph_id cambió o se reordenó, buscar en el párrafo por índice
        if 0 <= anchor.paragraph_index < len(current_doc.paragraphs):
            cand_p = current_doc.paragraphs[anchor.paragraph_index]
            cand_pid = self.get_or_create_paragraph_id(cand_p)
            cand_data = para_map.get(cand_pid)
            if cand_data:
                res = self._check_paragraph_match(anchor, cand_data)
                if res.is_valid:
                    return res

        # Paso 3: Búsqueda exhaustiva en todo el documento
        candidates: list[tuple[ParagraphAnchorData, int, int]] = []
        for pdata in para_map.values():
            matches = self._find_all_occurrences(pdata.text, anchor.matched_text)
            for s, e in matches:
                candidates.append((pdata, s, e))

        if not candidates:
            # Fragmento ya no existe
            return AnchorResolutionResult(
                is_valid=False,
                is_obsolete=True,
                reason="El fragmento ya no existe en el documento actual.",
            )

        if len(candidates) == 1:
            pdata, s, e = candidates[0]
            return AnchorResolutionResult(
                is_valid=True,
                is_ambiguous=False,
                paragraph_index=pdata.paragraph_index,
                paragraph_id=pdata.paragraph_id,
                start_offset=s,
                end_offset=e,
                matched_text=pdata.text[s:e],
                reason="Fragmento reubicado unívocamente.",
            )

        # Múltiples coincidencias: Desambiguar usando context_before y context_after
        disambiguated: list[tuple[ParagraphAnchorData, int, int]] = []
        for pdata, s, e in candidates:
            b_start = max(0, s - len(anchor.context_before))
            a_end = min(len(pdata.text), e + len(anchor.context_after))
            cand_before = pdata.text[b_start:s]
            cand_after = pdata.text[e:a_end]
            if (
                normalize_text(cand_before) == normalize_text(anchor.context_before)
                and normalize_text(cand_after) == normalize_text(anchor.context_after)
            ):
                disambiguated.append((pdata, s, e))

        if len(disambiguated) == 1:
            pdata, s, e = disambiguated[0]
            return AnchorResolutionResult(
                is_valid=True,
                is_ambiguous=False,
                paragraph_index=pdata.paragraph_index,
                paragraph_id=pdata.paragraph_id,
                start_offset=s,
                end_offset=e,
                matched_text=pdata.text[s:e],
                reason="Fragmento desambiguado exitosamente por contexto.",
            )

        # Si aún hay múltiples o ninguna coincide con el contexto: AMBIGUO
        return AnchorResolutionResult(
            is_valid=False,
            is_ambiguous=True,
            reason=(
                f"Existen {len(candidates)} ocurrencias idénticas del fragmento sin "
                "contexto unívoco suficiente para desambiguar."
            ),
        )

    def _check_paragraph_match(
        self, anchor: AnchorModel, pdata: ParagraphAnchorData
    ) -> AnchorResolutionResult:
        """Verifica si un anclaje es válido dentro de un párrafo dado."""
        p_text = pdata.text
        # Verificación exacta por offsets
        if (
            0 <= anchor.start_offset < anchor.end_offset <= len(p_text)
            and p_text[anchor.start_offset : anchor.end_offset] == anchor.matched_text
        ):
            return AnchorResolutionResult(
                is_valid=True,
                paragraph_index=pdata.paragraph_index,
                paragraph_id=pdata.paragraph_id,
                start_offset=anchor.start_offset,
                end_offset=anchor.end_offset,
                matched_text=anchor.matched_text,
                reason="Coincidencia exacta por identificador y offsets.",
            )

        # Si el texto del párrafo se modificó ligeramente, buscar dentro del mismo párrafo
        matches = self._find_all_occurrences(p_text, anchor.matched_text)
        if len(matches) == 1:
            s, e = matches[0]
            return AnchorResolutionResult(
                is_valid=True,
                paragraph_index=pdata.paragraph_index,
                paragraph_id=pdata.paragraph_id,
                start_offset=s,
                end_offset=e,
                matched_text=p_text[s:e],
                reason="Fragmento ubicado dentro del párrafo con nuevos offsets.",
            )

        if len(matches) > 1:
            # Desambiguación dentro del mismo párrafo
            matched_by_context = []
            for s, e in matches:
                b_start = max(0, s - len(anchor.context_before))
                a_end = min(len(p_text), e + len(anchor.context_after))
                if (
                    normalize_text(p_text[b_start:s]) == normalize_text(anchor.context_before)
                    or normalize_text(p_text[e:a_end]) == normalize_text(anchor.context_after)
                ):
                    matched_by_context.append((s, e))
            if len(matched_by_context) == 1:
                s, e = matched_by_context[0]
                return AnchorResolutionResult(
                    is_valid=True,
                    paragraph_index=pdata.paragraph_index,
                    paragraph_id=pdata.paragraph_id,
                    start_offset=s,
                    end_offset=e,
                    matched_text=p_text[s:e],
                    reason="Fragmento desambiguado por contexto dentro del párrafo.",
                )
            return AnchorResolutionResult(
                is_valid=False,
                is_ambiguous=True,
                reason="Múltiples fragmentos idénticos en el mismo párrafo.",
            )

        return AnchorResolutionResult(is_valid=False, reason="Fragmento no encontrado en el párrafo.")

    @staticmethod
    def _find_all_occurrences(haystack: str, needle: str) -> list[tuple[int, int]]:
        """Devuelve todas las posiciones (start, end) de needle en haystack."""
        if not needle or not haystack:
            return []
        res: list[tuple[int, int]] = []
        pos = 0
        while True:
            idx = haystack.find(needle, pos)
            if idx == -1:
                break
            res.append((idx, idx + len(needle)))
            pos = idx + 1
        return res

    def record_analysis_version(
        self,
        document_id: str,
        document_version: str,
        document: ParsedDocument,
        anchors: list[AnchorModel],
        analysis_id: str | None = None,
    ) -> AnalysisVersionRecord:
        """Registra una versión de análisis para trazabilidad y auditoría."""
        if analysis_id is None:
            import uuid
            analysis_id = f"anl_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{uuid.uuid4().hex[:6]}"

        doc_content = "".join(p.text for p in document.paragraphs)
        doc_hash = hashlib.sha256(doc_content.encode("utf-8")).hexdigest()
        para_map = self.build_paragraph_map(document, document_id, document_version)
        para_map_dicts = {
            pid: {
                "paragraph_id": p.paragraph_id,
                "paragraph_index": p.paragraph_index,
                "paragraph_hash": p.paragraph_hash,
                "section_index": p.section_index,
                "text_snippet": p.text[:80],
            }
            for pid, p in para_map.items()
        }

        record = AnalysisVersionRecord(
            document_id=document_id,
            document_version=document_version,
            analysis_id=analysis_id,
            analysis_date=datetime.now().isoformat(),
            document_hash=doc_hash,
            paragraph_map=para_map_dicts,
            anchors=[a.model_dump() for a in anchors],
        )

        history = self._history.setdefault(document_id, [])
        history.append(record)

        # Persistencia en SQLite con reintento ante concurrencia
        if self._db_path:
            for attempt in range(5):
                try:
                    with sqlite3.connect(self._db_path, timeout=30.0) as conn:
                        conn.execute("PRAGMA busy_timeout=15000;")
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO analysis_versions
                            (document_id, document_version, analysis_id, analysis_date, document_hash, payload)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                document_id,
                                document_version,
                                analysis_id,
                                record.analysis_date,
                                doc_hash,
                                json.dumps(record.to_dict(), ensure_ascii=False),
                            ),
                        )
                        conn.commit()
                    break
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < 4:
                        import time
                        time.sleep(0.05 * (attempt + 1))
                        continue
                    logger.warning("Fallo al persistir versión en SQLite: %s", e)
                except Exception as e:
                    logger.warning("Fallo al persistir versión en SQLite: %s", e)
                    break

        return record

    def get_version_history(self, document_id: str) -> list[AnalysisVersionRecord]:
        """Obtiene el historial de análisis de un documento (recuperable tras reinicio)."""
        if document_id in self._history and self._history[document_id]:
            return list(self._history[document_id])

        # Recuperar desde SQLite si la memoria está vacía (reinicio del servidor)
        if self._db_path:
            for attempt in range(3):
                try:
                    with sqlite3.connect(self._db_path, timeout=30.0) as conn:
                        conn.execute("PRAGMA busy_timeout=15000;")
                        cursor = conn.execute(
                            "SELECT payload FROM analysis_versions WHERE document_id = ? ORDER BY analysis_date ASC",
                            (document_id,),
                        )
                        rows = cursor.fetchall()
                        recovered: list[AnalysisVersionRecord] = []
                        for (raw_payload,) in rows:
                            d = json.loads(raw_payload)
                            rec = AnalysisVersionRecord(
                                document_id=d["document_id"],
                                document_version=d["document_version"],
                                analysis_id=d["analysis_id"],
                                analysis_date=d["analysis_date"],
                                document_hash=d["document_hash"],
                                paragraph_map=d["paragraph_map"],
                                anchors=d["anchors"],
                                rule_version=d.get("rule_version", "APA-7.0"),
                                model_version=d.get("model_version", "CEA-v1.0"),
                            )
                            recovered.append(rec)
                        if recovered:
                            self._history[document_id] = recovered
                            return recovered
                    break
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < 2:
                        import time
                        time.sleep(0.05 * (attempt + 1))
                        continue
                    logger.warning("Error recuperando historial de SQLite: %s", e)
                except Exception as e:
                    logger.warning("Error recuperando historial de SQLite: %s", e)
                    break

        return []


# Instancia singleton predeterminada
anchor_manager = CommentAnchorManager()
