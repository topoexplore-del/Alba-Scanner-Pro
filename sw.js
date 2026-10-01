// Alba Scanner Pro — service worker
// Estrategia: shell cache-first; datos JSON network-first (siempre lo más
// reciente del repo) con caché de respaldo para uso sin conexión.
const SHELL = 'alba-shell-v1';
const DATA = 'alba-data-v1';
const SHELL_FILES = ['movil.html', 'icon-192.png', 'icon-512.png', 'apple-touch-icon.png', 'manifest.webmanifest'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(SHELL_FILES)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => { e.waitUntil(self.clients.claim()); });

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.endsWith('.json')) {
    // Datos: red primero (tiempo real), caché si no hay conexión
    e.respondWith(
      fetch(e.request).then(r => {
        const copy = r.clone();
        caches.open(DATA).then(c => c.put(url.pathname, copy));
        return r;
      }).catch(() => caches.open(DATA).then(c => c.match(url.pathname)))
    );
  } else if (SHELL_FILES.some(f => url.pathname.endsWith(f))) {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
});
