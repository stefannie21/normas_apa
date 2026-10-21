/* Biblioteca de tesis ("Mis tesis").
   Capa de datos, sin nada de interfaz: guarda cada documento en IndexedDB
   (LibraryStore) junto al archivo original, para poder reabrir la tesis sin
   volver a subirla. La interfaz vive en views/tesis.js.

   El estado de cada tesis sale del ultimo analisis:
     pendiente  = todavia no se ha verificado
     proceso    = verificada con errores pendientes
     completada = verificada y sin errores
*/
import { LibraryStore } from "./editor/storage.js";

const LABEL = {
  completada: "Completada",
  proceso: "En proceso",
  pendiente: "Pendiente",
};

const COLOR = { completada: "#1e8449", proceso: "#e8a33d", pendiente: "#e35d6a" };

function fileExt(name) {
  const m = /\.([a-z0-9]+)$/i.exec(String(name || ""));
  return m ? m[1].toLowerCase() : "";
}

function extClass(name) {
  const e = fileExt(name);
  if (e === "docx") return "docx";
  if (e === "pdf") return "pdf";
  return "otro";
}

function humanSize(bytes) {
  const b = Number(bytes) || 0;
  if (b >= 1024 * 1024) return Math.round(b / (1024 * 1024)) + " MB";
  if (b >= 1024) return Math.round(b / 1024) + " KB";
  return b + " B";
}

function titleFromName(name) {
  return String(name || "Documento")
    .replace(/\.[a-z0-9]+$/i, "")
    .replace(/[_-]+/g, " ")
    .trim();
}

function stamp(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return "—";
  const dos = (n) => String(n).padStart(2, "0");
  return (
    dos(d.getDate()) + "/" + dos(d.getMonth() + 1) + "/" + d.getFullYear() +
    " · " + dos(d.getHours()) + ":" + dos(d.getMinutes())
  );
}

function statusFromAnalysis(summary) {
  const err = summary && summary.by_severity && summary.by_severity.error;
  if (err == null) return "pendiente";
  return err > 0 ? "proceso" : "completada";
}

// Texto por el que se busca. La extension se excluye a proposito: ".docx"
// trae una "c" y hacia que buscar "c" devolviera todas las tesis.
function searchText(rec) {
  return (
    rec.title + " " + (rec.author || "") + " " +
    String(rec.name || "").replace(/\.[a-z0-9]+$/i, "")
  ).toLowerCase();
}

async function list() {
  let rows = [];
  try {
    rows = (await LibraryStore.listTheses()) || [];
  } catch (e) {
    rows = []; // la biblioteca es una comodidad: si falla, la vista se queda vacia
  }
  rows.sort((a, b) => String(b.addedAt || "").localeCompare(String(a.addedAt || "")));
  return rows;
}

// Da de alta el archivo (o actualiza el ya existente con el MISMO nombre, que
// es el caso normal al reabrir una tesis).
async function record(file) {
  const prev = await LibraryStore.listTheses();
  const same = prev.find((r) => r.name === file.name);
  const rec = {
    id: same ? same.id : "t" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    name: file.name,
    title: same ? same.title : titleFromName(file.name),
    author: (same && same.author) || "",
    size: file.size,
    ext: fileExt(file.name),
    blob: file,
    addedAt: same ? same.addedAt : new Date().toISOString(),
    // al reabrir un documento sin verificar, vuelve a quedar pendiente
    status: "pendiente",
    score: null,
    analyzedAt: null,
  };
  await LibraryStore.upsertThesis(rec);
  return rec;
}

// El analisis es lo unico que hoy define el estado de una tesis.
async function syncAnalysis(summary, fileName) {
  if (!fileName) return null;
  const rows = await LibraryStore.listTheses();
  const rec = rows.find((r) => r.name === fileName);
  if (!rec) return null;
  rec.status = statusFromAnalysis(summary);
  rec.score = summary && summary.compliance_score != null ? summary.compliance_score : null;
  rec.analyzedAt = new Date().toISOString();
  await LibraryStore.upsertThesis(rec);
  return rec;
}

function remove(id) {
  return LibraryStore.deleteThesis(id);
}

export const Library = {
  LABEL,
  COLOR,
  extClass,
  humanSize,
  titleFromName,
  stamp,
  statusFromAnalysis,
  searchText,
  list,
  record,
  syncAnalysis,
  remove,
};
