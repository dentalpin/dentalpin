/**
 * Screen-pop (issue #64 §3, phase-1 polling flavour): while a user with
 * `telephony.calls.read` is logged in, poll the active-calls endpoint
 * and toast each new ringing call once — non-blocking, never navigates
 * on its own; the action button opens the patient record (or the
 * patient search pre-filtered by the caller's number).
 *
 * The 15s poll only runs while the gateway reports itself configured
 * and active (`GET /telephony/status`, re-checked every 10 minutes) —
 * a clinic that never set up telephony costs one status probe per
 * 10 minutes, not a request every 15 seconds.
 */
import { PERMISSIONS } from '~~/app/config/permissions'

const POLL_MS = 15000
const STATUS_RECHECK_MS = 10 * 60 * 1000
// Ringing calls age out of /calls/active within minutes; the id set only
// needs to outlive that window, not the session.
const SEEN_CAP = 200

export default defineNuxtPlugin((nuxtApp) => {
  const seen = new Set<string>()
  let gatewayActive: boolean | null = null
  let lastStatusCheck = 0
  let timer: ReturnType<typeof setInterval> | undefined

  function remember(id: string) {
    seen.add(id)
    if (seen.size > SEEN_CAP) {
      // Sets iterate in insertion order — drop the oldest half.
      for (const old of Array.from(seen).slice(0, SEEN_CAP / 2)) seen.delete(old)
    }
  }

  async function tick() {
    const { user } = useAuth()
    const { can } = usePermissions()
    if (!user.value || !can(PERMISSIONS.telephony.callsRead)) return

    const api = useApi()
    const now = Date.now()
    if (gatewayActive === null || now - lastStatusCheck > STATUS_RECHECK_MS) {
      lastStatusCheck = now
      try {
        const res = await api.get<{ data: { active: boolean } }>(
          '/api/v1/telephony/status',
          { errorToast: false }
        )
        gatewayActive = res.data.active
      } catch {
        // Unknown state (transient error / module gone) — stay quiet and
        // re-probe at the next status window instead of polling calls.
        gatewayActive = false
      }
    }
    if (!gatewayActive) return

    const toast = useToast()
    const t = (nuxtApp.$i18n as { t: (k: string) => string }).t
    try {
      const res = await api.get<{ data: Array<{
        id: string
        status: string
        direction: string
        from_number: string
        patient_id: string | null
        patient_name: string | null
      }> }>('/api/v1/telephony/calls/active', { errorToast: false })
      for (const call of res.data) {
        // The pop announces incoming calls; an outbound call ringing out
        // from the clinic's own line is not one.
        if (call.status !== 'ringing' || call.direction === 'outbound' || seen.has(call.id)) continue
        remember(call.id)
        toast.add({
          title: call.patient_name || t('telephony.calls.unknownCaller'),
          description: `${t('telephony.pop.incoming')} · ${call.from_number}`,
          icon: 'i-lucide-phone-incoming',
          color: 'warning',
          duration: 20000,
          actions: [{
            label: call.patient_id ? t('telephony.calls.openRecord') : t('telephony.calls.searchPatient'),
            onClick: () => {
              navigateTo(call.patient_id
                ? `/patients/${call.patient_id}`
                : `/patients?phone=${encodeURIComponent(call.from_number)}`)
            }
          }]
        })
      }
    } catch {
      // Background poll — a transient failure must stay invisible.
    }
  }

  if (import.meta.client) {
    timer = setInterval(tick, POLL_MS)
    nuxtApp.hook('app:unmount' as never, (() => {
      if (timer) clearInterval(timer)
    }) as never)
  }
})
