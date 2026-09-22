const CACHE_VERSION = "plup-v7";
const STATIC_CACHE = `${CACHE_VERSION}-static`;

const STATIC_ASSETS = [
  "./manifest.webmanifest"
];

self.addEventListener("install", event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .catch(() => {})
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();

      await Promise.all(
        keys
          .filter(key => !key.startsWith(CACHE_VERSION))
          .map(key => caches.delete(key))
      );

      await self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;

  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Pentru pagina principală folosim NETWORK FIRST,
  // astfel încât după fiecare deploy Netlify să apară versiunea nouă.
  if (
    request.mode === "navigate" ||
    url.pathname === "/" ||
    url.pathname.endsWith("/index.html")
  ) {
    event.respondWith(
      (async () => {
        try {
          const fresh = await fetch(request, {
            cache: "no-store"
          });

          return fresh;
        } catch (err) {
          const cached = await caches.match("./index.html");

          if (cached) return cached;

          throw err;
        }
      })()
    );

    return;
  }

  // Pentru fișierele locale statice:
  // folosim cache + actualizare în fundal.
  if (url.origin === self.location.origin) {
    event.respondWith(
      (async () => {
        const cached = await caches.match(request);

        const networkPromise = fetch(request)
          .then(async response => {
            if (response && response.ok) {
              const cache = await caches.open(STATIC_CACHE);
              cache.put(request, response.clone());
            }

            return response;
          })
          .catch(() => null);

        return cached || (await networkPromise) || Response.error();
      })()
    );

    return;
  }

  // Pentru resurse externe precum html2canvas / jsPDF:
  // încercăm internetul prima dată.
  event.respondWith(
    (async () => {
      try {
        const fresh = await fetch(request);

        if (fresh && fresh.ok) {
          const cache = await caches.open(STATIC_CACHE);
          cache.put(request, fresh.clone());
        }

        return fresh;
      } catch (err) {
        const cached = await caches.match(request);

        return cached || Response.error();
      }
    })()
  );
});

self.addEventListener("message", event => {
  if (event.data === "SKIP_WAITING") {
    self.skipWaiting();
  }
});
