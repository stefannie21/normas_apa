/* Prueba end-to-end con Chrome DevTools Protocol:
   1) Siembra la biblioteca con 1 tesis en proceso + 1 pendiente.
   2) Comprueba que "Resumen de tu actividad" cuente 1 pendiente.
   3) Hace clic en "Ver todas" y comprueba que navega a Mis tesis.
*/
const { spawn } = require("child_process");
const path = require("path");

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PROFILE = path.join(__dirname, ".chrome-cdp-profile");
const PORT = 9222;
const BASE = "http://127.0.0.1:8000";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const chrome = spawn(CHROME, [
    "--headless=new", "--disable-gpu", "--no-sandbox",
    "--remote-debugging-port=" + PORT,
    "--user-data-dir=" + PROFILE,
    "--no-first-run", "--no-default-browser-check",
    "about:blank",
  ], { stdio: "ignore", windowsHide: true });

  let target = null;
  for (let i = 0; i < 40; i++) {
    await sleep(400);
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const list = await res.json();
      target = list.find((t) => t.type === "page");
      if (target) break;
    } catch (_) { /* todavia arranca */ }
  }
  if (!target) { console.log("ERROR: Chrome no arranco"); chrome.kill(); return; }

  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

  let seq = 0;
  const pending = new Map();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const p = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? p.reject(new Error(JSON.stringify(msg.error))) : p.resolve(msg.result);
    }
  };
  const send = (method, params = {}) => new Promise((res, rej) => {
    const id = ++seq;
    pending.set(id, { resolve: res, reject: rej });
    ws.send(JSON.stringify({ id, method, params }));
  });

  const evaluate = async (expr) => {
    const r = await send("Runtime.evaluate", {
      expression: expr, returnByValue: true, awaitPromise: true,
    });
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
    return r.result.value;
  };

  await send("Page.enable");
  await send("Runtime.enable");

  // 1) Sembrar (los estaticos se sirven bajo /static)
  await send("Page.navigate", { url: BASE + "/static/_seed.html" });
  await sleep(2200);
  console.log("1) Seed:", await evaluate("document.getElementById('out') ? document.getElementById('out').textContent : 'redirigido a / (seed hecho)'"));

  // 2) Cargar la app
  await send("Page.navigate", { url: BASE + "/" });
  await sleep(2500);

  const contadores = await evaluate(`(function () {
    const g = (id) => { const e = document.getElementById(id); return e ? e.textContent.trim() : '(falta)'; };
    return {
      proceso: g('resumen-num-proceso'),
      completada: g('resumen-num-completada'),
      pendiente: g('resumen-num-pendiente'),
      pct: g('resumen-porcentaje'),
      filas: document.querySelectorAll('#dash-recientes .rec').length,
    };
  })()`);
  console.log("2) Contadores en Inicio:", JSON.stringify(contadores));

  // 3) Clic en "Ver todas"
  const clickResult = await evaluate(`(function () {
    const a = document.querySelector("[data-act='ver-todas']");
    if (!a) return 'NO_EXISTE_EL_ENLACE';
    a.click();
    return 'CLICK_OK';
  })()`);
  await sleep(1200);
  const destino = await evaluate(`(function () {
    const activo = document.querySelector('.sb-item.active');
    return {
      titulo: document.title,
      menuActivo: activo ? activo.dataset.view + ' / ' + activo.querySelector('.sb-label').textContent.trim() : '(ninguno)',
      contieneMisTesis: (document.getElementById('view-inner') || document.body).textContent.includes('Mis tesis'),
      url: location.href,
    };
  })()`);
  console.log("3) Clic:", clickResult);
  console.log("4) Destino:", JSON.stringify(destino));

  const ok = contadores.pendiente === "1" && clickResult === "CLICK_OK"
    && destino.menuActivo.indexOf("tesis") !== -1 && destino.contieneMisTesis;
  console.log("");
  console.log(ok ? "=== RESULTADO: TODO CORRECTO ===" : "=== RESULTADO: FALLO ===");

  ws.close();
  chrome.kill();
}

main().catch((e) => { console.error("ERROR:", e); process.exit(1); });
