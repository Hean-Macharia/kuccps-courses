// static/service-worker.js - Eligibility Checker PWA
const CACHE_NAME = 'eligibility-checker-v3';
const STATIC_CACHE = 'ec-static-v3';
const API_CACHE_NAME = 'ec-api-v3';

const urlsToCache = [
  '/',
  '/static/css/styles.css',
  '/static/js/main.js',
  '/static/js/pwa.js',
  '/static/js/offline-storage.js',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/offline',

  // Core pages
  '/degree',
  '/diploma',
  '/certificate',
  '/kmtc',
  '/artisan',
  '/ttc',
  '/about',
  '/contact',
  '/user-guide',
  '/news',
  '/guides',
  '/chat',
  '/basket',

  // External short courses (cached as static reference)
  'https://short-courses.onrender.com/'
];

const apiEndpointsToCache = [
  '/api/pwa/install-status',
  '/api/check-pwa',
  '/api/news/latest'
];

// Install event - cache static assets
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    Promise.all([
      caches.open(STATIC_CACHE)
        .then(cache => {
          console.log('[EC SW] Caching static assets');
          return cache.addAll(urlsToCache);
        })
        .catch(err => console.warn('[EC SW] Static cache error:', err)),
      caches.open(API_CACHE_NAME)
        .then(cache => {
          console.log('[EC SW] Caching API endpoints');
          return cache.addAll(apiEndpointsToCache);
        })
        .catch(err => console.warn('[EC SW] API cache error:', err))
    ])
  );
});

// Fetch event - intelligent caching strategy
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') return;

  // Skip chrome-extension and other non-http schemes
  if (!url.protocol.startsWith('http')) return;

  // API requests - Network First, then Cache
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Static assets - Cache First, then Network
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // External short-courses link - Network First
  if (url.hostname === 'short-courses.onrender.com') {
    event.respondWith(networkFirst(request));
    return;
  }

  // HTML pages - Network First with offline fallback
  if (request.headers.get('Accept') && request.headers.get('Accept').includes('text/html')) {
    event.respondWith(networkFirstWithOfflinePage(request));
    return;
  }

  // Default: try cache, then network
  event.respondWith(cacheFirst(request));
});

// Strategies
async function networkFirst(request) {
  try {
    const networkResponse = await fetch(request);

    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }

    return networkResponse;
  } catch (error) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    if (new URL(request.url).pathname.startsWith('/api/')) {
      return new Response(
        JSON.stringify({ error: 'You are offline', offline: true }),
        {
          status: 503,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    throw error;
  }
}

async function cacheFirst(request) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }

  try {
    const networkResponse = await fetch(request);

    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }

    return networkResponse;
  } catch (error) {
    if (request.headers.get('Accept') && request.headers.get('Accept').includes('text/html')) {
      return caches.match('/offline');
    }

    throw error;
  }
}

async function networkFirstWithOfflinePage(request) {
  try {
    const networkResponse = await fetch(request);

    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }

    return networkResponse;
  } catch (error) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    return caches.match('/offline');
  }
}

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME, STATIC_CACHE, API_CACHE_NAME];

  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (!cacheWhitelist.includes(cacheName)) {
            console.log('[EC SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      console.log('[EC SW] Activated with enhanced caching');
      return self.clients.claim();
    })
  );
});

// Background sync for offline actions
self.addEventListener('sync', event => {
  if (event.tag === 'sync-grades') {
    event.waitUntil(syncGrades());
  }
  if (event.tag === 'sync-basket') {
    event.waitUntil(syncBasket());
  }
  if (event.tag === 'sync-payment') {
    event.waitUntil(syncPayment());
  }
});

// Sync functions
async function syncGrades() {
  console.log('[EC SW] Syncing grades...');
}

async function syncBasket() {
  console.log('[EC SW] Syncing basket...');
}

async function syncPayment() {
  console.log('[EC SW] Syncing payment verification...');
}

// Push notification support
self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'Eligibility Checker';
  const options = {
    body: data.body || 'New courses and updates available!',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/icon-72x72.png',
    tag: data.tag || 'general',
    requireInteraction: false,
    data: data.url || '/'
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// Notification click handler
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = event.notification.data || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window' }).then(windowClients => {
      for (const client of windowClients) {
        if (client.url === url && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});