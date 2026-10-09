/**
 * Registers schedules' settings pages on the host registry. Mounted as
 * cards under ``/settings/workspace`` and as full pages at
 * ``/settings/workspace/<path>`` via the host's dynamic category route.
 *
 * The host is consumed via ``~~`` (frontend root), the same boundary
 * used by the existing slot system. No cross-module import: schedules
 * only depends on the host shell, not on other modules.
 */
import {
  registerGettingStartedRule,
  registerSettingsPage
} from '~~/app/composables/useSettingsRegistry'
import { PERMISSIONS } from '~~/app/config/permissions'
import type { ClinicHours } from '../composables/useClinicHours'

interface HoursOnboardingState { loaded: boolean, alwaysOpen: boolean }

const useHoursOnboardingState = () =>
  useState<HoursOnboardingState>('schedules:onboarding-hours', () => ({ loaded: false, alwaysOpen: false }))

/** True for the legacy 24/7 template (every weekday 00:00–23:59). */
function isAlwaysOpen(hours: ClinicHours): boolean {
  const days = hours.days ?? []
  if (days.length < 7) return false
  return days.every(d => d.shifts.length === 1
    && d.shifts[0]!.start_time.startsWith('00:00')
    && d.shifts[0]!.end_time.startsWith('23:59'))
}

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'clinic-hours',
    category: 'workspace',
    labelKey: 'schedules.settingsCards.clinicHoursTitle',
    descriptionKey: 'schedules.settingsCards.clinicHoursDescription',
    icon: 'i-lucide-building-2',
    permission: PERMISSIONS.schedules.clinicHoursRead,
    component: () => import('../components/settings/ClinicHoursPage.vue'),
    searchKeywords: ['horario', 'clinica', 'hours', 'clinic', 'agenda', 'apertura'],
    order: 20
  })

  registerSettingsPage({
    path: 'professional-schedules',
    category: 'workspace',
    labelKey: 'schedules.settingsCards.professionalHoursTitle',
    descriptionKey: 'schedules.settingsCards.professionalHoursDescription',
    icon: 'i-lucide-user-cog',
    // canAny: dentist/hygienist hold ``own.read``; assistant/receptionist
    // hold the broader ``professional.read``. Admin matches via ``*``.
    permission: [PERMISSIONS.schedules.professionalRead, PERMISSIONS.schedules.professionalOwnRead],
    component: () => import('../components/settings/ProfessionalSchedulesPage.vue'),
    searchKeywords: ['profesional', 'professional', 'doctor', 'dentista', 'horario', 'turnos'],
    order: 30
  })

  // Getting-started: a clinic still on the 24/7 default has not set its
  // real opening hours — the agenda would offer slots around the clock.
  registerGettingStartedRule({
    id: 'clinic-hours',
    labelKey: 'schedules.onboarding.hoursLabel',
    descriptionKey: 'schedules.onboarding.hoursDescription',
    icon: 'i-lucide-clock',
    to: '/settings/workspace/clinic-hours',
    permission: PERMISSIONS.schedules.clinicHoursRead,
    order: 30,
    severity: 'info',
    modal: () => import('../components/settings/ClinicHoursQuickModal.vue'),
    load: async (api) => {
      const state = useHoursOnboardingState()
      const res = await api.get<{ data: ClinicHours }>('/api/v1/schedules/clinic-hours')
      state.value = { loaded: true, alwaysOpen: isAlwaysOpen(res.data) }
    },
    when: () => {
      const s = useHoursOnboardingState().value
      return s.loaded && s.alwaysOpen
    }
  })
})
