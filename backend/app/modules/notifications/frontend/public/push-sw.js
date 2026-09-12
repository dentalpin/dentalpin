/* DentalPin WebPush service worker (notifications module, T6).
 *
 * Lives in the module layer (backend/app/modules/notifications/frontend/
 * public/) so uninstalling the module drops it from the next build.
 * Served from the site root as /push-sw.js (push services require a
 * same-origin worker). The patient subscribe page registers it with
 * the /p/push/<token> page as its scope owner.
 */
self.addEventListener('push', (event) => {
  let title = 'DentalPin'
  let body = ''
  let url = '/'
  try {
    const data = event.data ? event.data.json() : {}
    if (data.title) title = String(data.title)
    if (data.body) body = String(data.body)
    if (data.url) url = String(data.url)
  } catch {
    if (event.data) body = event.data.text()
  }
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: '/logo-icon.svg',
      tag: 'dentalpin-reminder',
      data: { url }
    })
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  // Patient-appropriate target: the payload URL when the server sent
  // one, else the site root (never the staff login — the worker has
  // no token to open an authenticated page with).
  const url = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) return client.focus()
      }
      if (self.clients.openWindow) return self.clients.openWindow(url)
    })
  )
})
