/* Service worker for المعاجم الثلاثة
 *
 * VERSION is bumped on every commit by .githooks/pre-commit so existing
 * PWA users automatically receive updates: new SW installs (skipWaiting),
 * old caches are dropped on activate, clients.claim takes over, and
 * controllerchange in index.html triggers a one-time reload.
 *
 * Strategies:
 *   - Navigation (HTML)  : NETWORK-FIRST  — online users always see the
 *                          freshest index.html; offline users get the cached
 *                          copy. This is the main defence against staleness.
 *   - Lisan chunks       : cache-first    — immutable once published, large
 *   - Other data JSON    : cache-first    — kept under DATA_VERSION so routine
 *                          shell deploys don't re-download the ~15 MB of data
 *   - Icons / manifest   : SWR            — refresh quietly in background
 */
const VERSION = "v20260609172845";
// Data files (maqayis/mufradat/bushro/lisan JSON) are immutable and large, so
// they are cached under their OWN version — NOT the shell VERSION. The pre-commit
// hook only bumps VERSION, so routine deploys (index.html/sw.js changes) keep the
// ~15 MB of dictionary data cached instead of re-downloading it on every refresh.
// Bump DATA_VERSION by hand only when the data/ files actually change.
const DATA_VERSION = "v5";
const SHELL_CACHE = "mojam-shell-" + VERSION;
const DATA_CACHE  = "mojam-data-"  + DATA_VERSION;
const LISAN_CACHE = "mojam-lisan-" + DATA_VERSION;

const PRECACHE = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./favicon.png",
  "./apple-touch-icon.png",
  "./icon-192.png",
  "./icon-512.png",
  "./icon.svg",
];

self.addEventListener("install", e => {
  self.skipWaiting();
  e.waitUntil(caches.open(SHELL_CACHE).then(c => c.addAll(PRECACHE).catch(() => {})));
});

self.addEventListener("activate", e => {
  e.waitUntil((async () => {
    const keep = new Set([SHELL_CACHE, DATA_CACHE, LISAN_CACHE]);
    const names = await caches.keys();
    await Promise.all(names.filter(n => !keep.has(n)).map(n => caches.delete(n)));
    await self.clients.claim();
  })());
});

const isLisanChunk = url => /\/data\/lisan\/chunks\/chunk_\d+\.json$/.test(url.pathname);
const isData       = url => /\/data\//.test(url.pathname);
const isNavigation = req => req.mode === "navigate"
                          || (req.headers.get("Accept") || "").includes("text/html");

async function networkFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const r = await fetch(req);
    if (r && r.ok) cache.put(req, r.clone());
    return r;
  } catch (err) {
    const hit = await cache.match(req)
              || await cache.match(new URL("./", location).href)
              || await cache.match(new URL("./index.html", location).href);
    if (hit) return hit;
    throw err;
  }
}

async function cacheFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req);
  if (hit) return hit;
  const r = await fetch(req);
  if (r && r.ok) cache.put(req, r.clone());
  return r;
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req);
  const fetcher = fetch(req)
    .then(r => { if (r && r.ok) cache.put(req, r.clone()); return r; })
    .catch(() => hit);
  return hit || fetcher;
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  if (isNavigation(req)) {
    e.respondWith(networkFirst(req, SHELL_CACHE));
  } else if (isLisanChunk(url)) {
    e.respondWith(cacheFirst(req, LISAN_CACHE));
  } else if (isData(url)) {
    e.respondWith(cacheFirst(req, DATA_CACHE));
  } else {
    e.respondWith(staleWhileRevalidate(req, SHELL_CACHE));
  }
});
