// Service worker minimal : rend l'app installable (PWA) sans mettre en cache
// de pages dynamiques ou de données patients. Chaque requête part sur le
// réseau normalement — pas de mode hors-ligne pour l'instant.

const VERSION = 'psysaas-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request));
});
