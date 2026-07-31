// Low-level SSE over fetch(). EventSource can't send the Authorization
// header (and only does GET), so the copilot chat streams a POST body and
// reads response.body via a ReadableStream reader, parsing `event:`/`data:`
// frames itself.

interface StreamHandlers {
  onEvent: (event: string, data: Record<string, unknown>) => void
  onError?: (message: string) => void
}

function parseFrame(frame: string): { event: string, data: Record<string, unknown> } | null {
  let event = 'message'
  let data = ''
  for (const line of frame.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data += line.slice(5).trim()
  }
  try {
    return { event, data: data ? JSON.parse(data) : {} }
  } catch {
    return null
  }
}

export function useCopilotStream() {
  const config = useRuntimeConfig()
  const { accessToken } = useAuth()

  async function stream(path: string, body: unknown, handlers: StreamHandlers): Promise<void> {
    let res: Response
    try {
      res = await fetch(`${config.public.apiBaseUrl}${path}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken.value}`
        },
        body: JSON.stringify(body)
      })
    } catch (e) {
      handlers.onError?.(String(e))
      return
    }

    if (!res.ok || !res.body) {
      handlers.onError?.(`HTTP ${res.status}`)
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const frame = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        const parsed = parseFrame(frame)
        if (parsed) handlers.onEvent(parsed.event, parsed.data)
      }
    }
  }

  return { stream }
}
