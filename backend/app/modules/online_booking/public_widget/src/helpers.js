export function validClinicId(value) {
  return (
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      value
    ) && value !== '00000000-0000-4000-8000-000000000000'
  )
}

export function safeUrl(value, base) {
  if (!value) return ''
  try {
    const url = new URL(value, base)
    const localHttp
      = url.protocol === 'http:'
        && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    return (url.protocol === 'https:' || localHttp)
      && !url.username
      && !url.password
      ? url.href
      : ''
  } catch {
    return ''
  }
}
