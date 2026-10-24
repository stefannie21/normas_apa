/* Logica principal: carga de .docx, edicion y analisis APA. */
import { Pager } from "./pager.js";
import { Commands } from "./commands.js";
import { Marker } from "./marker.js";
import { Fixer } from "./fixer.js";
import { History } from "./history.js";
import { SessionStore } from "./storage.js";
import { Ribbon } from "./ribbon.js";
import { Router } from "../core/router.js";
import { Library } from "../library.js";

const App = (function () {
  "use strict";
  const SEVERITY_ICON = { error: "!", warning: "!", info: "i" };
  const SEV_TEXT = { error: "Error", warning: "Aviso", info: "Observación" };

  // Version del HTML que produce el conversor (mammoth + enrichHtml). Se sube
  // cuando cambia algo en la conversion para que las sesiones ya guardadas en
  // el navegador se vuelvan a generar en vez de reutilizar el HTML antiguo.
  //  1: sin conservar los parrafos vacios del .docx
  //  2: los conserva (portadas que se empujan con lineas en blanco)
  //  3: los vacios miden lo que su marca de parrafo y las imagenes flotantes
  //     dejan de ocupar altura (portada con logo anclado)
  const FLOW_VERSION = 3;

  const page = document.getElementById("page");
  const emptyState = document.getElementById("empty-state");
  const fileInput = document.getElementById("file");
  const docName = document.getElementById("doc-name");
  const analyzeBtn = document.getElementById("analyze-btn");
  const emptyOpen = document.getElementById("empty-open");
  const statusMsg = document.getElementById("status-msg");
  const statusWords = document.getElementById("status-words");
  const statusChars = document.getElementById("status-chars");
  const statusPages = document.getElementById("status-pages");
  const zoomRange = document.getElementById("zoom-range");
  const toast = document.getElementById("toast");

  /* Panel del informe que aparece junto al documento al verificar */
  const reportPane = document.getElementById("report-pane");
  const paneClose = document.getElementById("pane-close");
  const paneScore = document.getElementById("pane-score");
  const paneCards = document.getElementById("pane-cards");
  const paneFilters = document.getElementById("pane-filters");
  const paneFindings = document.getElementById("pane-findings");
  const paneAll = document.getElementById("pane-all");
  const paneFiltersBtn = document.getElementById("pane-filters-btn");
  const paneCats = document.getElementById("pane-cats");
  let paneFilter = "all";
  let paneCategory = "";

  let currentFile = null;
  let currentFindings = [];
  let allFindings = []; // copia integra del informe, sin filtrar
  let zoom = 100;
  let reading = false;
  let docSections = null; // geometria de cada seccion del docx (vertical/horizontal)

  /* ---------- Ribbon ---------- */
  Ribbon.render(document.getElementById("ribbon-tabs"), document.getElementById("ribbon-panels"), {
    analyze: runAnalysis,
    "ai-review": runAiReview,
    "ai-revoke": revokeAiConsent,
    "fix-doc": openFixModal,
    "toggle-pane": () => togglePane(),
    orientacion: () => openOrientModal(),
    "clear-marks": clearMarks,
    "page-break": () => {
      insertHtml('<div class="page-break"></div>');
      repaginate();
    },
    table: insertTable,
    image: pickImage,
    link: insertLink,
    reading: toggleReading,
    "pdf-view": togglePdfView,
    "apa-defaults": applyApaDefaults,
    repaginate: repaginate,
    "toggle-ruler": () => document.body.classList.toggle("show-ruler"),
  });

  /* ---------- Archivo ---------- */
  emptyOpen.addEventListener("click", () => fileInput.click());
  analyzeBtn.addEventListener("click", () => runAnalysis());
  fileInput.addEventListener("change", () => {
    const f = fileInput.files[0];
    if (f) loadFile(f);
  });

  const canvas = document.getElementById("canvas");
  ["dragenter", "dragover"].forEach((ev) =>
    canvas.addEventListener(ev, (e) => {
      e.preventDefault();
      canvas.classList.add("dragging");
    })
  );
  ["dragleave", "drop"].forEach((ev) =>
    canvas.addEventListener(ev, (e) => {
      e.preventDefault();
      canvas.classList.remove("dragging");
    })
  );
  canvas.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files[0];
    if (f) loadFile(f);
  });

  // Debe coincidir con routes._text_key del backend (NFKD + sin diacriticos).
  function textKey(text, n) {
    n = n || 48;
    const s = String(text == null ? "" : text)
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^\p{L}\p{N}]+/gu, " ")
      .trim();
    return s.slice(0, n);
  }

  // Word mide el interlineado en multiplos de la ALTURA NATURAL de la fuente
  // (ascent + descent + separacion interna), que en Arial 11 es ~1.15 veces el
  // tamano de letra. CSS multiplica el tamano de letra, asi que al volcar
  // `line_spacing` tal cual, un doble espacio de Word salia un 15 % mas
  // apretado en el visor y cada pagina entran mas lineas de las que deberian
  // (la tesis se dividia en 29 hojas en vez de 33).
  function lineFactor(family, sizePx) {
    const size = parseFloat(sizePx) || 16;
    const fam = (family || "").split(",")[0].replace(/["']/g, "").trim() || "sans-serif";
    try {
      const ctx = document.createElement("canvas").getContext("2d");
      ctx.font = size + "px " + fam;
      // si el navegador rechaza la fuente conserva la anterior: se comprueba
      // que la asignacion haya cuajado antes de fiarse de las medidas
      if (Math.abs(parseFloat(ctx.font) - size) > 0.5) return 1.15;
      const m = ctx.measureText("Ág");
      if (m.fontBoundingBoxAscent && m.fontBoundingBoxDescent) {
        return (m.fontBoundingBoxAscent + m.fontBoundingBoxDescent) / size;
      }
    } catch (e) {
      /* navegadores sin fontBoundingBox: se usa el valor habitual */
    }
    return 1.15;
  }

  // mammoth descarta alineacion, interlineado, separaciones, tamanos, fuente y
  // saltos de pagina: todo eso se recupera del .docx via /api/docx-meta.
  async function enrichHtml(html) {
    if (!currentFile) return html;
    try {
      const data = new FormData();
      data.append("file", currentFile, currentFile.name);
      const res = await fetch("/api/docx-meta", { method: "POST", body: data });
      if (!res.ok) return html;
      const meta = await res.json();
      docSections = meta.sections && meta.sections.length ? meta.sections : null;

      // fuente y tamano por defecto del documento (Word los define en estilos)
      const defs = meta.defaults || {};
      if (defs.font) page.style.fontFamily = quoteFont(defs.font);
      if (defs.size_pt) page.style.fontSize = defs.size_pt + "pt";

      // tipografia real del documento: la que se usara para el factor de
      // interlineado. No puede ser la del parrafo, que al estar fuera de #page
      // heredaria la de la interfaz.
      const docFamily = (defs.font && quoteFont(defs.font)) || getComputedStyle(page).fontFamily;

      // cola de metadatos por clave: permite repetir la misma linea sin confundirse
      const queues = new Map();
      (meta.paragraphs || []).forEach((p) => {
        const k = p.key;
        if (!queues.has(k)) queues.set(k, []);
        queues.get(k).push(p);
      });

      const tmp = document.createElement("div");
      tmp.innerHTML = html;
      // getComputedStyle NO devuelve nada sobre un elemento desconectado del
      // documento, y el factor de interlineado depende justo de la fuente y el
      // tamano ya fijados. Por eso tmp se engancha fuera de pantalla mientras se
      // mide, y se retira antes de devolver el HTML.
      tmp.style.cssText = "position:absolute;left:-12000px;top:0;visibility:hidden;";
      document.body.appendChild(tmp);
      const blocks = Array.from(tmp.querySelectorAll("p,h1,h2,h3,h4,li"));
      blocks.forEach((el, i) => {
        const queue = queues.get(textKey(el.textContent));
        const info = queue && queue.length ? queue.shift() : null;
        if (!info) return;

        if (info.align && info.align !== "left") el.style.textAlign = info.align;
        // Espaciado "automático" de Word: con la casilla Auto puesta, Word
        // ignora el número y pone 14 pt (medido en Word para el cuerpo de
        // 12 pt). Si no se aplica, el párrafo sube 9 pt respecto al de arriba.
        const auto = Math.max(14, (info.size || 12) * 1.15);
        if (info.ab) el.style.marginTop = auto + "pt";
        else if (info.sb != null) el.style.marginTop = info.sb + "pt";
        if (info.aa) el.style.marginBottom = auto + "pt";
        else if (info.sa != null) el.style.marginBottom = info.sa + "pt";
        if (info.size) el.style.fontSize = info.size + "pt";
        // el factor se calcula con la FUENTE DEL DOCUMENTO (Arial en este caso)
        // y no con la que hereda el parrafo, que seria la de la interfaz
        if (info.ls) el.style.lineHeight = String(info.ls * lineFactor(docFamily, el.style.fontSize));

        // salto de pagina explicito antes de este parrafo
        if (info.pb && i > 0) {
          const br = document.createElement("div");
          br.className = "page-break";
          br.setAttribute("data-src", "word");
          el.parentNode.insertBefore(br, el);
        }
      });

      // Tamaño con el que el autor colocó cada figura en Word. Mammoth no lo
      // traslada al HTML, así que sin esto el paginador las pinta a su tamaño
      // natural en píxeles y una figura de 6 cm se ve ocupando la caja entera.
      // El orden del backend es el mismo en que mammoth emite los <img>.
      const imgs = Array.from(tmp.querySelectorAll("img"));
      (meta.images || []).forEach((s, i) => {
        const img = imgs[i];
        if (!img || !s) return;
        img.setAttribute("data-docx-w", s.width_cm);
        img.setAttribute("data-docx-h", s.height_cm);
        if (s.width_cm) img.style.width = s.width_cm + "cm";
        if (s.height_cm) img.style.height = s.height_cm + "cm";

        // Imagen FLOTANTE: en Word está anclada a un punto de la página y NO
        // ocupa altura de línea; el texto sigue como si no estuviera. Si se
        // pinta como imagen normal, el párrafo crece lo que mida la figura y
        // todo lo que viene detrás baja. En la portada el logo mide 78 pt y
        // Word le da 0: por eso la portada salía empujada media hoja.
        if (!s.anchored) return;
        const holder = img.parentElement;
        if (!holder) return;
        holder.style.position = "relative";
        // El párrafo que solo lleva la imagen anclada sigue siendo UNA línea en
        // Word (la de su marca de párrafo). Al sacar la imagen del flujo se
        // queda sin contenido y mediría 0: se le devuelve esa línea.
        if (!holder.textContent.replace(/\u00a0/g, " ").trim()) {
          holder.style.minHeight = "1.15em";
        }
        img.style.position = "absolute";
        img.style.left = (s.offset_h_pt || 0) + "pt";
        img.style.top = (s.offset_v_pt || 0) + "pt";
        img.style.margin = "0";
        img.style.zIndex = s.behind ? "0" : "3";
        img.setAttribute("data-anchored", "1");
      });

      // Alto real de los párrafos vacíos: lo fija el tamaño de su marca de
      // párrafo, no el del texto (que no hay). Los espaciadores de la portada
      // escritos con la marca a 18 pt miden 20.7 pt en Word; pintados con los
      // 12 pt por defecto miden 13.8 pt y el bloque de abajo sube 7 pt cada
      // uno. Se emparejan por orden con los <p> en blanco del flujo.
      const blanks = blocks.filter(
        (el) =>
          /^P$/i.test(el.tagName) &&
          !el.querySelector("img") &&
          !el.closest("td,th") &&
          !el.textContent.replace(/\u00a0/g, " ").trim()
      );
      (meta.empty_marks || []).forEach((pt, i) => {
        if (pt == null || !blanks[i]) return;
        blanks[i].style.fontSize = pt + "pt";
      });

      const out = tmp.innerHTML;
      document.body.removeChild(tmp);
      return out;
    } catch (e) {
      return html;
    }
  }

  function quoteFont(name) {
    const f = String(name || "").trim();
    if (!f) return "";
    return /[a-zA-Z]/.test(f) && !/^["']/.test(f) && !/,/.test(f) ? "'" + f.replace(/'/g, "") + "'" : f;
  }

  /* mammoth BORRA los parrafos vacios del .docx, y en Word son espaciadores de
     verdad: las portadas de tesis se empujan hacia abajo con ellos. Al quitarlos
     la portada salia hasta 3 pulgadas mas corta que en Word: las lineas se
     apelotonaban arriba y el "2026" del pie subia de sitio (o se caia a la hoja
     siguiente si el resto del texto lo empujaba).
     El modelo de documento de mammoth SI conserva esos parrafos (solo los
     descarta al generar el HTML), asi que aqui se les anade un espacio duro: el
     generador emite <p>&nbsp;</p> y la linea recupera su altura. */
  function keepEmptyParagraphs(doc) {
    const walk = (el) => {
      if (!el || typeof el !== "object") return;
      if (el.type === "paragraph" && (!el.children || el.children.length === 0)) {
        el.children = [{ type: "run", children: [{ type: "text", value: "\u00a0" }] }];
      }
      (el.children || []).forEach(walk);
    };
    walk(doc);
    return doc;
  }

  /* Devuelve el HTML del flujo de una sesion guardada.
     Si la sesion se creo con una version anterior del conversor, el HTML que
     trae no tiene los arreglos posteriores (por ejemplo los parrafos vacios de
     la portada) y el documento se veria igual que antes aunque el codigo ya
     este corregido: se rehace la conversion desde el .docx original, que la
     sesion guarda en `bytes`. Si no hay bytes o algo falla, se usa el guardado.

     OJO: al reconvertir se parte del .docx original, asi que las ediciones
     hechas a mano en el visor de esa sesion vieja no se conservan. Por eso
     flowRegenerated queda marcado y restoreSession avisa al usuario. */
  let flowRegenerated = false;
  // la sesion es de un conversor anterior y no se pudo rehacer (no hay .docx):
  // se queda como estaba, pero hay que decirlo en vez de dejar al usuario
  // mirando una portada que "sigue igual" sin saber por que.
  let flowStale = false;
  async function flowForSession(doc) {
    if (!doc) return "";
    if (doc.flowVersion === FLOW_VERSION) return doc.flow || "";
    if (!doc.bytes) {
      flowStale = true;
      return doc.flow || "";
    }
    try {
      const result = await mammoth.convertToHtml(
        { arrayBuffer: new Uint8Array(doc.bytes) },
        { transformDocument: keepEmptyParagraphs }
      );
      const html = await enrichHtml(result.value || "<p></p>");
      flowRegenerated = true;
      return html;
    } catch (e) {
      flowStale = true;
      return doc.flow || "";
    }
  }

  // Reajusta las imagenes cuando ya han cargado. Antes se usaba el evento 'load'
  // de la ventana, que ya se habia disparado al abrir la app: por eso nunca
  // corria para los documentos cargados despues.
  let refitTimer = null;
  function scheduleRefit() {
    clearTimeout(refitTimer);
    refitTimer = setTimeout(() => {
      if (!page.hidden && Pager.refit(page)) {
        Pager.paginate(page, docSections);
        updateTocPages();
        updateCountsDebounced();
        // la repaginacion por imagenes recarga forma parte de la carga, no es
        // un cambio del usuario: no debe aparecer como paso deshacible
        History.reset();
      }
    }, 600);
  }

  function loadFile(file) {
    if (!file.name.toLowerCase().endsWith(".docx")) {
      showToast("Solo se aceptan archivos .docx", "error");
      return;
    }
    currentFile = file;
    docName.textContent = file.name;
    analyzeBtn.disabled = false;
    saveBtn.disabled = false;
    Library.record(file).catch(() => {
      // la biblioteca es una comodidad: si falla, el editor sigue igual
    });
    markDirty(false);
    

    const reader = new FileReader();
    reader.onload = () => {
      mammoth
        .convertToHtml(
          { arrayBuffer: reader.result },
          { transformDocument: keepEmptyParagraphs }
        )
        .then((result) => enrichHtml(result.value || "<p></p>"))
        .then(async (html) => {
          page.innerHTML = html;
          buildIndex();
          Pager.paginate(page, docSections);
          // las imagenes pueden terminar de cargar despues: se reajustan y se repagina
          scheduleRefit();
          updateTocPages();
          page.contentEditable = "true";
          emptyState.hidden = true;
          page.hidden = false;
          clearMarks();
          resetReport();
          updateCounts();
          // Si esta tesis ya se habia verificado, se recupera su ultimo informe:
          // se puede leer al abrir sin volver a gastar una verificacion.
          const previo = await Library.getReport(file.name);
          const restaurado = restoreReportState(previo, true);
          // el documento que se acaba de abrir es el punto de partida
          History.reset();
          showToast(
            restaurado
              ? "Documento cargado con su ultimo informe guardado."
              : "Documento cargado. Edita y pulsa 'Verificar APA'.",
            "ok"
          );
          // guardar la sesion automaticamente para que al recargar la web
          // se restaure ESTE documento y no el anterior
          saveSession(true);
        })
        .catch((err) => showToast("No se pudo abrir el documento: " + err.message, "error"));
    };
    reader.readAsArrayBuffer(file);
  }

  function toggleReading() {
    reading = !reading;
    page.contentEditable = reading ? "false" : "true";
    document.body.classList.toggle("reading", reading);
    // Fuera de la edicion no se muestra la barra horizontal del visor: el
    // documento puede desbordarse, pero sin barra visible.
    canvas.classList.toggle("no-scrollbar", reading);
    showToast(reading ? "Modo lectura activado" : "Edición activada", "ok");
  }

  // Vista PDF fiel: Word convierte el .docx y se muestra el PDF en una capa.
  // Sirve para comprobar que el contenido no se mueve respecto al archivo
  // original. La edicion y las marcas siguen en el visor HTML.
  async function togglePdfView() {
    const existing = document.getElementById("pdf-overlay");
    if (existing) {
      existing.remove();
      return;
    }
    if (!currentFile) {
      showToast("Primero abre un documento .docx", "error");
      return;
    }
    showToast("Generando vista PDF con Word...", "ok");
    try {
      const data = new FormData();
      data.append("file", currentFile, currentFile.name);
      const res = await fetch("/api/docx-pdf", { method: "POST", body: data });
      if (!res.ok) {
        let detail = "No se pudo generar el PDF.";
        try {
          const j = await res.json();
          if (j && j.detail) detail = j.detail;
        } catch (e) {
          /* respuesta sin JSON */
        }
        showToast(detail, "error");
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const overlay = document.createElement("div");
      overlay.id = "pdf-overlay";
      overlay.innerHTML =
        '<div class="pdf-overlay-bar">' +
        '<span>Vista PDF (Word)</span>' +
        '<button type="button" id="pdf-close" title="Cerrar">Cerrar</button>' +
        "</div>" +
        '<iframe id="pdf-frame" title="Vista PDF del documento"></iframe>';
      document.body.appendChild(overlay);
      const frame = overlay.querySelector("#pdf-frame");
      frame.src = url;
      frame.addEventListener("load", () => URL.revokeObjectURL(url), { once: true });
      overlay.querySelector("#pdf-close").addEventListener("click", () => {
        overlay.remove();
      });
    } catch (e) {
      showToast("No se pudo generar la vista PDF.", "error");
    }
  }

  function repaginate() {
    Pager.paginate(page, docSections);
    updateTocPages();
    updateCounts();
    showToast("Páginas reorganizadas. Se puede deshacer con Ctrl+Z.", "ok");
  }

  /* ---------- Revision asistida por IA ---------- */
  let aiFindings = [];
  let lastFindings = [];
  let lastSummary = null;

  // El consentimiento vive en sessionStorage: vale para esta sesion de trabajo y
  // desaparece al cerrar la pestana. Nunca en localStorage, para no dejar un
  // permiso permanente que envie datos del documento fuera del equipo.
  const AI_CONSENT_KEY = "apa.ai.consent";

  function hasAiConsent() {
    try {
      return sessionStorage.getItem(AI_CONSENT_KEY) === "1";
    } catch (e) {
      return false;
    }
  }

  function grantAiConsent() {
    try {
      sessionStorage.setItem(AI_CONSENT_KEY, "1");
    } catch (e) {
      /* modo privado: el consentimiento dura solo la sesion en memoria */
    }
  }

  function revokeAiConsent() {
    try {
      sessionStorage.removeItem(AI_CONSENT_KEY);
    } catch (e) {
      /* sin persistencia */
    }
    showToast("Consentimiento de IA revocado: no se enviarán más datos.", "info");
  }

  // Dialogo de vista previa + consentimiento. Todo lo que muestra viene de
  // /api/ai/preview, que no contacta con el proveedor: solo describe el alcance.
  function askAiConsent(preview) {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.className = "ai-consent-overlay";
      const campos = (preview.fields || []).map((f) => `<code>${escapeHtml(f)}</code>`).join(" ");
      overlay.innerHTML = `
        <div class="ai-consent" role="dialog" aria-modal="true" aria-labelledby="ai-consent-t">
          <h2 id="ai-consent-t">Revisión con IA: datos que se enviarán</h2>
          <p>La revisión con IA envía <strong>solo las referencias y citas detectadas</strong>,
             nunca el texto completo de la tesis.</p>
          <ul class="ai-consent-list">
            <li><b>${preview.references || 0}</b> referencias</li>
            <li><b>${preview.citations || 0}</b> citas</li>
            <li>Máximo <b>${preview.chars_max || 0}</b> caracteres</li>
            <li>Proveedor: <b>${escapeHtml(preview.provider || "")}</b> · modelo <b>${escapeHtml(preview.model || "")}</b></li>
          </ul>
          <p class="ai-consent-fields">Campos: ${campos}</p>
          <p class="ai-consent-note">El consentimiento vale para esta sesión. Puedes revocarlo
             desde la cinta (Revisar APA â†’ Quitar consentimiento IA).</p>
          <div class="ai-consent-actions">
            <button type="button" data-act="no">Cancelar</button>
            <button type="button" class="primary" data-act="si">Autorizar y revisar</button>
          </div>
        </div>`;
      document.body.appendChild(overlay);
      const cerrar = (valor) => {
        overlay.remove();
        document.removeEventListener("keydown", onKey);
        resolve(valor);
      };
      const onKey = (e) => {
        if (e.key === "Escape") cerrar(false);
      };
      document.addEventListener("keydown", onKey);
      overlay.querySelector('[data-act="no"]').addEventListener("click", () => cerrar(false));
      overlay.querySelector('[data-act="si"]').addEventListener("click", () => cerrar(true));
      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) cerrar(false);
      });
    });
  }

  async function runAiReview() {
    if (!currentFile) {
      showToast("Primero abre un documento .docx", "error");
      return;
    }
    // 1) Consentimiento: si no lo hay, se muestra la vista previa y se pide.
    if (!hasAiConsent()) {
      statusMsg.textContent = "Preparando vista previa de IA...";
      let preview;
      try {
        const pv = new FormData();
        pv.append("file", currentFile, currentFile.name);
        const res = await fetch("/api/ai/preview", { method: "POST", body: pv });
        preview = await res.json();
        if (!res.ok) throw new Error(preview.detail || "Error " + res.status);
      } catch (err) {
        statusMsg.textContent = "";
        showToast("No se pudo preparar la vista previa de IA: " + err.message, "error");
        return;
      }
      statusMsg.textContent = "";
      if (!preview.ai_enabled) {
        showToast("La revisión con IA no está habilitada (falta la clave del proveedor).", "error");
        return;
      }
      const autorizado = await askAiConsent(preview);
      if (!autorizado) {
        showToast("Revisión con IA cancelada. No se envió nada.", "info");
        return;
      }
      grantAiConsent();
    }

    // 2) Revision: solo ahora se contacta con el proveedor.
    statusMsg.textContent = "Consultando a la IA...";
    const data = new FormData();
    data.append("file", currentFile, currentFile.name);
    data.append("consent", "1");
    try {
      const res = await fetch("/api/ai/classify", { method: "POST", body: data });
      const payload = await res.json();
      if (res.status === 428) {
        revokeAiConsent();
        statusMsg.textContent = "";
        showToast("El servidor exige consentimiento; vuelve a intentarlo.", "error");
        return;
      }
      if (!res.ok) throw new Error(payload.detail || "Error " + res.status);
      if (!payload.ai_enabled) {
        showToast("La revisión con IA no está habilitada (falta la clave del proveedor).", "error");
        statusMsg.textContent = "";
        return;
      }
      aiFindings = payload.findings || [];
      if (!lastFindings.length) await runAnalysisQuiet();
      renderReport({ summary: lastSummary, findings: lastFindings.concat(aiFindings) });
      openReportes();
      // el resultado con IA tambien queda guardado hasta la proxima verificacion
      persistReport();
      (payload.notes || []).forEach((n) => showToast(n, "info"));
      statusMsg.textContent = "";
      showToast(
        aiFindings.length
          ? "IA: " + aiFindings.length + " sugerencia(s) con " + (payload.model || "")
          : "IA (" + (payload.model || "") + "): sin sugerencias",
        aiFindings.length ? "ok" : "info"
      );
    } catch (err) {
      statusMsg.textContent = "";
      showToast("La revisión con IA falló: " + err.message, "error");
    }
  }


  /* ---------- Indice: numeros de pagina reales tras la paginacion ---------- */
  function updateTocPages() {
    // El indice puede ocupar mas de una hoja: el paginador lo parte en varios
    // bloques .doc-toc. Hay que recorrerlos TODOS, no solo el primero, o las
    // entradas de la continuacion se quedan sin numero de pagina.
    const tocs = Array.from(page.querySelectorAll(".doc-toc"));
    if (!tocs.length) return;
    const entries = [];
    tocs.forEach((t) => {
      Array.prototype.push.apply(entries, Array.prototype.slice.call(t.querySelectorAll(".toc-entry")));
    });
    if (!entries.length) return;
    let i = 0;
    let last = "1";
    page.querySelectorAll(".sheet").forEach((sheet, si) => {
      sheet.querySelectorAll("h1,h2,h3").forEach((h) => {
        // el propio titulo del indice no genera entrada: tampoco debe desplazar
        if (h.dataset.tocSkip === "1") return;
        const entry = entries[i++];
        if (!entry) return;
        last = String(si + 1);
        h.dataset.tocPage = last;
        const span = entry.querySelector(".toc-page");
        if (span) span.textContent = last;
      });
    });
    // titulos que no quedaron visibles (por ejemplo dentro de una tabla) usan la ultima pagina
    for (; i < entries.length; i++) {
      const span = entries[i].querySelector(".toc-page");
      if (span) span.textContent = last;
    }
  }

  /* ---------- Comandos del documento ---------- */
  function insertHtml(html) {
    Commands.focusPage();
    document.execCommand("insertHTML", false, html);
    updateCounts();
  }

  function insertTable() {
    let html = '<table class="doc-table">';
    for (let r = 0; r < 3; r++) {
      html += "<tr>";
      for (let c = 0; c < 3; c++) html += "<td><br></td>";
      html += "</tr>";
    }
    html += "</table><p><br></p>";
    insertHtml(html);
  }

  function pickImage() {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.accept = "image/*";
    inp.onchange = () => {
      const f = inp.files[0];
      if (!f) return;
      const r = new FileReader();
      r.onload = () => insertHtml('<img src="' + r.result + '" style="max-width:100%">');
      r.readAsDataURL(f);
    };
    inp.click();
  }

  function insertLink() {
    const url = window.prompt("Dirección del enlace (https://...):");
    if (!url) return;
    Commands.focusPage();
    document.execCommand("createLink", false, url);
    updateCounts();
  }


  function applyApaDefaults() {
    page.style.fontFamily = "'Times New Roman', serif";
    page.style.fontSize = "12pt";
    page.style.lineHeight = "2";
    page.querySelectorAll(".sheet").forEach((s) => {
      Array.from(s.children).forEach((el) => {
        if (el.classList.contains("sheet-num")) return;
        el.style.fontFamily = "'Times New Roman', serif";
        el.style.fontSize = "12pt";
        // mismo criterio que al importar el .docx: el 2 es el doble espacio de
        // Word, medido sobre la altura natural de la fuente
        el.style.lineHeight = String(2 * lineFactor("'Times New Roman', serif", el.style.fontSize));
        el.style.textAlign = "left";
        if (el.tagName === "P") {
          el.style.textIndent = "1.27cm";
          el.style.margin = "0";
        }
      });
    });
    Pager.paginate(page, docSections);
    updateCounts();
    showToast("Formato base APA aplicado (2.0, Times New Roman 12, sangría). Se puede deshacer con Ctrl+Z.", "ok");
  }

  function clearMarks() {
    Marker.clear();
    page.querySelectorAll(".finding-hit").forEach((el) => el.classList.remove("finding-hit"));
  }

  /* ---------- Analisis ---------- */
  // ejecuta el informe sin mensajes: lo usa la revision con IA cuando el
  // usuario aun no pulso "Verificar documento"
  async function runAnalysisQuiet() {
    if (!currentFile) return;
    try {
      const data = new FormData();
      data.append("file", currentFile, currentFile.name);
      const res = await fetch("/api/analyze", { method: "POST", body: data });
      if (!res.ok) return;
      const report = await res.json();
      lastFindings = report.findings || [];
      lastSummary = report.summary || null;
    } catch (e) {
      /* el informe por IA continuara igual */
    }
  }

  async function runAnalysis() {
    if (!currentFile) {
      showToast("Primero abre un documento .docx", "error");
      return;
    }
    analyzeBtn.disabled = true;
    statusMsg.textContent = "Analizando...";
    const data = new FormData();
    data.append("file", currentFile, currentFile.name);
    try {
      const res = await fetch("/api/analyze", { method: "POST", body: data });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Error" }));
        throw new Error(err.detail || "Error " + res.status);
      }
      const report = await res.json();
      renderReport(report);
      // el recuadro del informe aparece junto al documento
      openPane();
      // se guarda el informe en la sesion: al reiniciar se vuelve a mostrar
      // este mismo resultado y no hay que volver a verificar
      persistReport();
      statusMsg.textContent = "";
      const total = (report.summary && report.summary.total_findings) || (report.findings || []).length;
      showToast("Informe generado: " + total + " hallazgos.", "ok");
    } catch (err) {
      statusMsg.textContent = "";
      showToast("No se pudo analizar: " + err.message, "error");
    } finally {
      analyzeBtn.disabled = false;
    }
  }

  /* ---------- Panel del informe junto al documento ----------
     Recuadro lateral con los errores, advertencias y observaciones del
     documento. Se abre al pulsar "Verificar documento" y se cierra con la X. */
  function openPane() {
    if (!reportPane) return;
    reportPane.hidden = false;
    renderPane();
  }

  function closePane() {
    if (!reportPane) return;
    reportPane.hidden = true;
  }

  function togglePane() {
    if (!reportPane) return;
    if (reportPane.hidden) openPane();
    else closePane();
  }

  function renderPane() {
    if (!reportPane) return;
    const c = countBy(currentFindings);
    const score =
      lastSummary && lastSummary.compliance_score != null ? lastSummary.compliance_score : null;
    if (paneScore) paneScore.textContent = score == null ? "--" : score;
    const ring = reportPane.querySelector(".score-ring");
    if (ring) {
      const pct = score == null ? 0 : Math.max(0, Math.min(100, Number(score) || 0));
      ring.style.setProperty("--pct", String(pct));
      ring.style.setProperty(
        "--ring-color",
        score == null
          ? "var(--accent-soft)"
          : pct < 50
            ? "var(--error)"
            : pct < 75
              ? "var(--warning)"
              : "var(--accent)"
      );
    }
    if (paneCards) {
      paneCards.innerHTML = [
        ["error", c.error || 0, "Errores"],
        ["warning", c.warning || 0, "Avisos"],
        ["info", c.info || 0, "Observ."],
        ["", c.all || 0, "Total"],
      ]
        .map(
          ([clase, valor, texto]) =>
            `<div class="pane-card ${clase}"><div class="pc-num">${valor}</div><div class="pc-label">${texto}</div></div>`
        )
        .join("");
    }
    if (paneFilters) {
      const filtros = [
        ["all", "Todos"],
        ["error", "Errores"],
        ["warning", "Avisos"],
        ["info", "Observ."],
      ];
      paneFilters.innerHTML = filtros
        .map(
          ([k, texto]) =>
            `<button data-pfilter="${k}" class="${paneFilter === k ? "active" : ""}">${texto} <b>${c[k] || 0}</b></button>`
        )
        .join("");
      paneFilters.querySelectorAll("[data-pfilter]").forEach((b) =>
        b.addEventListener("click", () => {
          paneFilter = b.dataset.pfilter;
          renderPane();
        })
      );
    }
    if (!paneFindings) return;
    // chips de categoria: se abren con el boton de embudo
    const cats = new Map();
    currentFindings.forEach((f) => {
      const k = f.category || "Sin categoría";
      cats.set(k, (cats.get(k) || 0) + 1);
    });
    const listaCats = Array.from(cats.entries()).sort((a, b) => b[1] - a[1]);
    if (paneCats) {
      if (!listaCats.length) {
        paneCats.innerHTML = "";
      } else {
        paneCats.innerHTML = [
          `<button data-pcat="" class="${paneCategory ? "" : "active"}">Todas <b>${currentFindings.length}</b></button>`,
        ]
          .concat(
            listaCats.map(
              ([c, n]) =>
                `<button data-pcat="${escapeHtml(c)}" class="${paneCategory === c ? "active" : ""}">${escapeHtml(c)} <b>${n}</b></button>`
            )
          )
          .join("");
        paneCats.querySelectorAll("[data-pcat]").forEach((b) =>
          b.addEventListener("click", () => {
            paneCategory = b.dataset.pcat || "";
            renderPane();
          })
        );
      }
    }
    const lista = currentFindings.filter(
      (f) =>
        (paneFilter === "all" || f.severity === paneFilter) &&
        (!paneCategory || f.category === paneCategory)
    );
    if (!lista.length) {
      paneFindings.innerHTML = `<p class="empty-pane">${
        currentFindings.length
          ? "Sin hallazgos con estos filtros."
          : "Aún no se ha verificado el documento."
      }</p>`;
      return;
    }
    paneFindings.innerHTML = lista
      .map((f) => {
        const idx = currentFindings.indexOf(f);
        return `<article class="finding ${escapeHtml(f.severity || "")}" data-pi="${idx}">
          <div class="finding-rail">
            <span class="dot">${SEVERITY_ICON[f.severity] || ""}</span>
            <span class="finding-sev">${SEV_TEXT[f.severity] || ""}</span>
          </div>
          <div class="finding-body">
            <div class="finding-head">
              <span class="finding-cat">${escapeHtml(f.category || "")}</span>
              <span class="finding-rule">${escapeHtml(f.rule_id || "")}</span>
            </div>
            <p class="finding-msg">${escapeHtml(f.message || "")}</p>
            ${
              f.suggestion
                ? `<p class="finding-sug"><b>Sugerencia:</b> ${escapeHtml(f.suggestion)}</p>`
                : ""
            }
          </div>
        </article>`;
      })
      .join("");
    paneFindings.querySelectorAll(".finding").forEach((art) =>
      art.addEventListener("click", () => {
        const f = currentFindings[Number(art.dataset.pi)];
        if (f) jumpToFinding(f);
      })
    );
  }

  if (paneClose) paneClose.addEventListener("click", closePane);
  if (paneAll) paneAll.addEventListener("click", () => openReportes());
  if (paneFiltersBtn) {
    paneFiltersBtn.addEventListener("click", () => {
      if (!paneCats) return;
      const visible = paneCats.hasAttribute("hidden");
      if (visible) paneCats.removeAttribute("hidden");
      else paneCats.setAttribute("hidden", "");
      paneFiltersBtn.classList.toggle("active", visible);
      paneFiltersBtn.setAttribute("aria-expanded", visible ? "true" : "false");
    });
  }

  /* El informe ya no se dibuja en un panel pegado al documento: la vista
     "Reportes" lo pinta a partir de este estado. */
  function openReportes() {
    Router.go("reportes");
  }

  // Indices (sobre allFindings) de los avisos YA CORREGIDOS. Se guarda el
  // aviso concreto y no la regla entera: corregir un parrafo no puede tapar
  // los demas avisos de esa misma regla, que siguen siendo reales.
  const resolvedIdx = new Set();

  function resetReport() {
    currentFindings = [];
    lastFindings = [];
    allFindings = [];
    lastSummary = null;
    aiFindings = [];
    resolvedIdx.clear();
    if (paneFindings) {
      paneFindings.innerHTML = '<p class="empty-pane">Aún no se ha verificado el documento.</p>';
    }
    if (paneCards) paneCards.innerHTML = "";
    if (paneFilters) paneFilters.innerHTML = "";
    if (paneCats) {
      paneCats.innerHTML = "";
      paneCats.setAttribute("hidden", "");
    }
    if (paneFiltersBtn) {
      paneFiltersBtn.classList.remove("active");
      paneFiltersBtn.setAttribute("aria-expanded", "false");
    }
    paneCategory = "";
    if (paneScore) paneScore.textContent = "--";
    notifyChange();
  }

  // De la copia integra se descuenta lo ya corregido, aviso a aviso.
  function refreshCurrentFindings() {
    currentFindings = [];
    allFindings.forEach((f, i) => {
      if (!resolvedIdx.has(i)) currentFindings.push(f);
    });
  }

  // Copia serializable del informe: viaja en la sesion y en la biblioteca para
  // que al reiniciar se pueda mostrar de nuevo sin volver a verificar.
  function reportSnapshot() {
    return {
      summary: lastSummary,
      findings: allFindings.slice(),
      resolved: Array.from(resolvedIdx),
      generatedAt: new Date().toISOString(),
    };
  }

  // Guarda el informe vigente en la sesion y en la biblioteca. Se llama al
  // verificar, al revisar con IA y al corregir avisos: el estado queda
  // disponible tras reiniciar sin volver a gastar la verificacion.
  function persistReport() {
    if (!currentFile) return;
    saveSession(true);
    Library.syncAnalysis(lastSummary, currentFile.name, reportSnapshot()).catch(() => {
      /* sin biblioteca no se rompe nada */
    });
  }

  // Vuelve a poner en pantalla un informe ya generado. `quiet` evita los avisos
  // de "texto marcado" al restaurar (no es una accion del usuario).
  function restoreReportState(data, quiet) {
    if (!data) return false;
    const summary = data.summary || null;
    const findings = Array.isArray(data.findings) ? data.findings : [];
    if (!summary && !findings.length) return false;
    lastSummary = summary;
    allFindings = findings;
    lastFindings = allFindings;
    resolvedIdx.clear();
    (Array.isArray(data.resolved) ? data.resolved : []).forEach((i) => resolvedIdx.add(i));
    refreshCurrentFindings();
    markInDocument(quiet);
    updateCounts();
    if (reportPane && !reportPane.hidden) renderPane();
    notifyChange();
    return true;
  }

  function renderReport(report) {
    const s = report.summary || {};
    lastSummary = s;
    if (!report.partial) {
      // informe nuevo: esta es la copia integra y se reinicia lo ya corregido
      allFindings = report.findings || [];
      resolvedIdx.clear();
      lastFindings = allFindings;
    }
    refreshCurrentFindings();
    markInDocument();
    // el panel del informe se repinta con estos numeros
    if (reportPane && !reportPane.hidden) renderPane();
    // la vista Reportes y el panel de Inicio se repintan con estos numeros
    notifyChange();
  }

  /* ---------- Senalar los problemas dentro del texto ---------- */
  let marksVisible = true;

  function markInDocument(quiet) {
    if (!marksVisible) return;
    if (page.hidden || !currentFindings.length) {
      Marker.clear();
      return;
    }
    const res = Marker.apply(currentFindings);
    if (res.marks || res.blocks) {
      if (!quiet) {
        showToast(
          (res.marks ? res.marks + " texto(s) marcados" : "") +
            (res.blocks ? " y " + res.blocks + " párrafo(s)" : "") +
            " en el documento",
          "info"
        );
      }
    }
    if (res.unmatched && !quiet) {
      showToast(
        res.unmatched + " aviso(s) no se pudieron ubicar en el texto",
        "info"
      );
    }
  }

  function countBy(list) {
    const c = { all: list.length, error: 0, warning: 0, info: 0 };
    (list || []).forEach((f) => (c[f.severity] = (c[f.severity] || 0) + 1));
    return c;
  }

  /* Estado del informe para la vista "Reportes" y el panel de Inicio. */
  function reportState() {
    return {
      ready: lastSummary != null || allFindings.length > 0,
      summary: lastSummary,
      findings: currentFindings.slice(),
      counts: countBy(currentFindings),
      hasFile: !!currentFile,
    };
  }

  function normKey(t) {
    return (t || "").toLowerCase().replace(/[^a-z0-9\u00e0-\u00ff]+/g, " ").trim();
  }

  // Detecta una entrada de indice estatico viejo (escrito a mano o campo TOC de Word):
  // "Introduccion ............ 3", "1. Introduccion     3", "Introduccion\t3", etc.
  function isOldTocEntry(el, headingKeys) {
    if (!el || el.nodeType !== 1) return false;
    if (!/^(P|DIV|LI)$/.test(el.tagName)) return false;
    if (el.classList.contains("doc-toc")) return false;
    // nada de lo que hay dentro del indice generado se toma por indice viejo
    if (el.closest && el.closest(".doc-toc")) return false;
    const raw = (el.textContent || "").replace(/\u00a0/g, " ");
    const t = raw.trim();
    if (!t) return false;
    const hasTailNum = /\d{1,3}\s*$/.test(t);
    const hasLeader = /\.{3,}|\u2026{2,}| {2,}|\t|\u00b7{3,}/.test(raw);
    const body = raw
      .replace(/[\s.\u2026\u00b7]*\d{1,3}\s*$/, "")
      .replace(/[\s.]+$/, "")
      .trim();
    const headKey = normKey(body);
    const headMatch = headingKeys.some(
      (hk) =>
        headKey &&
        (headKey === hk ||
          headKey.startsWith(hk) ||
          hk.startsWith(headKey) ||
          headKey.endsWith(hk) ||
          hk.endsWith(headKey))
    );
    return headMatch && (hasTailNum || hasLeader);
  }

  // Algunas tesis ponen el indice como tabla de dos columnas (Titulo | Pagina).
  // Devuelve cuantas filas coinciden con encabezados (0 = no es indice viejo).
  function isOldTocTable(el, headingKeys) {
    if (!el || el.nodeType !== 1 || el.tagName !== "TABLE") return 0;
    const rows = Array.from(el.querySelectorAll("tr"));
    if (!rows.length) return 0;
    let ok = 0;
    rows.forEach((tr) => {
      const cells = Array.from(tr.querySelectorAll("td,th")).map((c) => c.textContent.trim());
      if (cells.length < 2) return;
      const key = normKey(cells[0]);
      const page = cells[cells.length - 1];
      if (
        /^\d{1,3}$/.test(page) &&
        headingKeys.some((hk) => key === hk || key.startsWith(hk) || key.endsWith(hk) || hk.startsWith(key) || hk.endsWith(key))
      )
        ok++;
    });
    return ok;
  }

  const TOC_SCAN_LIMIT = 80; // el indice siempre esta al principio del documento

  function isInlineTag(tag) {
    return /^(A|B|STRONG|I|EM|U|SUP|SUB|SMALL|BR|SPAN|IMG|TIME|CODE|MARK|SUB|SUP)$/.test(tag);
  }

  // Word envuelve las entradas del campo TOC en un contenedor (o las mete en una lista).
  // Si un elemento tiene >=2 hijos que ya son entradas de indice, se despliega a sus hijos.
  function expandEntryContainer(el, headingKeys, wrappers) {
    const kids = Array.from(el.children).filter((k) => k.nodeType === 1 && !isInlineTag(k.tagName));
    if (kids.length >= 2) {
      const matched = kids.filter((k) => isOldTocEntry(k, headingKeys) || isOldTocTable(k, headingKeys));
      if (matched.length >= 2) {
        wrappers.push(el);
        return kids;
      }
    }
    return [el];
  }

  function removeOldToc(root, headingKeys) {
    if (!headingKeys.length) return;
    const wrappers = [];
    const flat = [];
    Array.from(root.children).forEach((c) => {
      // Tras paginar, el flujo vive dentro de hojas .sheet. Hay que bajar a
      // ellas para encontrar las entradas viejas, pero una hoja NUNCA se
      // elimina: contiene mucho mas que el indice. Antes se tomaba la hoja
      // entera como "contenedor" y al reconstruir el indice se comia paginas
      // completas del documento (13 titulos y 5 hojas de la nada).
      if (c.classList && c.classList.contains("sheet")) {
        Array.from(c.children).forEach((k) => {
          if (k.classList && k.classList.contains("sheet-num")) return;
          expandEntryContainer(k, headingKeys, wrappers).forEach((e) => flat.push(e));
        });
        return;
      }
      expandEntryContainer(c, headingKeys, wrappers).forEach((e) => flat.push(e));
    });

    let run = [];
    const flush = () => {
      if (run.length >= 2) run.forEach((n) => n.remove());
      run = [];
    };
    flat.slice(0, TOC_SCAN_LIMIT).forEach((el) => {
      if (isOldTocEntry(el, headingKeys) || isOldTocTable(el, headingKeys)) run.push(el);
      else flush();
    });
    flush();

    // si al vaciar las entradas el contenedor quedo sin contenido, tambien se quita
    wrappers.forEach((w) => {
      if (w.isConnected && !w.textContent.trim() && !w.querySelector("img")) w.remove();
    });
  }

  function buildIndex() {
    const headings = Array.from(page.querySelectorAll("h1,h2,h3")).filter(
      (h) => h.id || /[a-záéíóúñ]{4,}/i.test(h.textContent || "")
    );
    if (!headings.length) return;

    const keys = headings.map((h) => normKey(h.textContent));
    removeOldToc(page, keys);

    // Titulo donde debe ir el indice. Antes solo aceptaba la palabra exacta
    // ("Indice"), asi que un documento titulado "Indice de Contenidos" se
    // quedaba sin ancla y el indice generado acababa DELANTE de la portada.
    // Se comparan sin tildes: el titulo viene con mayusculas y acentos.
    const normToc = (t) =>
      (t || "")
        .trim()
        .replace(/\s+/g, " ")
        .replace(/[.:;]+$/, "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
    const esIndiceDe = (s) =>
      /^(indice|tabla|contenido)\s+de\s+(contenidos?|tablas?|graficos?|figuras?|anexos|ilustraciones)\b/.test(s);
    const esIndice = (s) => /^(indice|contenido|contenidos|sumario)\b/.test(s);
    const candidatos = headings.filter((h) => {
      const s = normToc(h.textContent);
      return esIndice(s) || esIndiceDe(s);
    });
    // antes el indice de tablas, el de graficos o el de anexos que el de
    // contenidos: si solo hay uno de esos, se usa como ancla igualmente
    const heading =
      candidatos.find((h) => /contenido/.test(normToc(h.textContent))) || candidatos[0] || null;
    let anchor = heading || null;

    const toc = document.createElement("div");
    toc.className = "doc-toc";
    toc.appendChild(el("div", "toc-title-row", "Contenido"));
    if (heading) heading.dataset.tocSkip = "1"; // no es una entrada del indice

    const counters = [0, 0, 0];
    let serial = 0;
    headings.forEach((h) => {
      if (h === heading) return;
      const level = Math.min(3, Number(h.tagName[1]));
      counters[level - 1] += 1;
      for (let i = level; i < 3; i++) counters[i] = 0;
      const autoNum = counters.slice(0, level).join(".");
      // si el titulo ya trae su propia numeracion ("1.", "2.1.", "4.1.1.") se respeta
      const rawText = (h.textContent || "").trim();
      const m = rawText.match(/^\s*(\d+(?:[.)\s]\d+)*[.)])\s+/);
      const docNum = m ? m[1].replace(/[.)]+$/, "") : "";
      const num = docNum || autoNum;
      const title = m ? rawText.slice(m[0].length).trim() : rawText;
      const id = h.id || "sec-" + serial++;
      h.id = id;

      const entry = el("div", "toc-entry lv" + level);
      const link = document.createElement("a");
      link.href = "#" + id;
      link.appendChild(el("span", "toc-num", num));
      link.appendChild(el("span", "toc-title", title));
      link.appendChild(el("span", "toc-dots"));
      link.appendChild(el("span", "toc-page", ""));
      entry.appendChild(link);
      link.addEventListener("click", (e) => {
        e.preventDefault();
        jumpToHeading(id);
      });
      toc.appendChild(entry);
    });

    if (anchor) {
      anchor.after(toc);
      return;
    }
    // Sin un titulo de indice, el bloque se coloca despues del primer salto de
    // pagina, nunca al principio: anteponerlo tapaba la portada del documento.
    const primerSalto = page.querySelector(".page-break");
    if (primerSalto) {
      primerSalto.after(toc);
      return;
    }
    // Tampoco hay salto de pagina: se descarta antes que inventar una pagina
    // de indice donde el autor no la puso.
    toc.remove();
  }

  /* ---------- Utilidades ---------- */
  function escapeHtml(str) {
    return String(str == null ? "" : str).replace(
      /[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  // Al saltar a un titulo o a un hallazgo NO se borran las marcas de error: el
  // mapa completo del documento es justo lo que ayuda a situar el problema. Solo
  // se mueve el resaltado amarillo del elemento anterior.
  function clearFocusHighlight() {
    page.querySelectorAll(".finding-hit").forEach((el) => el.classList.remove("finding-hit"));
    page.querySelectorAll(".toc-entry").forEach((e) => e.classList.remove("outline-hit"));
  }

  function jumpToHeading(id) {
    const target = document.getElementById(id);
    if (!target) return;
    clearFocusHighlight();
    target.classList.add("finding-hit");
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    const link = page.querySelector(`a[href="#${id}"]`);
    if (link) link.closest(".toc-entry").classList.add("outline-hit");
  }

  function jumpToFinding(f) {
    if (!f) return;
    // desde "Reportes" el documento esta oculto: hay que volver antes de
    // desplazarse, o el salto no se ve
    if (Router.current() !== "correcciones") Router.go("correcciones");
    clearFocusHighlight();
    let target = null;
    if (f.excerpt && f.excerpt.length > 8) {
      const needle = f.excerpt.slice(0, 30).toLowerCase();
      target = Array.from(page.querySelectorAll("p,h1,h2,h3,h4,li,blockquote,td")).find((el) =>
        (el.textContent || "").toLowerCase().includes(needle)
      );
    }
    if (!target && f.paragraph_index != null) {
      target = page.querySelectorAll("p,h1,h2,h3,h4,li,blockquote,td")[f.paragraph_index] || null;
    }
    if (target) {
      target.classList.add("finding-hit");
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      showToast("No se pudo ubicar el fragmento en el documento.", "info");
    }
  }

  /* ---------- Estado ---------- */
  // el estado de Negrita/Cursiva/alieneacion se queda obsoleto al mover el
  // cursor: sin esto los botones mienten sobre el texto que se va a escribir
  let stateTimer = null;
  document.addEventListener("selectionchange", () => {
    if (page.hidden || document.activeElement !== page) return;
    clearTimeout(stateTimer);
    stateTimer = setTimeout(() => Commands.refresh(), 120);
  });

  function updateCounts() {
    // Los parrafos vacios del .docx llevan un espacio duro para conservar su
    // altura (ver keepEmptyParagraphs): se descartan al contar para que las
    // estadisticas no sumen un caracter por cada linea en blanco.
    const text = (Pager.textOf(page) || "")
      .split("\n")
      .map((line) => line.replace(/\u00a0/g, " ").trim())
      .filter(Boolean)
      .join("\n")
      .trim();
    const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
    statusWords.textContent = words.toLocaleString("es") + " palabras";
    statusChars.textContent = text.length.toLocaleString("es") + " caracteres";
    const pages = page.querySelectorAll(".sheet").length;
    totalPages = pages;
    if (currentPage > pages) currentPage = pages;
    updatePageLabel();
  }

  // recountar en cada pulsacion recalcula el texto de todas las hojas: en
  // documentos largos se nota, asi que se agrupa en un temporizador.
  let countsTimer = null;
  function updateCountsDebounced() {
    clearTimeout(countsTimer);
    countsTimer = setTimeout(updateCounts, 250);
  }
  page.addEventListener("input", () => {
    updateCountsDebounced();
    markDirty(true);
  });

  /* ---------- Pagina visible ---------- */
  let totalPages = 0;
  let currentPage = 1;

  // Orientacion de una hoja: el paginador deja el atributo en cada .sheet.
  function orientacionHoja(n) {
    const s = page.querySelectorAll(".sheet")[n - 1];
    if (!s) return "";
    return s.dataset.orient === "landscape" ? "Horizontal" : "Vertical";
  }

  // Paginas horizontales y verticales, en rangos ("44-46, 52").
  function resumenOrientacion() {
    const sheets = Array.from(page.querySelectorAll(".sheet"));
    const horiz = [];
    const vert = [];
    sheets.forEach((s, i) => {
      (s.dataset.orient === "landscape" ? horiz : vert).push(i + 1);
    });
    const aRangos = (paginas) => {
      const out = [];
      let ini = null;
      let prev = null;
      for (const n of paginas) {
        if (ini === null) {
          ini = n;
          prev = n;
          continue;
        }
        if (n === prev + 1) {
          prev = n;
          continue;
        }
        out.push(ini === prev ? String(ini) : ini + "-" + prev);
        ini = n;
        prev = n;
      }
      if (ini !== null) out.push(ini === prev ? String(ini) : ini + "-" + prev);
      return out;
    };
    return { horiz: aRangos(horiz), vert: aRangos(vert), total: sheets.length };
  }

  function updatePageLabel() {
    const orient = orientacionHoja(currentPage);
    statusPages.textContent =
      "Página " + currentPage + " de " + Math.max(totalPages, 1) + (orient ? " · " + orient : "");
  }
  function trackCurrentPage() {
    const sheets = page.querySelectorAll(".sheet");
    if (!sheets.length) return;
    const top = document.getElementById("canvas").getBoundingClientRect().top + 120;
    let found = 1;
    sheets.forEach((s, i) => {
      if (s.getBoundingClientRect().top <= top) found = i + 1;
    });
    if (found !== currentPage) {
      currentPage = found;
      updatePageLabel();
    }
  }
  document.getElementById("canvas").addEventListener("scroll", trackCurrentPage, { passive: true });

  /* ---------- Zoom ---------- */
  function setZoom(v) {
    zoom = Math.min(150, Math.max(50, v));
    // 'zoom' y no 'transform: scale': el transform no altera el tamano de layout,
    // con lo que al ampliar la parte inferior del documento quedaba fuera del
    // area desplazable.
    page.style.zoom = zoom / 100;
    const label = document.getElementById("zoom-label");
    if (label) label.textContent = zoom + "%";
    if (zoomRange) zoomRange.value = zoom;
  }
  document.getElementById("zoom-in").addEventListener("click", () => setZoom(zoom + 10));
  document.getElementById("zoom-out").addEventListener("click", () => setZoom(zoom - 10));
  zoomRange.addEventListener("input", () => setZoom(Number(zoomRange.value)));

  /* ---------- Toast ---------- */
  let toastTimer = null;
  function showToast(message, kind) {
    toast.textContent = message;
    toast.className = "toast " + (kind || "");
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toast.hidden = true), 3200);
  }

  /* ---------- API minima para el ribbon y las vistas ---------- */
  // el selector de estilos puede convertir <p> en <h1>, lo que invalida el
  // indice generado; se expone esta funcion para rehacerlo
  const listeners = [];
  function notifyChange() {
    listeners.forEach((fn) => {
      try {
        fn();
      } catch (e) {
        /* una vista rota no debe detener al editor */
      }
    });
  }

  const api = {
    onChange(fn) {
      if (typeof fn === "function") listeners.push(fn);
    },
    rebuildIndex() {
      // Se quitan TODAS las partes del indice, no solo la primera: si el
      // documento lo partio entre varias hojas, con querySelector se dejaba la
      // continuacion y el indice se veia duplicado tras cada reconstruccion.
      page.querySelectorAll(".doc-toc").forEach((t) => t.remove());
      page.querySelectorAll("[data-toc-skip]").forEach((h) => h.removeAttribute("data-toc-skip"));
      buildIndex();
      Pager.paginate(page, docSections);
      updateTocPages();
      updateCountsDebounced();
    },

    /* ---------- Estado para el panel de Inicio ---------- */
    state() {
      const text = (Pager.textOf(page) || "").trim();
      return {
        name: currentFile ? currentFile.name : "",
        pages: totalPages || page.querySelectorAll(".sheet").length,
        words: text ? text.split(/\s+/).filter(Boolean).length : 0,
        dirty,
        savedAt: lastSavedAt || "",
        score:
          lastSummary && lastSummary.compliance_score != null
            ? lastSummary.compliance_score
            : null,
        counts: countBy(allFindings),
        ruleCount: RULE_COUNT,
      };
    },
    pickFile() {
      fileInput.click();
    },
    // Reabrir una tesis guardada en la biblioteca.
    openFile(file) {
      if (file) loadFile(file);
    },
    openReport() {
      openReportes();
    },
    toast(message, kind) {
      showToast(message, kind);
    },
    report() {
      return reportState();
    },
    downloadReport() {
      return downloadReportDocx();
    },
    jumpToFinding(f) {
      jumpToFinding(f);
    },
    openFixModal() {
      openFixModal();
    },
    runAiReview() {
      return runAiReview();
    },
  };

  /* ---------- Guardar la sesion ---------- */
  const saveBtn = document.getElementById("save-btn");
  let dirty = false;
  let lastSavedAt = ""; // ISO de la ultima vez que se guardo en este navegador
  // total de reglas que declara el backend; se consulta una vez al arrancar
  let RULE_COUNT = 0;
  fetch("/api/rules")
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => {
      if (d && Array.isArray(d.rules)) RULE_COUNT = d.rules.length;
    })
    .catch(() => {
      /* sin conexion: el panel mostrara "?" */
    });

  function markDirty(value) {
    dirty = value;
    if (!saveBtn) return;
    saveBtn.classList.toggle("dirty", value);
    saveBtn.title = value
      ? "Hay cambios sin guardar. Pulsa para descargar el documento corregido"
      : "Descargar documento corregido (.docx)";
  }

  // Geometria de las secciones (que hojas son horizontales). Mammoth no la
  // trae, asi que se pregunta al backend leyendo el .docx original.
  async function fetchSections(file) {
    if (!file) return null;
    try {
      const data = new FormData();
      data.append("file", file, file.name);
      const res = await fetch("/api/docx-meta", { method: "POST", body: data });
      if (!res.ok) return null;
      const meta = await res.json();
      return meta.sections && meta.sections.length ? meta.sections : null;
    } catch (e) {
      return null;
    }
  }

  async function saveSession(silent) {
    if (!currentFile) return;
    // Guardar tambien en IndexedDB por si se recarga la pagina
    let buffer = null;
    try {
      buffer = await currentFile.arrayBuffer();
    } catch (e) {
      buffer = null;
    }
    const doc = {
      name: currentFile.name,
      flow: Pager.toFlowHtml(page, ".doc-toc"),
      bytes: buffer,
      // geometria de las secciones: sin esto, al recargar la pagina se
      // perdia que hojas son horizontales y todas se pintaban verticales
      sections: docSections,
      // fuente y tamano por defecto del documento: si no se guardan, al
      // restaurar la sesion el #page se queda con la fuente del CSS (Arial)
      // en vez de la real del .docx (ej: Times New Roman 12)
      docFont: page.style.fontFamily || "",
      docSize: page.style.fontSize || "",
      // version del conversor que produjo `flow`: permite saber si la sesion
      // guardada se puede reutilizar o hay que reconvertir el .docx
      flowVersion: FLOW_VERSION,
      // ultimo informe: se conserva para poder leerlo al reiniciar sin gastar
      // otra verificacion (ni tokens de IA). Se reemplaza al verificar de nuevo.
      report: reportSnapshot(),
      savedAt: new Date().toISOString(),
    };
    try {
      await SessionStore.save(doc);
      lastSavedAt = doc.savedAt;
      markDirty(false);
    } catch (e) {
      /* error al guardar en IndexedDB no bloquea la descarga */
    }
  }

  // Recolecta los IDs de las reglas que se han corregido
  function getCorrectedRuleIds() {
    var ids = new Set();
    allFindings.forEach(function (f, i) {
      if (resolvedIdx.has(i) && f.rule_id) ids.add(f.rule_id);
    });
    return Array.from(ids);
  }

  async function downloadCorrectedDocx() {
    if (!currentFile) {
      showToast("Abre un documento primero", "error");
      return;
    }
    saveBtn.disabled = true;
    statusMsg.textContent = "Generando documento corregido...";
    var ruleIds = getCorrectedRuleIds();
    var formData = new FormData();
    formData.append("file", currentFile, currentFile.name);
    formData.append("rules", ruleIds.join(","));
    try {
      var res = await fetch("/api/export", { method: "POST", body: formData });
      if (!res.ok) {
        var err = await res.json().catch(function () { return { detail: "Error" }; });
        throw new Error(err.detail || "Error " + res.status);
      }
      var blob = await res.blob();
      // El nombre viene en el Content-Disposition; si no se puede leer,
      // se construye a partir del nombre original
      var disposition = res.headers.get("Content-Disposition") || "";
      var fileName = "";
      var match = disposition.match(/filename="?([^"]+)"?/);
      if (match) {
        fileName = match[1];
      } else {
        var base = currentFile.name.replace(/\.docx$/i, "");
        fileName = base + "-correcciones.docx";
      }
      // Descargar el archivo: el navegador abre el dialogo "Guardar como..."
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
      markDirty(false);
      saveSession(true);
      statusMsg.textContent = "";
      showToast("Documento corregido descargado: " + fileName, "ok");
    } catch (err) {
      statusMsg.textContent = "";
      showToast("No se pudo descargar: " + err.message, "error");
    } finally {
      saveBtn.disabled = false;
    }
  }

  // Descarga el informe APA (todos los errores, advertencias y observaciones)
  // como un documento Word independiente.
  async function downloadReportDocx() {
    if (!currentFile) {
      showToast("Abre un documento primero", "error");
      return;
    }
    statusMsg.textContent = "Generando informe APA en Word...";
    var formData = new FormData();
    formData.append("file", currentFile, currentFile.name);
    try {
      var res = await fetch("/api/report/docx", { method: "POST", body: formData });
      if (!res.ok) {
        var err = await res.json().catch(function () { return { detail: "Error" }; });
        throw new Error(err.detail || "Error " + res.status);
      }
      var blob = await res.blob();
      var disposition = res.headers.get("Content-Disposition") || "";
      var fileName = "";
      var match = disposition.match(/filename="?([^"]+)"?/);
      if (match) {
        fileName = match[1];
      } else {
        var base = currentFile.name.replace(/\.docx$/i, "");
        fileName = "Informe-APA-" + base + ".docx";
      }
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
      statusMsg.textContent = "";
      showToast("Informe APA descargado: " + fileName, "ok");
    } catch (err) {
      statusMsg.textContent = "";
      showToast("No se pudo generar el informe: " + err.message, "error");
    }
  }

  // Restaura el documento de la sesion anterior (si existe) al abrir la app.
  async function restoreSession() {
    let doc = null;
    try {
      doc = await SessionStore.load();
    } catch (e) {
      return;
    }
    if (!doc || !doc.flow) return;
    try {
      if (doc.bytes) {
        currentFile = new File([new Uint8Array(doc.bytes)], doc.name, {
          type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        });
      } else {
        currentFile = new File([new Blob([doc.flow])], doc.name);
      }
      docName.textContent = doc.name;
      analyzeBtn.disabled = false;
      saveBtn.disabled = false;
      // Si la sesion viene de un conversor anterior se rehace el flujo aqui:
      // si no, se seguiria viendo el documento tal como estaba antes del arreglo.
      page.innerHTML = await flowForSession(doc);
      // La seccion de cada bloque es geometria calculada: si una sesion
      // anterior la guardo mal, el error se arrastraba en cada recarga. Se
      // borra para que el paginador la vuelva a deducir del texto.
      page.querySelectorAll("[data-section]").forEach((el) => el.removeAttribute("data-section"));
      // Las sesiones guardadas antes de este arreglo ya traerian el indice
      // generado dentro del flujo (a veces partido en varios bloques). Se quitan
      // TODOS antes de reconstruirlo, o el indice se veria repetido.
      page.querySelectorAll(".doc-toc").forEach((t) => t.remove());
      buildIndex();
      // La geometria de las secciones no viaja dentro del flujo HTML: si no se
      // recupera, el paginador usa la hoja vertical por defecto y las paginas
      // horizontales del .docx salen comprimidas. Primero se usa la que venia
      // guardada y, si no hay (sesiones viejas), se vuelve a pedir al backend
      // con el .docx original.
      docSections = doc.sections || null;
      if (!docSections && currentFile) {
        docSections = await fetchSections(currentFile);
      }
      // Restaurar la fuente y tamano del documento: si no se hace, al
      // recargar la pagina el #page se queda con la fuente del CSS (Arial)
      // en vez de la real del .docx (ej: Times New Roman 12). Solo se pisa si
      // la sesion los trae: si el flujo se acaba de reconvertir, enrichHtml()
      // ya dejo puesta la fuente correcta y no hay que borrarla.
      if (doc.docFont) page.style.fontFamily = doc.docFont;
      if (doc.docSize) page.style.fontSize = doc.docSize;
      // Si la sesion no trae fuente y hay un .docx original, se la pide al
      // backend para no perderla (sesiones guardadas antes de este arreglo).
      if ((!doc.docFont || !doc.docSize) && currentFile) {
        try {
          const data = new FormData();
          data.append("file", currentFile, currentFile.name);
          const res = await fetch("/api/docx-meta", { method: "POST", body: data });
          if (res.ok) {
            const meta = await res.json();
            const defs = meta.defaults || {};
            if (defs.font && !doc.docFont) page.style.fontFamily = quoteFont(defs.font);
            if (defs.size_pt && !doc.docSize) page.style.fontSize = defs.size_pt + "pt";
          }
        } catch (e) {
          /* sin metadatos: se usa la fuente del CSS */
        }
      }
      Pager.paginate(page, docSections);
      updateTocPages();
      page.contentEditable = "true";
      emptyState.hidden = true;
      page.hidden = false;
      resetReport();
      // El informe de la ultima verificacion se conserva hasta que se vuelva a
      // verificar: asi se puede leer al reiniciar sin gastar otra verificacion.
      restoreReportState(doc.report, true);
      updateCounts();
      markDirty(false);
      lastSavedAt = doc.savedAt || "";
      History.reset();
      const when = new Date(doc.savedAt).toLocaleString("es", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
      if (flowRegenerated) {
        // Se rehizo el flujo desde el .docx: se avisa para que no sorprenda que
        // el documento no tenga las ediciones hechas en el visor antes del cambio.
        flowRegenerated = false;
        showToast(
          "Documento reconvertido con el visor actualizado (" + doc.name + "). " +
            "Las ediciones hechas solo en pantalla no se conservan.",
          "info"
        );
      } else if (flowStale) {
        // Sin el .docx original no hay de donde rehacer la conversion: se dice
        // que hay que volver a abrirlo, o la portada seguira viendose igual.
        flowStale = false;
        showToast(
          "Este documento se guardó con una versión anterior del visor y no se " +
            "puede rehacer sin el .docx original. Vuelve a abrir el archivo para " +
            "ver la portada corregida.",
          "info"
        );
      } else {
        showToast("Sesión restaurada: " + doc.name + " (" + when + ").", "info");
      }
    } catch (e) {
      /* si el guardado esta corrupto, se ignora y se empieza limpio */
    }
  }

  saveBtn.addEventListener("click", downloadCorrectedDocx);

  /* ---------- Plegar la cinta de opciones ---------- */
  const ribbonNav = document.getElementById("ribbon");
  const ribbonCollapse = document.getElementById("ribbon-collapse");
  function setRibbonCollapsed(collapsed) {
    ribbonNav.classList.toggle("is-collapsed", collapsed);
    ribbonCollapse.querySelector(".chev-up").hidden = collapsed;
    ribbonCollapse.querySelector(".chev-down").hidden = !collapsed;
    ribbonCollapse.title = collapsed
      ? "Mostrar la barra de herramientas"
      : "Ocultar la barra de herramientas";
    ribbonCollapse.setAttribute(
      "aria-label",
      ribbonCollapse.title
    );
    try {
      localStorage.setItem("apa.ribbon.collapsed", collapsed ? "1" : "0");
    } catch (e) {
      /* modo privado: solo afecta a esta sesion */
    }
    // el documento recupera el alto al plegarse la cinta
    trackCurrentPage();
  }
  ribbonCollapse.addEventListener("click", () =>
    setRibbonCollapsed(!ribbonNav.classList.contains("is-collapsed"))
  );

  /* ---------- Orientacion de las paginas ---------- */
  const orientModal = document.getElementById("orient-modal");
  const orientBody = document.getElementById("orient-body");
  const orientSub = document.getElementById("orient-modal-sub");
  const orientCount = document.getElementById("orient-count");

  function closeOrientModal() {
    if (orientModal) orientModal.hidden = true;
  }

  function openOrientModal() {
    if (!orientModal) return;
    const r = resumenOrientacion();
    if (!r.total) {
      showToast("Abre un documento primero", "error");
      return;
    }
    orientSub.textContent =
      "El documento tiene " + r.total + " páginas. Estas son las horizontales y las verticales.";
    const bloque = (titulo, color, paginas, total) => `
      <div class="orient-block">
        <div class="orient-head">
          <span class="orient-dot ${color}"></span>
          <b>${titulo}</b>
          <span class="orient-count">${total} de ${r.total} páginas</span>
        </div>
        <p class="orient-pages">${paginas.length ? paginas.join(", ") : "â€”"}</p>
      </div>`;
    orientBody.innerHTML =
      bloque("Páginas horizontales (landscape)", "h", r.horiz, r.horiz.length ? cuenta(r.horiz) : 0) +
      bloque("Páginas verticales (portrait)", "v", r.vert, r.vert.length ? cuenta(r.vert) : 0);
    orientCount.textContent = "";
    orientModal.hidden = false;
  }

  // numero de paginas de un listado de rangos ("44-46, 52" -> 5)
  function cuenta(rangos) {
    let n = 0;
    for (const rg of rangos) {
      const partes = rg.split("-");
      n += partes.length === 2 ? Number(partes[1]) - Number(partes[0]) + 1 : 1;
    }
    return n;
  }

  if (orientModal) {
    orientModal.addEventListener("click", (e) => {
      if (e.target === orientModal) closeOrientModal();
    });
    const oc = document.getElementById("orient-modal-close");
    const oCancel = document.getElementById("orient-cancel");
    if (oc) oc.addEventListener("click", closeOrientModal);
    if (oCancel) oCancel.addEventListener("click", closeOrientModal);
  }

  /* ---------- Corregir documento ---------- */
  const fixModal = document.getElementById("fix-modal");
  const fixList = document.getElementById("fix-list");
  const fixSub = document.getElementById("fix-modal-sub");
  const fixCount = document.getElementById("fix-modal-count");
  const fixApply = document.getElementById("fix-apply");
  const fixCancel = document.getElementById("fix-cancel");
  const fixUndo = document.getElementById("fix-undo");
  const fixClose = document.getElementById("fix-modal-close");
  let fixSnapshot = null;

  function closeFixModal() {
    fixModal.hidden = true;
    fixSnapshot = null;
    fixUndo.hidden = true;
  }

  function renderFixList(items) {
    const ctx = { sections: docSections || [] };
    const rows = Fixer.preview(items, ctx).filter((r) => r.count > 0);
    if (!rows.length) {
      fixList.innerHTML =
        '<p class="modal-note">No hay correcciones automáticas disponibles: primero verifica el documento.</p>';
      fixApply.disabled = true;
      fixCount.textContent = "";
      return rows;
    }
    fixList.innerHTML = rows
      .map(
        (r) => `<label class="fix-item">
        <input type="checkbox" value="${r.id}" checked>
        <span class="fix-text">
          <span class="fix-label">${r.label}</span>
          <span class="fix-detail">${r.detail}</span>
        </span>
        <span class="fix-count">${r.count}</span>
      </label>`
      )
      .join("");
    fixApply.disabled = false;
    fixCount.textContent = `${rows.length} tipo(s) seleccionado(s)`;
    return rows;
  }

  function openFixModal() {
    if (page.hidden) {
      showToast("Abre un documento primero", "error");
      return;
    }
    const items = Fixer.available(lastFindings);
    if (!items.length) {
      showToast("Verifica el documento primero para detectar los errores", "error");
      return;
    }
    fixSub.textContent =
      (docName.textContent || "Documento") +
      " - revisa lo que se va a corregir antes de aplicar.";
    fixUndo.hidden = true;
    fixModal.hidden = false;
    renderFixList(items);
  }

  function applyFixes() {
    const chosen = Array.from(fixList.querySelectorAll("input:checked")).map(
      (i) => i.value
    );
    if (!chosen.length) {
      showToast("Selecciona al menos una corrección", "error");
      return;
    }
    const items = Fixer.CORRECTIONS.filter((c) => chosen.includes(c.id));
    fixSnapshot = Pager.toFlowHtml(page);
    const res = Fixer.applySelected(items, { sections: docSections || [] });
    if (!res.total) {
      showToast("No había nada que corregir", "error");
      closeFixModal();
      return;
    }
    repaginate();
    markDirty(true);
    fixModal.hidden = true;
    showToast("Se aplicaron " + res.total + " corrección(es) correctamente.", "ok");
    // el corrector del panel SI actsua sobre todo el documento: aqui se
    // resuelven todos los avisos de las reglas aplicadas
    const aplicadas = reglasAplicadas(res);
    if (aplicadas.size) {
      allFindings.forEach((f, i) => {
        if (aplicadas.has(f.rule_id)) resolvedIdx.add(i);
      });
    }
    refreshMarksAfterFix(res);
  }

  function reglasAplicadas(res) {
    const out = new Set();
    ((res && res.done) || []).forEach((d) => {
      (d.rules || []).forEach((r) => out.add(r));
    });
    return out;
  }

  // `markFindings` son los avisos de la marca pulsada. Si no se pasan (o van
  // vacios) se resuelven todos los avisos de las reglas aplicadas.
  function refreshMarksAfterFix(res, markFindings) {
    if (!res || !res.total) {
      renderReport({ summary: lastSummary, partial: true });
      return;
    }
    const aplicadas = reglasAplicadas(res);
    if (aplicadas.size) {
      if (markFindings && markFindings.length) {
        // solo se retiran los avisos de ESA marca: el resto sigue disponible
        markFindings.forEach((f) => {
          if (!aplicadas.has(f.rule_id)) return;
          const i = allFindings.indexOf(f);
          if (i !== -1) resolvedIdx.add(i);
        });
      } else {
        allFindings.forEach((f, i) => {
          if (aplicadas.has(f.rule_id)) resolvedIdx.add(i);
        });
      }
    }
    const quedan = allFindings.length - resolvedIdx.size;
    renderReport({ summary: lastSummary, partial: true });
    // los avisos resueltos tambien se guardan: al reiniciar siguen corregidos
    persistReport();
    if (quedan) {
      setTimeout(function () {
        showToast("Quedan " + quedan + " aviso(s) por revisar manualmente.", "info");
      }, 1800);
    }
  }

  function undoFixes() {
    if (!fixSnapshot) return;
    page.innerHTML = fixSnapshot;
    repaginate();
    fixSnapshot = null;
    fixUndo.hidden = true;
    closeFixModal();
    showToast("Correcciones deshechas", "ok");
    // al deshacer vuelven a aparecer los avisos corregidos
    resolvedIdx.clear();
    renderReport({ summary: lastSummary, partial: true });
    persistReport();
  }

  fixApply.addEventListener("click", applyFixes);
  fixUndo.addEventListener("click", undoFixes);
  fixCancel.addEventListener("click", closeFixModal);
  fixClose.addEventListener("click", closeFixModal);
  fixModal.addEventListener("click", (e) => {
    if (e.target === fixModal) closeFixModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !fixModal.hidden) closeFixModal();
    if (e.key === "Escape" && orientModal && !orientModal.hidden) closeOrientModal();
  });

  // el marcado del documento usa estos enlaces con la app
  Marker.setHooks({
    sections: () => docSections || [],
    afterFix: (res, markFindings) => {
      repaginate();
      markDirty(true);
      showToast(
        res && res.total
          ? "Corregido (" + res.total + ")"
          : "No se aplicó ningún cambio aquí",
        res && res.total ? "ok" : "info"
      );
      refreshMarksAfterFix(res, markFindings);
    },
    openReport: () => openPane(),
  });

  /* ---------- Init ---------- */
  page.hidden = true;
  resetReport();
  setZoom(100);
  markDirty(false);

  /* ---------- Deshacer / rehacer ---------- */
  // El historial propio sustituye al del navegador: este solo guardaba lo
  // tecleado y se borraba al repaginar, marcar avisos o aplicar correcciones.
  History.init({
    // tras restaurar hay que rehacer la paginacion, porque al deshacer un
    // "Reorganizar paginas" vuelve el documento a como estaba sin paginar
    afterRestore() {
      Pager.paginate(page, docSections);
      updateTocPages();
      updateCounts();
      markDirty(true);
    },
  });
  History.onChange(() => {
    Commands.refresh();
    History.refresh();
  });

  // aviso al cerrar con cambios sin guardar
  window.addEventListener("beforeunload", (e) => {
    if (!dirty) return;
    e.preventDefault();
    e.returnValue = "";
  });

  // el ribbon no conoce el editor: se le inyecta el callback del indice
  Ribbon.setHooks({ onStyleChange: () => api.rebuildIndex() });

  restoreSession();

  try {
    if (localStorage.getItem("apa.ribbon.collapsed") === "1") setRibbonCollapsed(true);
  } catch (e) {
    /* sin persistencia */
  }

  return api;
})();

export { App };







