<script setup lang="ts">
/**
 * Slot entry into `appointment.completed.followup` (#207).
 *
 * The `appointment.completed` handler only closes plan items the doctor
 * ticked during the visit (`completed_in_appointment`) — anything left
 * unticked silently stays "pendiente". This prompt lists those leftover
 * linked treatments with checkboxes (all checked by default) and marks
 * them performed through the same gated completion path the plan page
 * uses. It deliberately does NOT emit `done`: the host closes the whole
 * modal on `done`, and the other follow-up actions should stay usable.
 */
import type { ApiResponse, Appointment, AppointmentTreatmentBrief } from '~~/app/types'

const props = defineProps<{
  appointment: { id: string }
}>()

defineEmits<{ done: [] }>()

const { t, locale } = useI18n()
const api = useApi()
const { completeItem } = useTreatmentPlans()

const pendingLinked = ref<AppointmentTreatmentBrief[]>([])
const checked = ref<Record<string, boolean>>({})
const isMarking = ref(false)
const markedCount = ref<number | null>(null)

// The ctx appointment comes from whatever list payload triggered the
// dialog — re-fetch the detail so `treatments` is always present.
onMounted(async () => {
  try {
    const res = await api.get<ApiResponse<Appointment>>(`/api/v1/appointments/${props.appointment.id}`)
    pendingLinked.value = (res.data.treatments ?? []).filter(
      tr => tr.planned_item_id && tr.plan_id
        && tr.planned_item_status === 'pending' && !tr.completed_in_appointment
    )
    checked.value = Object.fromEntries(pendingLinked.value.map(tr => [tr.id, true]))
  } catch {
    pendingLinked.value = []
  }
})

function treatmentName(tr: AppointmentTreatmentBrief): string {
  return tr.names?.[locale.value] || tr.names?.en || tr.internal_code
}

const selectedCount = computed(() => Object.values(checked.value).filter(Boolean).length)

async function markPerformed() {
  isMarking.value = true
  let done = 0
  try {
    for (const tr of pendingLinked.value) {
      if (!checked.value[tr.id] || !tr.plan_id) continue
      const result = await completeItem(tr.plan_id, tr.planned_item_id, {})
      if (result) done += 1
    }
  } finally {
    isMarking.value = false
  }
  markedCount.value = done
  pendingLinked.value = pendingLinked.value.filter(
    tr => !checked.value[tr.id]
  )
}
</script>

<template>
  <div
    v-if="pendingLinked.length > 0 || markedCount !== null"
    class="space-y-3"
  >
    <template v-if="pendingLinked.length > 0">
      <p class="text-default">
        {{ t('treatmentPlans.followup.subtitle') }}
      </p>
      <div class="space-y-1.5">
        <label
          v-for="tr in pendingLinked"
          :key="tr.id"
          class="flex items-center gap-2 text-sm text-default"
        >
          <UCheckbox v-model="checked[tr.id]" />
          <span class="min-w-0 truncate">
            {{ treatmentName(tr) }}
            <span
              v-if="tr.tooth_number"
              class="text-caption text-subtle"
            >#{{ tr.tooth_number }}</span>
          </span>
        </label>
      </div>
      <UButton
        color="primary"
        icon="i-lucide-check-check"
        :loading="isMarking"
        :disabled="selectedCount === 0"
        @click="markPerformed"
      >
        {{ t('treatmentPlans.followup.markPerformed') }}
      </UButton>
    </template>
    <p
      v-else
      class="text-sm text-(--color-success-accent)"
    >
      {{ t('treatmentPlans.followup.marked', { count: markedCount ?? 0 }) }}
    </p>
  </div>
</template>
