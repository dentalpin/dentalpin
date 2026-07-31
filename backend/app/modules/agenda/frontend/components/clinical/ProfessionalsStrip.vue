<script setup lang="ts">
import type { ApiResponse } from '~~/app/types'

type ProfessionalState = 'free' | 'in_treatment' | 'on_break' | 'off'

interface StripPill {
  id: string
  first_name: string
  last_name: string
  state: ProfessionalState
  current_appointment_id: string | null
  current_cabinet_id: string | null
}

interface StripResponse {
  date: string
  clinic_id: string
  professionals: StripPill[]
}

interface ProfessionalWithColor {
  id: string
  first_name: string
  last_name: string
  color: string
}

const props = defineProps<{
  currentDate: Date
  professionals: ProfessionalWithColor[]
  /** Optional filter state — if set, highlight the matching pill. */
  filteredId?: string | null
}>()

const emit = defineEmits<{
  'pill-click': [professionalId: string]
}>()

const { t } = useI18n()
const api = useApi()

const pills = ref<StripPill[]>([])
const isLoading = ref(false)

async function load() {
  const year = props.currentDate.getFullYear()
  const month = String(props.currentDate.getMonth() + 1).padStart(2, '0')
  const day = String(props.currentDate.getDate()).padStart(2, '0')
  const dateParam = `${year}-${month}-${day}`
  isLoading.value = true
  try {
    const response = await api.get<ApiResponse<StripResponse>>(
      `/api/v1/agenda/kanban/day?date=${dateParam}`
    )
    pills.value = response.data.professionals
  } catch {
    pills.value = []
  } finally {
    isLoading.value = false
  }
}

watch(() => props.currentDate, () => {
  void load()
}, { immediate: true })

// Re-fetch every 30s to keep the strip reactive without adding a
// websocket.
let pollHandle: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  pollHandle = setInterval(() => {
    if (document.visibilityState === 'visible') void load()
  }, 30_000)
})
onBeforeUnmount(() => {
  if (pollHandle !== null) clearInterval(pollHandle)
})

// Exposed so parents can refresh after user actions (drop, transition).
defineExpose({ refresh: load })

const stateColor: Record<ProfessionalState, string> = {
  free: '#22C55E', // green-500
  in_treatment: '#2563EB', // blue-600
  on_break: '#F59E0B', // amber-500
  off: '#9CA3AF' // gray-400
}

function colorForPill(pill: StripPill): string {
  // When we have a professional-specific colour and the pill is free,
  // prefer that colour so the strip visually matches the rest of the
  // agenda (which colours cards by professional). State still wins for
  // busy / break / off so operational signal isn't lost.
  const prof = props.professionals.find(p => p.id === pill.id)
  if (pill.state === 'free' && prof) return prof.color
  return stateColor[pill.state]
}

function initials(pill: StripPill): string {
  const f = pill.first_name.charAt(0)
  const l = pill.last_name.charAt(0)
  return `${f}${l}`.toUpperCase()
}

function stateLabel(state: ProfessionalState): string {
  return t(`appointments.professionals.state.${state}`)
}

function onPillClick(pill: StripPill) {
  emit('pill-click', pill.id)
}
</script>

<template>
  <div
    v-if="pills.length > 0 || isLoading"
    class="flex flex-wrap items-center gap-2 px-1 py-2 mb-3 border-b border-subtle"
  >
    <span class="text-caption text-subtle mr-2 shrink-0">
      {{ t('appointments.professionals.strip') }}
    </span>
    <button
      v-for="pill in pills"
      :key="pill.id"
      type="button"
      class="group flex items-center gap-2 pl-1 pr-2.5 py-1 rounded-full ring-1 ring-[var(--color-border)] bg-surface transition-all"
      :class="{
        'ring-2 ring-[var(--color-primary)]': filteredId === pill.id,
        'opacity-60': pill.state === 'off'
      }"
      :title="`${pill.first_name} ${pill.last_name} · ${stateLabel(pill.state)}`"
      @click.stop="onPillClick(pill)"
    >
      <span
        class="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
        :style="{ backgroundColor: colorForPill(pill) }"
      >
        {{ initials(pill) }}
      </span>
      <span class="text-ui text-default">
        {{ pill.first_name }}
      </span>
      <span
        class="inline-block w-2 h-2 rounded-full"
        :style="{ backgroundColor: stateColor[pill.state] }"
        :aria-label="stateLabel(pill.state)"
      />
    </button>
  </div>
</template>
