// static/service-worker.js - Enhanced version
const CACHE_NAME = 'kuccps-courses-v2';
const STATIC_CACHE = 'kuccps-static-v2';
const urlsToCache = [
  '/',
  '/static/css/styles.css',
  '/static/js/main.js',
  '/static/js/pwa.js',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/offline',
  
  // Cache static templates
  '/static/templates/navbar.html',
  '/static/templates/footer.html',
  
  // Cache common images
  '/static/images/logo.png',
  '/static/images/background.jpg'
];

// Cache API responses
const API_CACHE_NAME = 'kuccps-api-v1';
const apiEndpointsToCache = [
  '/api/pwa/install-status',
  '/api/check-pwa'
];

// Install event - cache static assets
self.addEventListener('install', event => {
  event.waitUntil(
    Promise.all([
      caches.open(STATIC_CACHE)
        .then(cache => {
          console.log('Caching static assets');
          return cache.addAll(urlsToCache);
        }),
      caches.open(API_CACHE_NAME)
        .then(cache => {
          console.log('Caching API endpoints');
          return cache.addAll(apiEndpointsToCache);
        })
    ])
  );
});

// Fetch event - intelligent caching strategy
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Skip non-GET requests
  if (request.method !== 'GET') return;
  
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
  
  // HTML pages - Network First with offline fallback
  if (request.headers.get('Accept').includes('text/html')) {
    event.respondWith(networkFirstWithOfflinePage(request));
    return;
  }
  
  // Default: try cache, then network
  event.respondWith(cacheFirst(request));
});

// Strategies
async function networkFirst(request) {
  try {
    // Try network first
    const networkResponse = await fetch(request);
    
    // Clone and cache the response
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, networkResponse.clone());
    
    return networkResponse;
  } catch (error) {
    // Network failed, try cache
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // If it's an API request and we have no cache, return error
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
    
    // Cache the response for future
    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    // Return offline page for HTML requests
    if (request.headers.get('Accept').includes('text/html')) {
      return caches.match('/offline');
    }
    
    throw error;
  }
}

async function networkFirstWithOfflinePage(request) {
  try {
    const networkResponse = await fetch(request);
    
    // Cache successful responses
    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    // Return cached version if available
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Return offline page
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
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      console.log('Service Worker activated with enhanced caching');
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
});

// Sync functions
async function syncGrades() {
  console.log('Syncing grades...');
  // Implement grade sync logic
}

async function syncBasket() {
  console.log('Syncing basket...');
  // Implement basket sync logic
}
// Add these to urlsToCache array:
urlsToCache.push(
  '/degree',
  '/diploma', 
  '/kmtc',
  '/certificate',
  '/artisan',
  '/ttc',
  '/about',
  '/contact',
  '/user-guide'
);