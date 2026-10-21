/* Guardado local de la sesion (IndexedDB).
   Permite conservar el documento original y las ediciones hechas en la web
   entre recargas, sin depender del servidor y sin el limite de 5 MB de
     localStorage (los .docx con imagenes lo superan con facilidad). */
const SessionStore = (function () {
  "use strict";

  const DB_NAME = "apa-studio";
  const STORE = "docs";
  const KEY = "current";
  const VERSION = 1;

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
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  function tx(mode, fn) {
    return open().then(
      (db) =>
        new Promise((resolve, reject) => {
          const t = db.transaction(STORE, mode);
          const store = t.objectStore(STORE);
          let result;
          try {
            result = fn(store);
          } catch (e) {
            reject(e);
            return;
          }
          t.oncomplete = () => resolve(result && result.result !== undefined ? result.result : result);
          t.onerror = () => reject(t.error);
          t.onabort = () => reject(t.error);
        })
    );
  }

  function save(doc) {
    return tx("readwrite", (store) => store.put(doc, KEY));
  }

  function load() {
    return tx("readonly", (store) => store.get(KEY)).then((value) => value || null);
  }

  function clear() {
    return tx("readwrite", (store) => store.delete(KEY));
  }

  return { save, load, clear };
})();

export { SessionStore };
