/* Eligibility Checker: privacy-aware offline shell. */
const CACHE_VERSION = 'eligibility-checker-emerald-v5';
const SHELL_CACHE = `${CACHE_VERSION}-shell`;
const ASSET_CACHE = `${CACHE_VERSION}-assets`;
const SHELL_URLS = ['/', '/offline'];
const ASSET_URLS = [
  '/static/css/main.min.css?v=emerald-all-20261127',
  '/static/css/midnight.min.css?v=emerald-section-motion-20261127',
  '/static/js/ui-motion.min.js?v=emerald-all-20261127',
  '/static/js/writing.min.js?v=typewriter-sections-loop-20261127',
  '/static/js/base-ui.min.js?v=emerald-all-20261127',
  '/static/js/pwa.js?v=emerald-all-20261127',
  '/static/js/offline-storage.js',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const shell = await caches.open(SHELL_CACHE);
    await Promise.allSettled(SHELL_URLS.map(async url => {
      const response = await fetch(url, { credentials: 'same-origin' });
      if (response.ok && response.type === 'basic') await shell.put(url, response);
    }));
    const assets = await caches.open(ASSET_CACHE);
    await Promise.allSettled(ASSET_URLS.map(async url => {
      const response = await fetch(url, { credentials: 'same-origin' });
      if (response.ok && response.type === 'basic') await assets.put(url, response);
    }));
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keep = new Set([SHELL_CACHE, ASSET_CACHE]);
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => /^(eligibility-checker-|ec-static-|ec-api-)/.test(key) && !keep.has(key)).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

function privateOrTransactional(pathname) {
  return /^\/(?:api(?:\/|$)|payment(?:\/|[-_]|$)|admin(?:\/|$)|submit[-_][^/]*|enter[-_]?details(?:\/|$)|(?:degree|diploma|kmtc|certificate|artisan|collection)[-_]results(?:\/|$)|results(?:\/|$)|basket(?:\/|$)|auth(?:\/|$)|user[-_]info(?:\/|$)|verified[-_]dashboard(?:\/|$))/.test(pathname);
}

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || privateOrTransactional(url.pathname)) return;

  if (url.pathname.startsWith('/static/videos/')) return; // Large media stays network-only.

  if (url.pathname.startsWith('/static/')) {
    event.respondWith((async () => {
      const cache = await caches.open(ASSET_CACHE);
      const cached = await cache.match(request);
      const refresh = fetch(request).then(response => {
        if (response.ok && response.type === 'basic') cache.put(request, response.clone());
        return response;
      });
      if (cached) { event.waitUntil(refresh.catch(() => {})); return cached; }
      return refresh;
    })());
    return;
  }

  if (request.headers.get('Accept')?.includes('text/html')) {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        if (response.ok && response.type === 'basic') {
          const cache = await caches.open(SHELL_CACHE);
          await cache.put(request, response.clone());
        }
        return response;
      } catch (_) {
        const cached = await caches.match(request);
        return cached || await caches.match('/offline');
      }
    })());
  }
});
