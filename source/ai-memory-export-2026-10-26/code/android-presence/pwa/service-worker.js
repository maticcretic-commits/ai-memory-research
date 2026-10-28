/* AI Memory PWA service worker.
 * Cache-first app shell for offline opening. Push notifications never
 * carry sensitive payload text: the payload is ignored for display and
 * a fixed, content-free notice is shown instead.
 */
const CACHE_NAME = "ai-memory-pwa-v1";
const APP_SHELL = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.map((key) => {
        return key === CACHE_NAME ? Promise.resolve(false) : caches.delete(key);
      })))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") {
    return; // Chat/API traffic is never cached.
  }
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || url.pathname.endsWith("/chat")) {
    return;
  }
  event.respondWith(
    caches.match(request, { ignoreSearch: true }).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        return response;
      }).catch(() => caches.match("./index.html", { ignoreSearch: true }));
    })
  );
});

self.addEventListener("push", (event) => {
  // Deliberately do not read or display event.data: a push is only a
  // doorbell. The app fetches any real content after the founder opens it.
  event.waitUntil(
    self.registration.showNotification("AI Memory", {
      body: "I have something for you. Tap to open.",
      icon: "./icon-192.png",
      badge: "./icon-192.png",
      tag: "ai-memory-doorbell",
      renotify: true,
      data: { url: "./index.html" }
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "./index.html";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes("index.html") && "focus" in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(target);
      }
      return undefined;
    })
  );
});
