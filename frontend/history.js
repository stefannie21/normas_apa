/* Historial de cambios del documento: deshacer / rehacer.

   Antes se delegaba en el historial nativo de contentedEditable, y por eso
   fallaba: esa pila solo recoge lo tecleado y se destruye en cuanto el DOM se
   reconstruye. Aqui se repagina el documento (root.innerHTML = ""), se envuelven
   los avisos en <span class="apa-mark"> y se aplican las correcciones, asi que
   un solo paso de "Reorganizar paginas" dejaba Ctrl+Z sin nada que deshacer.
   Lo mismo pasaba con los cambios que ni siquiera pasan por execCommand
   (applyToBlocks, los selectores de fuente e interlineado, el selector de
   estilos), porque el navegador no llega a verlos.

   Aqui se guarda una instantanea completa de #page con cada cambio. Un
   MutationObserver la toma sola, de modo que cualquier operacion de la
   aplicacion queda deshacible sin tener que acordarse de registrarla. */
(function () {
  "use strict";

  var MAX_STEPS = 60;     // instantaneas conservadas hacia atras
  var COALESCE_MS = 600;  // las pulsaciones seguidas se agrupan en un solo paso

  var root = null;
  var past = [];
  var future = [];
  var baseline = null;   // estado en pantalla, tal y como estaba al ultimo paso
  var timer = null;
  var restoring = false;
  var observer = null;
  var listeners = [];
  var afterRestore = null;

  function host() {
    return root || document.getElementById("page");
  }

  /* ------------------------------------------------------------ seleccion */

  // La seleccion se guarda como camino de indices hijos: sigue siendo valida
  // aunque el DOM se haya reconstruido entero entre medias.
  function nodePath(node) {
    var path = [];
    var cur = node;
    var top = host();
    while (cur && cur !== top) {
      var parent = cur.parentNode;
      if (!parent) return null;
      path.unshift(Array.prototype.indexOf.call(parent.childNodes, cur));
      cur = parent;
    }
    return cur === top ? path : null;
  }

  function nodeFromPath(path) {
    var cur = host();
    for (var i = 0; i < path.length; i++) {
      if (!cur || !cur.childNodes[path[i]]) return null;
      cur = cur.childNodes[path[i]];
    }
    return cur;
  }

  function maxOffset(node) {
    return node.nodeType === 3 ? node.length : node.childNodes.length;
  }

  function captureSel() {
    var sel = window.getSelection();
    var top = host();
    if (!sel || !sel.rangeCount || !top) return null;
    var r = sel.getRangeAt(0);
    if (!top.contains(r.startContainer) || !top.contains(r.endContainer)) return null;
    return {
      start: nodePath(r.startContainer),
      startOffset: r.startOffset,
      end: nodePath(r.endContainer),
      endOffset: r.endOffset,
    };
  }

  function restoreSel(saved) {
    if (!saved) return;
    var sel = window.getSelection();
    if (!sel) return;
    try {
      var a = nodeFromPath(saved.start);
      var b = nodeFromPath(saved.end);
      if (!a || !b) return;
      var r = document.createRange();
      r.setStart(a, Math.min(saved.startOffset, maxOffset(a)));
      r.setEnd(b, Math.min(saved.endOffset, maxOffset(b)));
      sel.removeAllRanges();
      sel.addRange(r);
    } catch (e) {
      /* el nodo ya no existe: se deja el cursor donde este */
    }
  }

  /* ------------------------------------------------------------ instantanea */

  // Se guarda tambien el atributo style de #page: "Aplicar formato base"
  // cambia desde ahi la fuente, el interlineado y la sangria.
  function take() {
    var el = host();
    if (!el) return null;
    return { html: el.innerHTML, style: el.getAttribute("style"), sel: captureSel() };
  }

  function apply(state) {
    var el = host();
    if (!el || !state) return;
    restoring = true;
    clearTimeout(timer);
    timer = null;
    try {
      el.innerHTML = state.html;
      if (state.style == null) el.removeAttribute("style");
      else el.setAttribute("style", state.style);
      // La repaginacion reconstruye las hojas, asi que el cursor se devuelve
      // despues de ella, no antes.
      if (typeof afterRestore === "function") afterRestore();
      restoreSel(state.sel);
    } finally {
      restoring = false;
    }
    // el repaginado ha movido nodos: la base se vuelve a tomar sobre el
    // resultado real para no guardar un estado imposible de alcanzar
    baseline = take();
  }

  /* ----------------------------------------------------------------- pasos */

  function notify() {
    var canUndo = past.length > 0;
    var canRedo = future.length > 0;
    refreshButtons(canUndo, canRedo);
    listeners.forEach(function (fn) {
      try {
        fn(canUndo, canRedo);
      } catch (e) {
        /* un oyente con error no debe romper el historial */
      }
    });
  }

  function refreshButtons(canUndo, canRedo) {
    var u = document.querySelector('.rbtn[data-cmd="undo"]');
    var r = document.querySelector('.rbtn[data-cmd="redo"]');
    if (u) {
      u.disabled = !canUndo;
      u.title = canUndo ? "Deshacer (Ctrl+Z)" : "No hay nada que deshacer";
    }
    if (r) {
      r.disabled = !canRedo;
      r.title = canRedo ? "Rehacer (Ctrl+Y)" : "No hay nada que rehacer";
    }
  }

  // Cierra el grupo de cambios en curso: lo que hubiera en pantalla pasa a
  // "se puede deshacer" y la base avanza al estado nuevo.
  function commit() {
    timer = null;
    if (restoring) return;
    var next = take();
    if (!next) return;
    if (baseline && baseline.html === next.html && baseline.style === next.style) return;
    if (baseline) past.push(baseline);
    baseline = next;
    if (past.length > MAX_STEPS) past.splice(0, past.length - MAX_STEPS);
    // un cambio nuevo descarta la rama de rehacer
    future.length = 0;
    notify();
  }

  // Cierra el grupo de cambios en curso antes de deshacer o rehacer.
  //
  // No basta con lanzar el commit pendiente: el MutationObserver entrega su
  // callback como microtask, asi que si se pulsa Ctrl+Z en el mismo instante
  // en que se termina de teclear el temporizador todavia no existe. Por eso
  // flush() compara siempre el DOM actual con la base, en lugar de depender
  // solo del temporizador.
  function flush() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    commit();
  }

  function undo() {
    flush();
    if (!past.length) return false;
    var current = take();
    var prev = past.pop();
    future.push(current);
    apply(prev);
    notify();
    return true;
  }

  function redo() {
    flush();
    if (!future.length) return false;
    var current = take();
    var nextState = future.pop();
    past.push(current);
    if (past.length > MAX_STEPS) past.splice(0, past.length - MAX_STEPS);
    apply(nextState);
    notify();
    return true;
  }

  // Al abrir un documento distinto el historial anterior ya no tiene sentido.
  function reset() {
    clearTimeout(timer);
    timer = null;
    past.length = 0;
    future.length = 0;
    baseline = take();
    notify();
  }

  /* ----------------------------------------------------------- observacion */

  function observe() {
    var el = host();
    if (!el) return;
    if (observer) observer.disconnect();
    observer = new MutationObserver(function () {
      if (restoring) return;
      clearTimeout(timer);
      timer = setTimeout(commit, COALESCE_MS);
    });
    observer.observe(el, {
      childList: true,
      subtree: true,
      attributes: true,
      characterData: true,
    });
  }

  /* ------------------------------------------------------------- teclado */

  function onKeyDown(e) {
    if (!e.ctrlKey && !e.metaKey) return;
    var key = String(e.key || "").toLowerCase();
    if (key !== "z" && key !== "y") return;
    // dentro de un campo de texto el historial nativo sigue siendo el correcto
    var t = e.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA")) return;
    var el = host();
    if (!el || el.hidden) return;
    // se atiende siempre el historial propio: el del navegador ya no es fiable
    e.preventDefault();
    if (key === "y") redo();
    else if (e.shiftKey) redo();
    else undo();
  }

  function init(options) {
    root = document.getElementById("page");
    if (!root) return;
    afterRestore = (options && options.afterRestore) || null;
    document.addEventListener("keydown", onKeyDown);
    reset();
    observe();
  }

  window.History = {
    init: init,
    undo: undo,
    redo: redo,
    flush: flush,
    reset: reset,
    refresh: function () {
      refreshButtons(past.length > 0, future.length > 0);
    },
    isUndoing: function () {
      return restoring;
    },
    onChange: function (fn) {
      if (typeof fn === "function") listeners.push(fn);
    },
    canUndo: function () {
      return past.length > 0;
    },
    canRedo: function () {
      return future.length > 0;
    },
  };
})();