<script setup lang="ts">
import { computed, ref } from 'vue'
import type { RecallReason } from '../composables/useRecalls'

// Slot entry into `odontogram.condition.actions`. Host ctx (per
// `clinical_notes.TreatmentNoteButton`) is
// ``{ treatmentId, toothNumber?, status? }`` — patient_id isn't in
// the ctx, so we fetch it lazily on click via the treatment API.
const props = defineProps<{
  ctx: {
    treatmentId?: string
    toothNumber?: number | null
    status?: string
  }
}>()

const { t } = useI18n()
const api = useApi()

const open = ref(false)
const patientId = ref<string | null>(null)
const treatmentCategoryKey = ref<string | null>(null)

const treatmentId = computed(() => props.ctx?.treatmentId ?? null)

const reason = computed<RecallReason>(() => {
  switch (treatmentCategoryKey.value) {
    case 'preventivo': return 'hygiene'
    case 'ortodoncia': return 'ortho_review'
    case 'cirugia': return 'post_op'
    case 'implantes': return 'implant_review'
    default: return 'treatment_followup'
  }
})

async function onClick() {
  if (!treatmentId.value) return
  // Resolve patient + category key from the treatment row before
  // opening the modal. Done lazily so the slot button itself stays
  // cheap on the diagnosis sidebar.
  try {
    const res = await api.get<{
      data: { patient_id: string, catalog_item?: { category?: { key?: string } } | null }
    }>(`/api/v1/odontogram/treatments/${treatmentId.value}`)
    patientId.value = res.data.patient_id
    treatmentCategoryKey.value = res.data.catalog_item?.category?.key ?? null
    open.value = true
  } catch {
    // Endpoint may not exist on every host; fail silent rather than
    // leaving an obviously broken button.
  }
}
</script>

<template>
  <div v-if="treatmentId">
    <UButton
      icon="i-lucide-bell-plus"
      :aria-label="t('recalls.setRecall')"
      size="xs"
      color="neutral"
      variant="ghost"
      :title="t('recalls.setRecall')"
      @click="onClick"
    />
    <SetRecallModal
      v-if="patientId"
      v-model:open="open"
      :patient-id="patientId"
      :initial-reason="reason"
      :initial-treatment-id="treatmentId"
      :initial-treatment-category-key="treatmentCategoryKey"
    />
  </div>
</template>
