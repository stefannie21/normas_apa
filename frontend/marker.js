/* Marca dentro del documento donde esta cada problema.

Divide el trabajo en dos: lo que el corrector puede arreglar solo y lo que
solo se puede senalar para que la persona decida. Aqui solo se senala:
este modulo NUNCA modifica el texto del usuario.
*/
(function () {
  "use strict";

  const SEV = { error: "apa-mark-error", warning: "apa-mark-warning", info: "apa-mark-info" };
  const SEL =
    "p,h1,h2,h3,h4,h5,h6,li,blockquote,td,th";
  const registry = new Map(); // data-fid -> hallazgo completo

  function root() {
    return document.getElementById("page");
  }

  function blocks() {
    const p = root();
    if (!p) return [];
    return Array.from(p.querySelectorAll(SEL)).filter(
      (el) => !el.closest(".doc-toc") && !el.classList.contains("sheet-num")
    );
  }

  function clear() {
    const p = root();
    if (!p) return;
    // se desenvuelve el texto marked sin perderlo
    p.querySelectorAll(".apa-mark").forEach((m) => {
      const parent = m.parentNode;
      while (m.firstChild) parent.insertBefore(m.firstChild, m);
      parent.removeChild(m);
      parent.normalize();
    });
    p.querySelectorAll(".apa-flagged").forEach((el) =>
      el.classList.remove("apa-flagged")
    );
    close();
  }

  function locate(f) {
    const all = blocks();
    if (f.excerpt && f.excerpt.length > 8) {
      const needle = f.excerpt.slice(0, 30).toLowerCase();
      const hit = all.find((el) =>
        (el.textContent || "").toLowerCase().includes(needle)
      );
      if (hit) return hit;
    }
    if (f.paragraph_index != null && all[f.paragraph_index]) return all[f.paragraph_index];
    return null;
  }

  // Si el mismo texto ya esta marcado, se agrupan las reglas en esa misma
// marca en vez de duplicar el resaltado (asi el conteo es estable).
  function markIfExists(el, needle) {
    const target = needle.trim().toLowerCase();
    if (!target) return null;
    return Array.from(el.querySelectorAll(".apa-mark")).find(
      (m) => m.textContent.trim().toLowerCase() === target
    );
  }

  // envuelve la primera aparicion de needle en el elemento, respetando
  // saltos de linea y sin tocar texto ya marcado
  function wrapText(el, needle, cls, meta, fid) {
    const existing = markIfExists(el, needle);
    if (existing) {
      existing.dataset.fids = (existing.dataset.fids || "") + "," + fid;
      // gana la severidad mas alta
      if (rank(meta.severity) > rank(existing.dataset.sev)) {
        existing.dataset.sev = meta.severity;
        existing.classList.remove("apa-mark-error", "apa-mark-warning", "apa-mark-info");
        existing.classList.add(SEV[meta.severity] || SEV.info);
      }
      return existing;
    }
    const target = needle.toLowerCase();
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) {
      const n = walker.currentNode;
      if (!n.parentNode.closest(".apa-mark")) nodes.push(n);
    }
    for (const node of nodes) {
      const at = node.data.toLowerCase().indexOf(target);
      if (at < 0) continue;
      const span = document.createElement("span");
      span.className = "apa-mark " + cls;
      span.dataset.sev = meta.severity || "info";
      span.dataset.fids = String(fid);
      span.tabIndex = 0;
      const before = node.data.slice(0, at);
      const hit = node.data.slice(at, at + needle.length);
      const after = node.data.slice(at + needle.length);
      span.textContent = hit;
      const frag = document.createDocumentFragment();
      if (before) frag.appendChild(document.createTextNode(before));
      frag.appendChild(span);
      if (after) frag.appendChild(document.createTextNode(after));
      node.parentNode.replaceChild(frag, node);
      return span;
    }
    return null;
  }

  function rank(sev) {
    return sev === "error" ? 3 : sev === "warning" ? 2 : 1;
  }

  function apply(findings) {
    clear();
    const p = root();
    if (!p) return { marks: 0, blocks: 0, unmatched: 0 };
    registry.clear();
    let marks = 0;
    let blocksFlagged = 0;
    let unmatched = 0;
    const flagged = new Set();

    (findings || []).forEach((f, i) => {
      const el = locate(f);
      if (!el) {
        unmatched++;
        return;
      }
      registry.set(String(i), f);
      const cls = SEV[f.severity] || SEV.info;
      let span = null;
      if (f.excerpt && f.excerpt.length > 8) {
        span = wrapText(el, f.excerpt.slice(0, 60), cls, f, i);
      }
      if (!span) {
        // sin fragmento localizable: se marca el parrafo entero en el margen
        el.classList.add("apa-flagged", cls);
        if (!flagged.has(el)) {
          flagged.add(el);
          blocksFlagged++;
        }
      } else {
        marks++;
        span.addEventListener("click", onMarkClick);
        span.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onMarkClick(e);
          }
        });
      }
    });

    return { marks, blocks: blocksFlagged, unmatched };
  }

  /* ---------- hooks que inyecta la app ---------- */
  const hooks = {
    sections: () => [],
    afterFix: () => {},
    openReport: () => {},
  };

  /* ---------- Globito explicativo ---------- */
  let pop = null;

  function close() {
    if (pop) {
      pop.remove();
      pop = null;
    }
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function onMarkClick(e) {
    e.preventDefault();
    e.stopPropagation();
    const el = e.currentTarget;
    close();
    const fids = (el.dataset.fids || "")
      .split(",")
      .map((x) => registry.get(x.trim()))
      .filter(Boolean);
    const list = fids.length ? fids : [{}];
    const rules = list.map((f) => f.rule_id || "").filter(Boolean);
    const uniqueRules = Array.from(new Set(rules));
    const sev =
      list.find((f) => f.severity === "error") ||
      list.find((f) => f.severity === "warning") ||
      list[0];
    const isAuto =
      window.Fixer &&
      uniqueRules.some((r) => window.Fixer.CORRECTIONS.some((c) => c.rules.includes(r)));
    const label =
      sev.severity === "error" ? "Error" : sev.severity === "warning" ? "Alerta" : "Observación";

    const msgs = list
      .map((f) => `<li><b>${esc(f.rule_id || "")}</b> ${esc(f.message || "")}${
        f.suggestion ? `<span class="apa-pop-sug">${esc(f.suggestion)}</span>` : ""
      }</li>`)
      .join("");

    pop = document.createElement("div");
    pop.className = "apa-pop sev-" + (sev.severity || "info");
    pop.innerHTML =
      `<div class="apa-pop-head">
         <span class="apa-pop-tag">${label}</span>
         <span class="apa-pop-rule">${uniqueRules.join(" + ") || ""}</span>
         ${list.length > 1 ? `<span class="apa-pop-more">${list.length} avisos</span>` : ""}
       </div>
       <ul class="apa-pop-list">${msgs}</ul>
       <div class="apa-pop-foot">
         ${
           isAuto
             ? '<button class="apa-pop-fixbtn">Corregir esto</button>'
             : '<button class="apa-pop-report">Ver en el informe</button>'
         }
         <button class="apa-pop-close">Cerrar</button>
       </div>`;

    document.body.appendChild(pop);
    const r = el.getBoundingClientRect();
    const pr = pop.getBoundingClientRect();
    const left = Math.min(
      Math.max(8, r.left + window.scrollX + r.width / 2 - pr.width / 2),
      window.scrollX + document.documentElement.clientWidth - pr.width - 8
    );
    let top = r.top + window.scrollY - pr.height - 8;
    if (top < 4) top = r.bottom + window.scrollY + 8;
    pop.style.left = left + "px";
    pop.style.top = top + "px";

    pop.querySelector(".apa-pop-close").addEventListener("click", close);
    const fixBtn = pop.querySelector(".apa-pop-fixbtn");
    if (fixBtn) {
      fixBtn.addEventListener("click", () => {
        const items = window.Fixer.CORRECTIONS.filter((c) =>
          uniqueRules.some((r) => c.rules.includes(r))
        );
        const res = window.Fixer.applySelected(items, {
          sections: hooks.sections(),
        });
        close();
        hooks.afterFix(res);
      });
    }
    const repBtn = pop.querySelector(".apa-pop-report");
    if (repBtn) {
      repBtn.addEventListener("click", () => {
        close();
        hooks.openReport();
      });
    }
  }

  document.addEventListener("click", (e) => {
    if (pop && !pop.contains(e.target) && !e.target.classList.contains("apa-mark"))
      close();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });

  window.Marker = {
    apply,
    clear,
    close,
    setHooks(h) {
      Object.assign(hooks, h || {});
    },
  };
})();