// FitBasket service worker: makes the app installable and usable offline.
const CACHE = "fitbasket-v3";
const PYODIDE_HOST = "cdn.jsdelivr.net";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icons/icon-192.png"];

self.addEventListener("install", (event) => {
  // Best effort: a missing file (e.g. no Python bundle when served by the API) must not block install.
  event.waitUntil(
    caches
      .open(CACHE)
      .then((c) => Promise.all(SHELL.map((path) => c.add(path).catch(() => undefined))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // model API calls (POST) always go to the network
  const url = new URL(req.url);

  // Pyodide files are versioned and immutable: cache once, then serve offline.
  if (url.hostname === PYODIDE_HOST && url.pathname.startsWith("/pyodide/")) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            if (res.ok) caches.open(CACHE).then((c) => c.put(req, res.clone()));
            return res;
          }),
      ),
    );
    return;
  }
  if (url.origin !== self.location.origin || url.pathname.includes("/api/")) return;

  // Pages and the Python bundle: network first so updates arrive, cached copy when offline.
  if (req.mode === "navigate" || url.pathname.endsWith(".zip")) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const key = req.mode === "navigate" ? "./index.html" : req;
          if (res.ok) caches.open(CACHE).then((c) => c.put(key, res.clone()));
          return res;
        })
        .catch(() => caches.match(req.mode === "navigate" ? "./index.html" : req, { ignoreSearch: true })),
    );
    return;
  }

  // Scripts, styles, the Python bundle: serve cached, refresh in the background.
  event.respondWith(
    caches.match(req).then((hit) => {
      const fresh = fetch(req)
        .then((res) => {
          if (res.ok) caches.open(CACHE).then((c) => c.put(req, res.clone()));
          return res;
        })
        .catch(() => hit);
      return hit || fresh;
    }),
  );
});
