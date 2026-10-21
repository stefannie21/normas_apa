/* Guardado local (IndexedDB).
   Dos cosas distintas:
     - SessionStore: el documento abierto y sus ediciones (clave "current").
     - LibraryStore: la biblioteca de tesis de "Mis tesis", una por documento.
   Se usa IndexedDB y no localStorage porque los .docx con imagenes superan
   con facilidad los 5 MB de localStorage. */
const Store = (function () {
  "use strict";

  const DB_NAME = "apa-studio";
  const STORE = "docs";
  const LIB = "library";
  const KEY = "current";
  const VERSION = 2;

  function open() {
    return new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        reject(new Error("Este navegador no soporta IndexedDB"));
        return;
      }
      const req = indexedDB.open(DB_NAME, VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE);
        if (!db.objectStoreNames.contains(LIB)) {
          db.createObjectStore(LIB, { keyPath: "id" });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  function tx(storeName, mode, fn) {
    return open().then(
      (db) =>
        new Promise((resolve, reject) => {
          const t = db.transaction(storeName, mode);
          const store = t.objectStore(storeName);
          let result;
          try {
            result = fn(store);
          } catch (e) {
            reject(e);
            return;
          }
          t.oncomplete = () =>
            resolve(result && result.result !== undefined ? result.result : result);
          t.onerror = () => reject(t.error);
          t.onabort = () => reject(t.error);
        })
    );
  }

  /* ---------- Sesion: un solo documento abierto ---------- */
  function save(doc) {
    return tx(STORE, "readwrite", (store) => store.put(doc, KEY));
  }

  function load() {
    return tx(STORE, "readonly", (store) => store.get(KEY)).then((value) => value || null);
  }

  function clear() {
    return tx(STORE, "readwrite", (store) => store.delete(KEY));
  }

  /* ---------- Biblioteca de tesis ---------- */
  function listTheses() {
    return tx(LIB, "readonly", (store) => store.getAll()).then((rows) => rows || []);
  }

  function getThesis(id) {
    return tx(LIB, "readonly", (store) => store.get(id));
  }

  // El store se creo con keyPath "id", asi que put() NO admite clave aparte:
  // pasarla lanza InvalidStateError.
  function upsertThesis(rec) {
    return tx(LIB, "readwrite", (store) => store.put(rec)).then(() => rec);
  }

  function deleteThesis(id) {
    return tx(LIB, "readwrite", (store) => store.delete(id));
  }

  return {
    session: { save, load, clear },
    library: { listTheses, getThesis, upsertThesis, deleteThesis },
  };
})();

const SessionStore = Store.session;
const LibraryStore = Store.library;

export { SessionStore, LibraryStore };
