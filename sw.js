/* Service worker for المعاجم الثلاثة
 * Strategy:
 *   - shell (HTML/CSS/icons/manifest): cache-first, refresh in background
 *   - small JSON data (maqayis, mufradat, lisan roots/chunks meta): cache-first
 *   - lisan chunk files (large): stale-while-revalidate, kept on demand
 */
const VERSION = "v1";
const SHELL_CACHE = "mojam-shell-" + VERSION;
const DATA_CACHE  = "mojam-data-"  + VERSION;
const LISAN_CACHE = "mojam-lisan-" + VERSION;

const SHELL = [
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
  e.waitUntil(caches.open(SHELL_CACHE).then(c => c.addAll(SHELL).catch(() => {})));
});

self.addEventListener("activate", e => {
  e.waitUntil((async () => {
    const keep = new Set([SHELL_CACHE, DATA_CACHE, LISAN_CACHE]);
    const names = await caches.keys();
    await Promise.all(names.filter(n => !keep.has(n)).map(n => caches.delete(n)));
    await self.clients.claim();
  })());
});

function isLisanChunk(url) {
  return /\/data\/lisan\/chunks\/chunk_\d+\.json$/.test(url.pathname);
}
function isData(url) {
  return /\/data\//.test(url.pathname);
}

async function cacheFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req);
  if (hit) {
    fetch(req).then(r => { if (r && r.ok) cache.put(req, r); }).catch(() => {});
    return hit;
  }
  const r = await fetch(req);
  if (r && r.ok) cache.put(req, r.clone());
  return r;
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req);
  const fetcher = fetch(req).then(r => { if (r && r.ok) cache.put(req, r.clone()); return r; }).catch(() => hit);
  return hit || fetcher;
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  if (isLisanChunk(url)) {
    e.respondWith(staleWhileRevalidate(req, LISAN_CACHE));
  } else if (isData(url)) {
    e.respondWith(cacheFirst(req, DATA_CACHE));
  } else {
    e.respondWith(cacheFirst(req, SHELL_CACHE));
  }
});
