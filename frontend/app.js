/* Logica principal: carga de .docx, edicion y analisis APA. */
(function () {
  "use strict";
  const SEVERITY_ICON = { error: "!", warning: "!", info: "i" };

  const page = document.getElementById("page");
  const emptyState = document.getElementById("empty-state");
  const fileInput = document.getElementById("file");
  const docName = document.getElementById("doc-name");
  const analyzeBtn = document.getElementById("analyze-btn");
  const openBtn = document.getElementById("open-btn");
  const emptyOpen = document.getElementById("empty-open");
  const reportPane = document.getElementById("report-pane");
  const paneClose = document.getElementById("pane-close");
  const scoreNum = document.getElementById("score-num");
  const paneCards = document.getElementById("pane-cards");
  const paneFilters = document.getElementById("pane-filters");
  const findingsEl = document.getElementById("findings");
  const statusMsg = document.getElementById("status-msg");
  const statusWords = document.getElementById("status-words");
  const statusChars = document.getElementById("status-chars");
  const statusPages = document.getElementById("status-pages");
  const zoomRange = document.getElementById("zoom-range");
  const toast = document.getElementById("toast");

  let currentFile = null;
  let currentFindings = [];
  let allFindings = []; // copia integra del informe, sin filtrar
  let activeFilter = "all";
  let zoom = 100;
  let reading = false;
  let docSections = null; // geometria de cada seccion del docx (vertical/horizontal)

  /* ---------- Ribbon ---------- */
  Ribbon.render(document.getElementById("ribbon-tabs"), document.getElementById("ribbon-panels"), {
    analyze: runAnalysis,
    "ai-review": runAiReview,
    "fix-doc": openFixModal,
    "toggle-pane": () => (reportPane.hidden ? openPane() : (reportPane.hidden = true)),
    "clear-marks": clearMarks,
    "page-break": () => {
      insertHtml('<div class="page-break"></div>');
      repaginate();
    },
    table: insertTable,
    image: pickImage,
    link: insertLink,
    reading: toggleReading,
    "apa-defaults": applyApaDefaults,
    repaginate: repaginate,
    "toggle-ruler": () => document.body.classList.toggle("show-ruler"),
  });

  /* ---------- Archivo ---------- */
  openBtn.addEventListener("click", () => fileInput.click());
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

      // cola de metadatos por clave: permite repetir la misma linea sin confundirse
      const queues = new Map();
      (meta.paragraphs || []).forEach((p) => {
        const k = p.key;
        if (!queues.has(k)) queues.set(k, []);
        queues.get(k).push(p);
      });

      const tmp = document.createElement("div");
      tmp.innerHTML = html;
      const blocks = Array.from(tmp.querySelectorAll("p,h1,h2,h3,h4,li"));
      blocks.forEach((el, i) => {
        const queue = queues.get(textKey(el.textContent));
        const info = queue && queue.length ? queue.shift() : null;
        if (!info) return;

        if (info.align && info.align !== "left") el.style.textAlign = info.align;
        if (info.ls) el.style.lineHeight = String(info.ls);
        if (info.sb != null) el.style.marginTop = info.sb + "pt";
        if (info.sa != null) el.style.marginBottom = info.sa + "pt";
        if (info.size) el.style.fontSize = info.size + "pt";

        // salto de pagina explicito antes de este parrafo
        if (info.pb && i > 0) {
          const br = document.createElement("div");
          br.className = "page-break";
          br.setAttribute("data-src", "word");
          el.parentNode.insertBefore(br, el);
        }
      });
      return tmp.innerHTML;
    } catch (e) {
      return html;
    }
  }

  function quoteFont(name) {
    const f = String(name || "").trim();
    if (!f) return "";
    return /[a-zA-Z]/.test(f) && !/^["']/.test(f) && !/,/.test(f) ? "'" + f.replace(/'/g, "") + "'" : f;
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
    markDirty(false);
    

    const reader = new FileReader();
    reader.onload = () => {
      mammoth
        .convertToHtml({ arrayBuffer: reader.result })
        .then((result) => enrichHtml(result.value || "<p></p>"))
        .then((html) => {
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
          showToast("Documento cargado. Edita y pulsa 'Verificar APA'.", "ok");
        })
        .catch((err) => showToast("No se pudo abrir el documento: " + err.message, "error"));
    };
    reader.readAsArrayBuffer(file);
  }

  function toggleReading() {
    reading = !reading;
    page.contentEditable = reading ? "false" : "true";
    document.body.classList.toggle("reading", reading);
    showToast(reading ? "Modo lectura activado" : "Edicion activada", "ok");
  }

  function repaginate() {
    Pager.paginate(page, docSections);
    updateTocPages();
    updateCounts();
    showToast("Paginas reorganizadas (se reinicia el historial de Ctrl+Z).", "ok");
  }

  /* ---------- Revision asistida por IA ---------- */
  let aiFindings = [];
  let lastFindings = [];
  let lastSummary = null;

  async function runAiReview() {
    if (!currentFile) {
      showToast("Primero abre un documento .docx", "error");
      return;
    }
    statusMsg.textContent = "Consultando a la IA...";
    const data = new FormData();
    data.append("file", currentFile, currentFile.name);
    try {
      const res = await fetch("/api/ai/classify", { method: "POST", body: data });
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || "Error " + res.status);
      if (!payload.ai_enabled) {
        showToast("La revision con IA no esta habilitada (falta AI_ENABLED o la clave).", "error");
        statusMsg.textContent = "";
        return;
      }
      aiFindings = payload.findings || [];
      if (!lastFindings.length) runAnalysisQuiet();
      renderReport({ summary: lastSummary, findings: lastFindings.concat(aiFindings) });
      openPane();
      (payload.notes || []).forEach((n) => showToast(n, "info"));
      statusMsg.textContent = "";
      showToast(
        aiFindings.length
          ? "IA: " + aiFindings.length + " sugerencia(s) de " + (payload.model || "")
          : "IA: sin sugerencias",
        aiFindings.length ? "ok" : "info"
      );
    } catch (err) {
      statusMsg.textContent = "";
      showToast("La revision con IA fallo: " + err.message, "error");
    }
  }


  /* ---------- Indice: numeros de pagina reales tras la paginacion ---------- */
  function updateTocPages() {
    const toc = page.querySelector(".doc-toc");
    if (!toc) return;
    const entries = Array.from(toc.querySelectorAll(".toc-entry"));
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
    const url = window.prompt("Direccion del enlace (https://...):");
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
        el.style.lineHeight = "2";
        el.style.textAlign = "left";
        if (el.tagName === "P") {
          el.style.textIndent = "1.27cm";
          el.style.margin = "0";
        }
      });
    });
    Pager.paginate(page, docSections);
    updateCounts();
    showToast("Formato base APA aplicado (2.0, Times New Roman 12, sangria). Ctrl+Z no restaura este paso.", "ok");
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
      openPane();
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


  function openPane() {
    reportPane.hidden = false;
  }
  paneClose.addEventListener("click", () => (reportPane.hidden = true));

  function resetReport() {
    currentFindings = [];
    lastFindings = [];
    allFindings = [];
    lastSummary = null;
    aiFindings = [];
    activeFilter = "all";
    scoreNum.textContent = "--";
    paneCards.innerHTML = "";
    paneFilters.innerHTML = "";
    findingsEl.innerHTML = '<p class="empty-pane">Aun no se ha verificado el documento.</p>';
  }

  function renderReport(report) {
    const s = report.summary || {};
    const by = s.by_severity || {};
    lastSummary = s;
    // copia integra: no se filtra, para poder deshacer y volver a marcar todo
    if (!report.partial) allFindings = report.findings || [];
    lastFindings = report.findings || [];
    scoreNum.textContent = s.compliance_score != null ? s.compliance_score : "--";

    currentFindings = report.findings || [];
    const counts = countBy(currentFindings);
    paneCards.innerHTML = [
      card(counts.error, "Errores", "error"),
      card(counts.warning, "Avisos", "warning"),
      card(counts.info, "Observ.", "info"),
      card(counts.all, "Total"),
    ].join("");

    activeFilter = "all";
    renderFilters();
    renderFindings();
    markInDocument();
  }

  /* ---------- Senalar los problemas dentro del texto ---------- */
  let marksVisible = true;

  function markInDocument() {
    if (!marksVisible) return;
    if (page.hidden || !currentFindings.length) {
      Marker.clear();
      return;
    }
    const res = Marker.apply(currentFindings);
    if (res.marks || res.blocks) {
      showToast(
        (res.marks ? res.marks + " texto(s) marcados" : "") +
          (res.blocks ? " y " + res.blocks + " parrafo(s)" : "") +
          " en el documento",
        "info"
      );
    }
    if (res.unmatched) {
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

  function card(value, label, cls) {
    return `<div class="pane-card ${cls || ""}"><div class="pc-num">${value}</div><div class="pc-label">${label}</div></div>`;
  }

  function renderFilters() {
    const counts = { all: currentFindings.length, error: 0, warning: 0, info: 0 };
    currentFindings.forEach((f) => (counts[f.severity] = (counts[f.severity] || 0) + 1));
    const items = [["all", "Todos"], ["error", "Errores"], ["warning", "Avisos"], ["info", "Observ."]];
    paneFilters.innerHTML = items
      .map(
        ([k, label]) =>
          `<button data-filter="${k}" class="${activeFilter === k ? "active" : ""}">${label} <b>${counts[k] || 0}</b></button>`
      )
      .join("");
    paneFilters.querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () => {
        activeFilter = b.dataset.filter;
        renderFilters();
        renderFindings();
      })
    );
  }

  function renderFindings() {
    const list = currentFindings.filter((f) => activeFilter === "all" || f.severity === activeFilter);
    if (!list.length) {
      findingsEl.innerHTML = '<p class="empty-pane">Sin hallazgos en esta categoria.</p>';
      return;
    }
    findingsEl.innerHTML = list
      .map((f) => {
        const extra = f.extra || {};
        const isAi = String(f.rule_id || "").startsWith("AI-");
        const badge = isAi
          ? `<span class="ai-badge" title="Sugerencia de la IA: no se aplica automaticamente">IA</span>`
          : "";
        const conf =
          isAi && extra.ai_confidence != null
            ? `<span class="ai-conf">confianza ${Math.round(extra.ai_confidence * 100)}%</span>`
            : "";
        const missing =
          isAi && extra.ai_missing && extra.ai_missing.length
            ? `<p class="finding-missing">Falta: ${escapeHtml(extra.ai_missing.join(" · "))}</p>`
            : "";
        return `<article class="finding ${f.severity}${isAi ? " ai" : ""}" data-i="${currentFindings.indexOf(f)}">
          <div class="finding-head">
            <span class="dot">${SEVERITY_ICON[f.severity] || ""}</span>
            <span class="finding-cat">${escapeHtml(f.category || "")}</span>
            ${badge}${conf}
            <span class="finding-rule">${escapeHtml(f.rule_id || "")}</span>
          </div>
          <p class="finding-msg">${escapeHtml(f.message || "")}</p>
          ${missing}
          ${f.excerpt ? `<p class="finding-excerpt">"${escapeHtml(f.excerpt)}"</p>` : ""}
          ${f.suggestion ? `<p class="finding-sug">Sugerencia: ${escapeHtml(f.suggestion)}</p>` : ""}
          <p class="finding-loc">${escapeHtml(f.location || "")}</p>
        </article>`;
      })
      .join("");
    findingsEl.querySelectorAll(".finding").forEach((el) =>
      el.addEventListener("click", () => jumpToFinding(currentFindings[Number(el.dataset.i)]))
    );
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

    const tocLike = (t) => /^(índice|indice|contenido|contenidos|tabla de contenido|sumario)$/i.test(t.trim().replace(/[.:]$/, ""));
    const heading = headings.find((h) => tocLike(h.textContent || ""));
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
    } else {
      page.prepend(toc);
    }
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

  function jumpToHeading(id) {
    clearMarks();
    const target = document.getElementById(id);
    if (!target) return;
    target.classList.add("finding-hit");
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    page.querySelectorAll(".toc-entry")
      .forEach((e) => e.classList.remove("outline-hit"));
    const link = page.querySelector(`a[href="#${id}"]`);
    if (link) link.closest(".toc-entry").classList.add("outline-hit");
  }

  function jumpToFinding(f) {
    if (!f) return;
    clearMarks();
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
    const text = (Pager.textOf(page) || "").trim();
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
  function updatePageLabel() {
    statusPages.textContent = "Pagina " + currentPage + " de " + Math.max(totalPages, 1);
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

  /* ---------- API minima para el ribbon ---------- */
  // el selector de estilos puede convertir <p> en <h1>, lo que invalida el
  // indice generado; se expone esta funcion para rehacerlo
  window.App = {
    rebuildIndex() {
      const toc = page.querySelector(".doc-toc");
      if (toc) toc.remove();
      page.querySelectorAll("[data-toc-skip]").forEach((h) => h.removeAttribute("data-toc-skip"));
      buildIndex();
      Pager.paginate(page, docSections);
      updateTocPages();
      updateCountsDebounced();
    },
  };

  /* ---------- Guardar la sesion ---------- */
  const saveBtn = document.getElementById("save-btn");
  let dirty = false;

  function markDirty(value) {
    dirty = value;
    if (!saveBtn) return;
    saveBtn.classList.toggle("dirty", value);
    saveBtn.title = value
      ? "Hay cambios sin guardar. Pulsa para guardarlos en este navegador"
      : "Guardar los cambios en este navegador";
  }

  async function saveSession(silent) {
    if (!currentFile) return;
    let buffer = null;
    try {
      buffer = await currentFile.arrayBuffer();
    } catch (e) {
      buffer = null;
    }
    const doc = {
      name: currentFile.name,
      flow: Pager.toFlowHtml(page),
      bytes: buffer,
      savedAt: new Date().toISOString(),
    };
    try {
      await SessionStore.save(doc);
      markDirty(false);
      if (!silent) {
        const when = new Date(doc.savedAt).toLocaleTimeString("es", {
          hour: "2-digit",
          minute: "2-digit",
        });
        showToast("Cambios guardados en este navegador (" + when + ").", "ok");
      }
    } catch (e) {
      showToast("No se pudo guardar: " + e.message, "error");
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
      page.innerHTML = doc.flow;
      buildIndex();
      Pager.paginate(page, docSections);
      updateTocPages();
      page.contentEditable = "true";
      emptyState.hidden = true;
      page.hidden = false;
      resetReport();
      updateCounts();
      markDirty(false);
      const when = new Date(doc.savedAt).toLocaleString("es", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
      showToast("Sesion restaurada: " + doc.name + " (" + when + ").", "info");
    } catch (e) {
      /* si el guardado esta corrupto, se ignora y se empieza limpio */
    }
  }

  saveBtn.addEventListener("click", () => saveSession(false));

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
        '<p class="modal-note">No hay correcciones automaticas disponibles: primero verifica el documento.</p>';
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
      showToast("Selecciona al menos una correccion", "error");
      return;
    }
    const items = Fixer.CORRECTIONS.filter((c) => chosen.includes(c.id));
    fixSnapshot = Pager.toFlowHtml(page);
    const res = Fixer.applySelected(items, { sections: docSections || [] });
    if (!res.total) {
      showToast("No habia nada que corregir", "error");
      closeFixModal();
      return;
    }
    repaginate();
    markDirty(true);
    fixApply.disabled = true;
    fixCount.textContent = res.total + " correccion(es) aplicada(s)";
    fixUndo.hidden = false;
    showToast("Se aplicaron " + res.total + " correcciones", "ok");
    // tras corregir, se retiran las marcas de las reglas ya resueltas:
    // lo que queda marcado es justo lo que hay que revisar a mano
    refreshMarksAfterFix(res);
  }

  const resolvedRules = new Set();

  function refreshMarksAfterFix(res) {
    (res && res.done ? res.done : []).forEach((d) => {
      (d.rules || []).forEach((r) => resolvedRules.add(r));
    });
    currentFindings = allFindings.filter((f) => !resolvedRules.has(f.rule_id));
    const quedan = currentFindings.length;
    renderReport({ summary: lastSummary, findings: currentFindings, partial: true });
    showToast(
      quedan
        ? "Quedan " + quedan + " aviso(s) marcados en el texto"
        : "No queda ningun aviso por revisar",
      quedan ? "info" : "ok"
    );
  }

  function undoFixes() {
    if (!fixSnapshot) return;
    page.innerHTML = fixSnapshot;
    repaginate();
    fixSnapshot = null;
    fixUndo.hidden = true;
    closeFixModal();
    showToast("Correcciones deshechas", "ok");
    // al deshacer vuelven a aparecer los avisos de las reglas corregidas
    resolvedRules.clear();
    currentFindings = allFindings;
    renderReport({ summary: lastSummary, findings: currentFindings, partial: true });
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
  });

  // el marcado del documento usa estos enlaces con la app
  Marker.setHooks({
    sections: () => docSections || [],
    afterFix: (res) => {
      repaginate();
      markDirty(true);
      showToast(
        res && res.total
          ? "Corregido (" + res.total + ")"
          : "No habia nada que corregir",
        res && res.total ? "ok" : "info"
      );
      refreshMarksAfterFix(res);
    },
    openReport: () => {
      if (reportPane.hidden) openPane();
    },
  });

  /* ---------- Init ---------- */
  page.hidden = true;
  resetReport();
  setZoom(100);
  markDirty(false);

  // aviso al cerrar con cambios sin guardar
  window.addEventListener("beforeunload", (e) => {
    if (!dirty) return;
    e.preventDefault();
    e.returnValue = "";
  });

  restoreSession();

  try {
    if (localStorage.getItem("apa.ribbon.collapsed") === "1") setRibbonCollapsed(true);
  } catch (e) {
    /* sin persistencia */
  }
})();







