const CACHE_NAME = 'fgi-v1';
const urlsToCache = ['/', '/index.html', '/data.json', '/manifest.json'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(urlsToCache)));
});

self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(response => {
      // 网络优先策略，但缓存作为后备
      return fetch(e.request).catch(() => response);
    })
  );
});
