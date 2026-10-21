# Filtro IA - Privacidad, Sesgo y Transparencia

## 1. Objetivo

El verificador/corrector de Normas APA incorpora una capa de IA acotada cuyo objetivo exclusivo es **clasificar citas y referencias y detectar elementos APA 7 ausentes**. Esta capa está diseñada con los principios de Privacidad, Filtro de sesgo y Transparencia.

La IA **nunca escribe en el documento**. Solo clasifica, sugiere y devuelve hallazgos con confianza. Todo lo que modifica el `.docx` se hace a través de las reglas deterministas.

---

## 2. Alcance

- **Único propósito:** Clasificar el tipo de cada referencia y detectar elementos APA 7 que faltan.
- **Datos enviados:** Únicamente el JSON estructurado con **citas y referencias** extraídas del documento. **Nunca** se envía el texto completo de la tesis.
- **No enviado:** Texto del cuerpo del documento, títulos completos, tablas, figuras, imágenes, contenido del Resumen/Abstract, Portada o cualquier párrafo fuera de las referencias/citas detectadas.
- **Truncados aplicados:** `texto` de referencia (máx. 400 caracteres), `titulo` (160), `contenedor` (120); `texto` de cita (120). Máximo 80 citas. Esto limita el volumen enviado.

---

## 3. Privacidad

### Consentimiento
- **Explícito:** El usuario debe autorizar (`consent=1`) para cada ejecución de la revisión con IA.
- **Sin consentimiento:** El endpoint `POST /api/ai/classify` responde **428 (Precondition Required)** y **no contacta** al proveedor de IA.
- **Vista previa sin llamada externa:** `POST /api/ai/preview` muestra el alcance real (nº referencias/citas, `chars_max`, campos, proveedor/modelo) **sin llamar a la IA**.
- **Almacenamiento:** El consentimiento se guarda en **`sessionStorage`** (válido solo durante la sesión actual). **No** se guarda en `localStorage`. Se puede revocar en cualquier momento mediante el botón **"Quitar consentimiento IA"** en la cinta ("Revisar APA").
- **Modal de consentimiento:** Se muestra antes del primer envío con la información concreta que se enviará.

### Enmascarado (declarado)
- El payload mínimo se construye únicamente a partir de los registros estructurados (autores contados, año, tipo detectado, cursivas, título/contenedor truncados). No se extraen campos libres con datos personales sensibles del texto. El diseño mantiene el **principio de mínimo necesario**.

---

## 4. Filtro de sesgo

### Vocabulario cerrado para `missing`
Los elementos ausentes (`missing`) se normalizan y **solo** se aceptan valores del vocabulario cerrado:

```json
["autoría", "fecha", "título", "fuente", "editorial", "volumen", "número", "páginas", "doi_url", "edición", "traducción"]
```

Se aplican alias para normalizar salidas del modelo (`autor/autores/autoria` → `autoría`, `año/ano/anio` → `fecha`, `DOI/url/enlace` → `doi_url`, etc.). Cualquier categoría no reconocida **se descarta**.

### Contraste con reglas deterministas
Para evitar falsos positivos y limitar sesgos del modelo:
- Se ejecuta el análisis **determinista** (`analyze(document)`) y se compara por **referencia** (usando `paragraph_index` de cada entrada de referencias).
- **Discrepancia:** Si no existe cobertura de reglas deterministas para esa referencia, pero la IA detecta elementos ausentes con **confianza ≥ 0.75** (`DISCREPANCY_CONF_MIN`), se genera un hallazgo etiquetado con `ai_discrepancy: true` y mensaje "Discrepancia: ...".
- **Confianza base:** Para sugerencias con cobertura determinista se exige **≥ 0.60** (`MODEL_CONF_MIN`).
- Las sugerencias por debajo del umbral no se convierten en hallazgos: pasan a **notas** para revisión manual.
- Los hallazgos IA incluyen: `ai_missing`, `ai_confidence`, `ai_model`, `ai_discrepancy`, `ai_source_type`, `bib_kind`, `auto_fixable: false`.

### Et al. (APA 7)
El prompt de IA obliga a respetar: con **1–2 autores** nunca se usa `et al.` y el separador depende de la forma:
- **Paréntesis:** `(Pérez & Gómez, 2023)`
- **Narrativa:** `Pérez y Gómez (2023)` (o `and` en inglés)

Con **≥ 3 autores**: `et al.` desde la primera mención.

---

## 5. Transparencia

### Insignia IA
Todos los hallazgos generados por IA llevan:
- **Badge "IA"** con tooltip que muestra: "Sugerencia de la IA: no se aplica automáticamente. Solo revisa citas/referencias. · Modelo: [modelo] · Confianza: [XX]%"
- En el listado del informe aparecen diferenciados (`.finding.ai`) para distinguirlos de los hallazgos deterministas.

### Auditoría
El backend devuelve:
```json
{
  "model": "gemini-3.8-flash",
  "notes": ["Revisión IA ejecutada con el modelo ...", "..."],
  "findings": [...]
}
```

- `ai_notes` se conserva en `AnalysisResult` y pasa a `report.ai_review.notes`.
- El informe JSON incluye `ai_review.used: true` y las notas de auditoría.
- En cada hallazgo IA se registra: modelo usado, confianza, elementos detectados, si es **discrepancia** y cobertura determinista.

### Garantías explícitas en la interfaz
- Modal de consentimiento muestra: referencias/citas enviadas, **máx. caracteres**, campos exactos, proveedor y modelo.
- Texto visible: **"Solo envía citas y referencias, no el texto completo"**.
- La IA **nunca escribe en el documento**. Los hallazgos IA son **solo lectura** y no son aplicables automáticamente (requieren criterio humano).

---

## 6. Implementación técnica

| Componente | Cambio |
|---|---|
| `backend/app/services/ai_reviewer.py` | Payload mínimo con truncados, `MISSING_CATEGORIES` + normalización de alias, contraste por referencia, umbrales `MODEL_CONF_MIN=0.6`, `DISCREPANCY_CONF_MIN=0.75`. Añade `ai_discrepancy`, `ai_model` en `extra`. |
| `backend/app/api/routes.py` | `GET/POST` lógicos: `POST /api/ai/preview` (sin llamada IA), `POST /api/ai/classify` exige `consent=1` (retorna 428 sin consentimiento). Recalcula contraste con `analyze(document)`. |
| `backend/app/services/analyzer.py` | Añadido `AnalysisResult.ai_notes`. |
| `backend/app/services/report.py` | Transmite `ai_review.notes` al informe. |
| `frontend/editor/app.py` (app.js) | Flujo de consentimiento con `sessionStorage`, modal de vista previa, botón "Quitar consentimiento IA", tooltip con modelo+confianza. |
| `frontend/views/inicio.js` | Texto corregido para reflejar alcance real (citas/referencias únicamente). |

---

## 7. Verificación

- **Sin consentimiento:** `/api/ai/classify` devuelve `428` y **no contacta** al proveedor.
- **Vista previa:** `/api/ai/preview` devuelve recuentos/campos y `sends_full_document: false` sin llamar a IA.
- **Vocabulario cerrado:** Categorías no reconocidas son descartadas.
- **Contraste:** Las discrepancias requieren **confianza ≥ 0.75** para evitar ruido; con cobertura determinista usa 0.60.
- **Privacidad de sesión:** Consentimiento en `sessionStorage` (no persistente). Se puede revocar.
- **Transparencia:** Todo hallazgo IA lleva modelo, confianza, badge y queda claramente diferenciado en el informe.

---

## 8. Limitaciones conocidas

- El enmascarado de correos/teléfonos/comunicaciones personales no se aplica explícitamente sobre texto libre en esta versión: el payload es mínimo (campos estructurados con truncados) y el riesgo se mitiga por el **principio de mínimo necesario** y la **exclusión del texto completo**.
- El contraste por referencia depende de `paragraph_index` correcto (proveniente del parseo de `docx_parser`).
- La IA solo clasifica referencias/citas. No analiza gramática, coherencia ni estilo.

---

*El filtro de IA cumple los requisitos de privacidad, sesgo controlado y transparencia total.*
