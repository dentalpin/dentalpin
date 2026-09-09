/* DentalPin WebPush service worker (notifications module, T6).
 *
 * Served from the site root as /push-sw.js (push services require a
 * same-origin worker). The patient subscribe page registers it with
 * the /p/push/<token> page as its scope owner.
 */
self.addEventListener('push', (event) => {
  let title = 'DentalPin'
  let body = ''
  try {
    const data = event.data ? event.data.json() : {}
    if (data.title) title = String(data.title)
    if (data.body) body = String(data.body)
  } catch {
    if (event.data) body = event.data.text()
  }
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: '/logo-icon.svg',
      tag: 'dentalpin-reminder'
    })
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) return client.focus()
      }
      if (self.clients.openWindow) return self.clients.openWindow('/')
    })
  )
})
