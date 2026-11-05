/* Prueba end-to-end: el botón de la columna Acciones de "Mis tesis"
   es un tacho de basura y elimina realmente el registro. */
const { spawn } = require("child_process");
const path = require("path");

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PROFILE = path.join(__dirname, ".chrome-cdp-profile");
const PORT = 9223;
const BASE = "http://127.0.0.1:8000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const chrome = spawn(CHROME, [
    "--headless=new", "--disable-gpu", "--no-sandbox",
    "--remote-debugging-port=" + PORT,
    "--user-data-dir=" + PROFILE,
    "--no-first-run", "--no-default-browser-check", "about:blank",
  ], { stdio: "ignore", windowsHide: true });

  let target = null;
  for (let i = 0; i < 40; i++) {
    await sleep(400);
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      target = list.find((t) => t.type === "page");
      if (target) break;
    } catch (_) {}
  }
  if (!target) { console.log("ERROR: Chrome no arranco"); chrome.kill(); return; }

  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let seq = 0;
  const pending = new Map();
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id); pending.delete(m.id);
      m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result);
    }
  };
  const send = (method, params = {}) => new Promise((res, rej) => {
    const id = ++seq; pending.set(id, { resolve: res, reject: rej });
    ws.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async (expr) => {
    const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
    return r.result.value;
  };

  await send("Page.enable"); await send("Runtime.enable");
  await send("Page.navigate", { url: BASE + "/static/_seed.html" });
  await sleep(2200);
  await send("Page.navigate", { url: BASE + "/" });
  await sleep(2200);

  // ir a Mis tesis
  await evaluate("document.querySelector('[data-view=\"tesis\"]').click()");
  await sleep(1200);

  const antes = await evaluate(`(function () {
    const filas = [...document.querySelectorAll('#tv-body tr')];
    return {
      total: filas.length,
      botones: filas[0] ? [...filas[0].querySelectorAll('[data-tv-row]')].map(b => b.dataset.tvRow) : [],
      esTrash: filas[0] ? !!filas[0].querySelector('[data-tv-row="delete"] svg') : false,
      titulo: filas[0] ? filas[0].querySelector('[data-tv-row="delete"]').getAttribute('title') : '',
    };
  })()`);
  console.log("1) Antes de eliminar:", JSON.stringify(antes));

  // aceptar el confirm y pulsar el tacho de la primera fila
  const despues = await evaluate(`(async function () {
    window.confirm = () => true;
    const nombre = document.querySelector('#tv-body tr .tv-file-titulo').textContent;
    document.querySelector('#tv-body tr [data-tv-row="delete"]').click();
    await new Promise(r => setTimeout(r, 900));
    const filas = [...document.querySelectorAll('#tv-body tr')];
    return { eliminada: nombre, total: filas.length,
             restantes: filas.map(f => f.querySelector('.tv-file-titulo').textContent) };
  })()`);
  console.log("2) Despues de eliminar:", JSON.stringify(despues));

  const ok = antes.total === 2 && antes.botones.join(",") === "open,download,delete"
    && antes.esTrash && antes.titulo === "Eliminar esta tesis"
    && despues.total === 1;
  console.log("");
  console.log(ok ? "=== RESULTADO: TODO CORRECTO ===" : "=== RESULTADO: FALLO ===");

  ws.close(); chrome.kill();
}
main().catch((e) => { console.error("ERROR:", e); process.exit(1); });
