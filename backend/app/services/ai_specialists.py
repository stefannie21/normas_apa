"""Especialistas de IA acotada por tareas (Fases 3, 9 y 10 del proyecto CEA).

Principio fundamental:
- No enviar todo el documento a un único modelo para revisión general.
- Cada tarea cuenta con su propio especialista con contexto mínimo estrictamente necesario.
- Respuestas estructuradas con validación Pydantic.
- Métricas de consumo de tokens y tiempo de respuesta.
- Proveedor desacoplado (admite Gemini u otros vía API REST).
- Si no hay API key o la IA está deshabilitada, opera en modo de evaluación
  determinista asistida sin fallar.
"""
from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import httpx

from backend.app.config import get_settings
from backend.app.models.apa_models import AnchorModel, EvidenceModel, StructuredFindingModel
from backend.app.services.comment_anchor_manager import anchor_manager, normalize_text, sha256_hash

if TYPE_CHECKING:
    from backend.app.services.docx_parser import ParagraphInfo, ParsedDocument

logger = logging.getLogger(__name__)


def _clean_json_text(text: str) -> str:
    """Extrae JSON limpio eliminando delimitadores de código markdown si existen."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


class BaseSpecialist(ABC):
    """Clase base para especialistas de IA con trazabilidad de tokens y esquema."""

    task_id: str = "base_task"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.last_prompt_tokens: int = 0
        self.last_completion_tokens: int = 0
        self.last_elapsed_sec: float = 0.0

    @abstractmethod
    def run(self, **kwargs: Any) -> list[StructuredFindingModel]:
        """Ejecuta la tarea especializada y devuelve hallazgos estructurados."""
        ...

    def _call_gemini_raw(self, prompt: str, system_instruction: str = "") -> str:
        """Llamada HTTP con soporte unificado para Gemini / OpenAI."""
        t0 = time.time()
        key = self.settings.resolved_key
        if not key:
            raise ValueError("Clave de API de IA no configurada")

        if self.settings.provider == "gemini":
            models = self.settings.model_cascade
            # Si el modelo tiene 'gpt', seleccionar fallback a gemini
            model = next((m for m in models if "gpt" not in m), "gemini-1.5-flash")
            url = f"{self.settings.base_url}/models/{model}:generateContent"
            headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
            payload: dict[str, Any] = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json",
                },
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            with httpx.Client(timeout=35.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            self.last_elapsed_sec = round(time.time() - t0, 3)
            usage = data.get("usageMetadata", {})
            self.last_prompt_tokens = usage.get("promptTokenCount", len(prompt) // 4)
            self.last_completion_tokens = usage.get("candidatesTokenCount", 0)

            candidates = data.get("candidates", [])
            if not candidates:
                return "[]"
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                return "[]"
            return parts[0].get("text", "[]")
        else:
            # OpenAI / compatible
            model = self.settings.resolved_model
            url = f"{self.settings.base_url}/chat/completions"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            }
            with httpx.Client(timeout=35.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            self.last_elapsed_sec = round(time.time() - t0, 3)
            usage = data.get("usage", {})
            self.last_prompt_tokens = usage.get("prompt_tokens", len(prompt) // 4)
            self.last_completion_tokens = usage.get("completion_tokens", 0)
            choices = data.get("choices", [])
            if not choices:
                return "[]"
            return choices[0].get("message", {}).get("content", "[]")


# ==============================================================================
# Especialista 1: Citas complejas
# ==============================================================================
class ComplexCitationSpecialist(BaseSpecialist):
    """Especialista en citas complejas narrativas, parentéticas múltiples y secundarias."""

    task_id: str = "complex_citation_analysis"

    def run(
        self,
        document: ParsedDocument,
        candidate_paragraphs: list[ParagraphInfo],
        document_id: str = "doc",
        document_version: str = "v1",
    ) -> list[StructuredFindingModel]:
        if not candidate_paragraphs:
            return []

        # Preparación de contexto mínimo estrictamente necesario
        snippets = []
        for p in candidate_paragraphs:
            snippets.append({
                "paragraph_id": anchor_manager.get_or_create_paragraph_id(p),
                "paragraph_index": p.index,
                "text": p.text[:500],
            })

        system_prompt = (
            "Eres un especialista en citas APA 7.ª edición. Analiza las citas complejas "
            "(citas secundarias 'citado en', citas con 3+ autores, citas con múltiples "
            "fuentes en un mismo paréntesis, citas corporativas) en los párrafos dados.\n"
            "REGLAS ESTRICTAS:\n"
            "1. NO inventes autores ni años. Si un apellido no está escrito en el texto, no existe.\n"
            "2. Reconoce estructuras válidas como (García, 2019; López & Pérez, 2020) o citas secundarias.\n"
            "3. Solo reporta FAIL ante incumplimientos demostrados de APA 7.\n"
            "Devuelve un array JSON con objetos con este esquema:\n"
            "[{\n"
            "  \"paragraph_id\": str,\n"
            "  \"rule_id\": \"CIT-001\" | \"CIT-002\" | \"CIT-003\" | \"CIT-004\" | \"CIT-009\",\n"
            "  \"title\": str,\n"
            "  \"message\": str,\n"
            "  \"suggestion\": str,\n"
            "  \"matched_text\": str,\n"
            "  \"reason\": str,\n"
            "  \"severity\": \"error\" | \"warning\" | \"info\",\n"
            "  \"confidence\": float\n"
            "}]"
        )

        user_prompt = f"Párrafos candidatos:\n{json.dumps(snippets, ensure_ascii=False, indent=2)}"

        raw_items = []
        if self.settings.ai_available:
            try:
                raw_json = self._call_gemini_raw(user_prompt, system_prompt)
                cleaned = _clean_json_text(raw_json)
                parsed = json.loads(cleaned)
                if isinstance(parsed, list):
                    raw_items = parsed
                elif isinstance(parsed, dict) and "findings" in parsed:
                    raw_items = parsed["findings"]
            except Exception as exc:
                logger.warning("Fallo en ComplexCitationSpecialist (IA): %s", exc)

        # Mapeo y validación de hallazgos
        findings: list[StructuredFindingModel] = []
        p_by_id = {anchor_manager.get_or_create_paragraph_id(p): p for p in candidate_paragraphs}

        for item in raw_items:
            try:
                pid = str(item.get("paragraph_id", ""))
                p = p_by_id.get(pid)
                if not p:
                    continue
                matched = str(item.get("matched_text", "")).strip()
                if not matched or matched not in p.text:
                    # Si no coincide exactamente, verificar normalizado o descartar
                    norm_p = normalize_text(p.text)
                    norm_m = normalize_text(matched)
                    if norm_m not in norm_p:
                        continue
                anchor = anchor_manager.create_anchor(
                    p=p,
                    matched_text=matched,
                    document_id=document_id,
                    document_version=document_version,
                )
                finding = StructuredFindingModel(
                    task_id=self.task_id,
                    rule_id=str(item.get("rule_id", "CIT-001")),
                    category="Citas en el texto",
                    status="FAIL",
                    severity=str(item.get("severity", "warning")),
                    title=str(item.get("title", "Incumplimiento en cita compleja")),
                    message=str(item.get("message", "")),
                    suggestion=str(item.get("suggestion", "")),
                    evidence=EvidenceModel(
                        original_text=matched,
                        reason=str(item.get("reason", "Regla APA 7 de citación")),
                    ),
                    anchor=anchor,
                    confidence=float(item.get("confidence", 0.9)),
                )
                findings.append(finding)
            except Exception as e:
                logger.debug("Descartado hallazgo de cita compleja por esquema inválido: %s", e)

        return findings


# ==============================================================================
# Especialista 2: Evaluación contextual de referencias
# ==============================================================================
class ReferenceContextSpecialist(BaseSpecialist):
    """Especialista en analizar tipos de fuente y componentes de la lista de referencias."""

    task_id: str = "reference_context_evaluation"

    def run(
        self,
        document: ParsedDocument,
        document_id: str = "doc",
        document_version: str = "v1",
        reference_paragraphs: list[ParagraphInfo] | None = None,
    ) -> list[StructuredFindingModel]:
        ref_paras = reference_paragraphs if reference_paragraphs is not None else document.reference_paragraphs()
        if not ref_paras:
            return []

        # Preparación de entradas de referencias
        ref_items = []
        for p in ref_paras:
            ref_items.append({
                "paragraph_id": anchor_manager.get_or_create_paragraph_id(p),
                "paragraph_index": p.index,
                "raw": p.text.strip(),
            })

        system_prompt = (
            "Eres un especialista en bibliografía y referencias bajo normas APA 7.ª edición.\n"
            "Analiza las referencias para identificar: tipo de fuente (artículo, libro, "
            "capítulo, tesis, web, ley), componentes faltantes OBLIGATORIOS (autoría, fecha, "
            "título, fuente) y coherencia estructural.\n"
            "REGLAS OBLIGATORIAS:\n"
            "1. NO marcar como incorrectas omisiones permitidas por APA 7 (ej. obras sin DOI, "
            "libros sin número de edición, publicaciones sin número de fascículo/issue).\n"
            "2. Distinguir autores corporativos (ej. OMS, Banco Mundial) de autores personales.\n"
            "Devuelve un array JSON con este formato:\n"
            "[{\n"
            "  \"paragraph_id\": str,\n"
            "  \"source_type\": str,\n"
            "  \"rule_id\": \"REF-004\" | \"REF-005\" | \"REF-006\" | \"REF-007\" | \"REF-008\",\n"
            "  \"title\": str,\n"
            "  \"message\": str,\n"
            "  \"suggestion\": str,\n"
            "  \"matched_text\": str,\n"
            "  \"reason\": str,\n"
            "  \"severity\": \"error\" | \"warning\" | \"info\",\n"
            "  \"confidence\": float\n"
            "}]"
        )

        user_prompt = f"Referencias a evaluar:\n{json.dumps(ref_items, ensure_ascii=False, indent=2)}"

        raw_items = []
        if self.settings.ai_available:
            try:
                raw_json = self._call_gemini_raw(user_prompt, system_prompt)
                cleaned = _clean_json_text(raw_json)
                parsed = json.loads(cleaned)
                if isinstance(parsed, list):
                    raw_items = parsed
                elif isinstance(parsed, dict) and "findings" in parsed:
                    raw_items = parsed["findings"]
            except Exception as exc:
                logger.warning("Fallo en ReferenceContextSpecialist (IA): %s", exc)

        findings: list[StructuredFindingModel] = []
        p_by_id = {anchor_manager.get_or_create_paragraph_id(p): p for p in ref_paras}

        for item in raw_items:
            try:
                pid = str(item.get("paragraph_id", ""))
                p = p_by_id.get(pid)
                if not p:
                    continue
                matched = str(item.get("matched_text", "")).strip() or p.text[:80]
                anchor = anchor_manager.create_anchor(
                    p=p,
                    matched_text=matched,
                    document_id=document_id,
                    document_version=document_version,
                )
                finding = StructuredFindingModel(
                    task_id=self.task_id,
                    rule_id=str(item.get("rule_id", "REF-004")),
                    category="Lista de referencias",
                    status="FAIL",
                    severity=str(item.get("severity", "warning")),
                    title=str(item.get("title", f"Fuente: {item.get('source_type', 'Referencia')}")),
                    message=str(item.get("message", "")),
                    suggestion=str(item.get("suggestion", "")),
                    evidence=EvidenceModel(
                        original_text=matched,
                        reason=str(item.get("reason", "Estructura de referencia APA 7")),
                    ),
                    anchor=anchor,
                    confidence=float(item.get("confidence", 0.85)),
                    extra={"source_type": item.get("source_type", "")},
                )
                findings.append(finding)
            except Exception as e:
                logger.debug("Descartado hallazgo de referencia por esquema: %s", e)

        return findings


# ==============================================================================
# Especialista 3: Propuestas de corrección
# ==============================================================================
class CorrectionProposalSpecialist(BaseSpecialist):
    """Especialista en proponer correcciones para observaciones PREVIAMENTE IDENTIFICADAS.

    Regla inquebrantable:
    - NO puede crear observaciones nuevas.
    - No inventa información (autores, años, DOIs).
    """

    task_id: str = "correction_proposal"

    def run(
        self,
        findings: list[StructuredFindingModel],
    ) -> list[StructuredFindingModel]:
        if not findings or not self.settings.ai_available:
            return findings

        # Filtrar hallazgos que no tengan una sugerencia clara o específica
        targets = [f for f in findings if len(f.suggestion) < 15 or "Verificar" in f.suggestion]
        if not targets:
            return findings

        payload = [
            {
                "index": i,
                "rule_id": f.rule_id,
                "title": f.title,
                "message": f.message,
                "evidence": f.evidence.original_text,
                "current_suggestion": f.suggestion,
            }
            for i, f in enumerate(targets[:15])  # Límite por lote para optimizar tokens
        ]

        system_prompt = (
            "Eres un corrector de estilo APA 7.ª edición. Proporciona una explicación clara "
            "y una propuesta de corrección EXACTA y respetuosa con el texto original para "
            "los hallazgos existentes suministrados.\n"
            "REGLAS CRÍTICAS:\n"
            "1. NO generes hallazgos nuevos. Solo responde para los índices suministrados.\n"
            "2. NO inventes nombres de autores, años, DOIs ni URLs.\n"
            "3. Si falta un dato bibliográfico, indica 'Agregar [dato] correspondiente'.\n"
            "Devuelve un array JSON:\n"
            "[{\"index\": int, \"explanation\": str, \"suggested_fix\": str}]"
        )

        user_prompt = f"Hallazgos a corregir:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"

        try:
            raw_json = self._call_gemini_raw(user_prompt, system_prompt)
            cleaned = _clean_json_text(raw_json)
            corrections = json.loads(cleaned)
            if isinstance(corrections, list):
                for corr in corrections:
                    idx = corr.get("index")
                    if isinstance(idx, int) and 0 <= idx < len(targets):
                        target_f = targets[idx]
                        fix = str(corr.get("suggested_fix", "")).strip()
                        if fix:
                            target_f.suggestion = fix
        except Exception as exc:
            logger.warning("Fallo en CorrectionProposalSpecialist: %s", exc)

        return findings


# ==============================================================================
# Especialista 4: Análisis estructural contextual
# ==============================================================================
class StructuralContextSpecialist(BaseSpecialist):
    """Especialista en evaluar encabezados y jerarquías ambiguas."""

    task_id: str = "structural_context_analysis"

    def run(
        self,
        document: ParsedDocument,
        candidate_headings: list[ParagraphInfo],
        document_id: str = "doc",
        document_version: str = "v1",
    ) -> list[StructuredFindingModel]:
        if not candidate_headings:
            return []

        snippets = []
        all_p = document.paragraphs
        for h in candidate_headings:
            prev_txt = all_p[h.index - 1].text[:120] if h.index > 0 else ""
            next_txt = all_p[h.index + 1].text[:120] if h.index + 1 < len(all_p) else ""
            snippets.append({
                "paragraph_id": anchor_manager.get_or_create_paragraph_id(h),
                "paragraph_index": h.index,
                "text": h.text.strip(),
                "prev_context": prev_txt,
                "next_context": next_txt,
            })

        system_prompt = (
            "Eres un revisor de estructura académica y normas APA 7.ª edición.\n"
            "Evalúa párrafos candidatos a encabezados que carecen de estilo nativo de Word "
            "(ej. texto corto en negrita sin estilo de encabezado).\n"
            "Determina si son realmente subtítulos que deben llevar nivel APA 1, 2 o 3, "
            "o si corresponden a texto del cuerpo (ej. etiquetas de listas, casos de estudio).\n"
            "Devuelve un array JSON:\n"
            "[{\n"
            "  \"paragraph_id\": str,\n"
            "  \"is_heading\": bool,\n"
            "  \"recommended_level\": int,\n"
            "  \"reason\": str\n"
            "}]"
        )

        user_prompt = f"Encabezados candidatos:\n{json.dumps(snippets, ensure_ascii=False, indent=2)}"

        raw_items = []
        if self.settings.ai_available:
            try:
                raw_json = self._call_gemini_raw(user_prompt, system_prompt)
                cleaned = _clean_json_text(raw_json)
                parsed = json.loads(cleaned)
                if isinstance(parsed, list):
                    raw_items = parsed
            except Exception as exc:
                logger.warning("Fallo en StructuralContextSpecialist (IA): %s", exc)

        findings: list[StructuredFindingModel] = []
        p_by_id = {anchor_manager.get_or_create_paragraph_id(p): p for p in candidate_headings}

        for item in raw_items:
            try:
                if not item.get("is_heading"):
                    continue
                pid = str(item.get("paragraph_id", ""))
                p = p_by_id.get(pid)
                if not p:
                    continue
                lvl = int(item.get("recommended_level", 2))
                anchor = anchor_manager.create_anchor(
                    p=p,
                    matched_text=p.text.strip(),
                    document_id=document_id,
                    document_version=document_version,
                )
                finding = StructuredFindingModel(
                    task_id=self.task_id,
                    rule_id="HEAD-004",
                    category="Títulos y jerarquía",
                    status="FAIL",
                    severity="warning",
                    title="Encabezado sin estilo de Word",
                    message=(
                        f"El párrafo funciona estructuralmente como Título {lvl} pero no "
                        "utiliza el estilo de encabezado correspondiente de Word."
                    ),
                    suggestion=f"Aplicar estilo 'Título {lvl}' en Word y verificar jerarquía APA.",
                    evidence=EvidenceModel(
                        original_text=p.text.strip(),
                        reason=str(item.get("reason", "Análisis estructural contextual")),
                    ),
                    anchor=anchor,
                    confidence=0.88,
                )
                findings.append(finding)
            except Exception as e:
                logger.debug("Descartado análisis estructural por esquema: %s", e)

        return findings
