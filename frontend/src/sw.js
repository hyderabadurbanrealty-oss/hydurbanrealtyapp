// Kill-switch: this site has no service worker. Unregister any stale worker
// left behind by a previous deployment/tool so it stops intercepting fetches.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => {
  event.waitUntil(
    self.registration.unregister().then(() =>
      self.clients.matchAll({ type: 'window' })
    ).then((clients) => {
      clients.forEach((client) => client.navigate(client.url));
    })
  );
});
