<script setup lang="ts">
// Dispatches a tool result to a typed card based on the tool name. Falls
// back to a generic key/value view for tools without a bespoke card.
import type { PatientResult } from './CopilotPatientCard.vue'
import type { AppointmentResult } from './CopilotAppointmentCard.vue'
import type { SlotResult } from './CopilotSlotCard.vue'

const props = defineProps<{ name: string, result: unknown }>()
const { t } = useI18n()
const { money } = useCopilotFormat()

type Obj = Record<string, unknown>

// Tool names arrive namespaced by the registry (e.g. "patients.search_patients").
// Match on the bare tool name after the last dot.
const tool = computed(() => props.name.split('.').pop() ?? props.name)

const obj = computed<Obj>(() =>
  props.result && typeof props.result === 'object' ? (props.result as Obj) : {}
)
const errorCode = computed(() => (typeof obj.value.error === 'string' ? obj.value.error : null))

const patients = computed<PatientResult[]>(() => {
  if (tool.value === 'search_patients') return (obj.value.patients as PatientResult[]) ?? []
  if (tool.value === 'get_patient' && obj.value.id) return [obj.value as unknown as PatientResult]
  return []
})

const appointments = computed<AppointmentResult[]>(() => {
  if (tool.value === 'get_day_overview') return (obj.value.appointments as AppointmentResult[]) ?? []
  if (tool.value === 'get_appointment' && obj.value.id) return [obj.value as unknown as AppointmentResult]
  return []
})

const slots = computed<SlotResult[]>(() => {
  if (tool.value === 'find_free_slots') return (obj.value.free_windows as SlotResult[]) ?? []
  if (tool.value === 'get_availability') return (obj.value.open_windows as SlotResult[]) ?? []
  return []
})

const mode = computed<'error' | 'patients' | 'appointments' | 'slots' | 'generic'>(() => {
  if (errorCode.value) return 'error'
  if (['search_patients', 'get_patient'].includes(tool.value)) return 'patients'
  if (['get_day_overview', 'get_appointment'].includes(tool.value)) return 'appointments'
  if (['find_free_slots', 'get_availability'].includes(tool.value)) return 'slots'
  return 'generic'
})

const MONEY_HINT = /total|collected|invoiced|net|refunded|amount|balance/i

// Shallow flatten of the result for the generic fallback.
const genericRows = computed(() => {
  const currency = typeof obj.value.currency === 'string' ? obj.value.currency : 'EUR'
  const rows: { label: string, value: string }[] = []
  for (const [key, value] of Object.entries(obj.value)) {
    if (value === null || value === undefined || Array.isArray(value) || typeof value === 'object') continue
    let display = String(value)
    if (typeof value === 'number' && MONEY_HINT.test(key)) display = money(value, currency)
    rows.push({ label: key.replace(/_/g, ' '), value: display })
  }
  return rows
})

const genericLists = computed(() => {
  const lists: { label: string, items: string[] }[] = []
  for (const [key, value] of Object.entries(obj.value)) {
    if (!Array.isArray(value) || value.length === 0) continue
    const items = value.slice(0, 8).map((it) => {
      if (it && typeof it === 'object') {
        return Object.values(it as Obj)
          .filter(v => v !== null && typeof v !== 'object')
          .join(' · ')
      }
      return String(it)
    })
    lists.push({ label: key.replace(/_/g, ' '), items })
  }
  return lists
})

const isEmpty = computed(
  () =>
    (mode.value === 'patients' && patients.value.length === 0)
    || (mode.value === 'appointments' && appointments.value.length === 0)
    || (mode.value === 'slots' && slots.value.length === 0)
)
</script>

<template>
  <p
    v-if="mode === 'error'"
    class="px-1 text-xs text-muted"
  >
    {{ errorCode === 'not_found' ? t('copilot.card.notFound') : t('copilot.card.noResults') }}
  </p>

  <p
    v-else-if="isEmpty"
    class="px-1 text-xs text-muted"
  >
    {{ t('copilot.card.noResults') }}
  </p>

  <div
    v-else-if="mode === 'patients'"
    class="space-y-2"
  >
    <CopilotPatientCard
      v-for="p in patients"
      :key="p.id"
      :patient="p"
    />
  </div>

  <div
    v-else-if="mode === 'appointments'"
    class="space-y-2"
  >
    <CopilotAppointmentCard
      v-for="a in appointments"
      :key="a.id"
      :appointment="a"
    />
  </div>

  <CopilotSlotCard
    v-else-if="mode === 'slots'"
    :slots="slots"
  />

  <!-- Generic fallback: scalar rows + shallow lists -->
  <div
    v-else
    class="rounded-lg border border-default bg-elevated p-3 text-xs"
  >
    <dl
      v-if="genericRows.length"
      class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1"
    >
      <template
        v-for="row in genericRows"
        :key="row.label"
      >
        <dt class="capitalize text-muted">
          {{ row.label }}
        </dt>
        <dd class="text-right font-medium tabular-nums">
          {{ row.value }}
        </dd>
      </template>
    </dl>
    <div
      v-for="list in genericLists"
      :key="list.label"
      class="mt-2"
    >
      <p class="mb-1 capitalize text-muted">
        {{ list.label }}
      </p>
      <ul class="space-y-0.5">
        <li
          v-for="(item, i) in list.items"
          :key="i"
          class="truncate"
        >
          {{ item }}
        </li>
      </ul>
    </div>
  </div>
</template>
