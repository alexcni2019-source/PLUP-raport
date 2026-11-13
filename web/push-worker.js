self.addEventListener('push', event => {
  if (!event.data) return;
  const { title, body } = event.data.json();
  event.waitUntil(self.registration.showNotification(title, {
    body,
    icon: '/plup-icon.svg',
    data: { path: '/?view=team' },
  }));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const target = new URL('/?view=team', self.location.origin).href;
  event.waitUntil(clients.openWindow(target));
});
