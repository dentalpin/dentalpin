<script setup lang="ts">
/**
 * Diagnosis mode container.
 *
 * Renders the odontogram-owned `DiagnosisMode` as the "Odontograma" tab
 * and exposes the `patient.diagnosis.subtabs` slot so optional modules
 * (periodontogram, future imaging tools) can plug in additional
 * diagnostic surfaces without `patients` importing them.
 *
 * Falls back to the plain `<DiagnosisMode>` when the slot is empty —
 * UI stays identical to the pre-slot world when no optional module is
 * installed. Preserves the uninstall promise.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useModuleSlots } from '~~/app/composables/useModuleSlots'

const props = defineProps<{
  patientId: string
  readonly?: boolean
}>()

const emit = defineEmits<{
  'create-plan': []
  'continue-plan': [planId: string]
}>()

interface DiagnosisSubtabCtx {
  patientId: string
  readonly?: boolean
}

const route = useRoute()
const router = useRouter()
const { resolve } = useModuleSlots()
const { t } = useI18n()

const subtabs = computed(() =>
  resolve<DiagnosisSubtabCtx>('patient.diagnosis.subtabs', {
    patientId: props.patientId,
    readonly: props.readonly
  })
)

const activeKey = ref<string>('odontogram')

const tabItems = computed(() => {
  const items: Array<{ value: string, label: string }> = [
    { value: 'odontogram', label: t('clinical.diagnosis.odontogramTab') }
  ]
  for (const entry of subtabs.value) {
    items.push({
      value: entry.id,
      label: entry.labelKey ? t(entry.labelKey) : entry.id
    })
  }
  return items
})

onMounted(() => {
  const param = route.query.diagnosisView
  if (typeof param === 'string' && tabItems.value.some(i => i.value === param)) {
    activeKey.value = param
  }
})

watch(activeKey, (value) => {
  router.replace({
    query: { ...route.query, diagnosisView: value === 'odontogram' ? undefined : value }
  })
})
</script>

<template>
  <!-- No optional sub-tabs installed: keep the pre-slot UX intact. -->
  <DiagnosisMode
    v-if="subtabs.length === 0"
    :patient-id="patientId"
    :readonly="readonly"
    @create-plan="emit('create-plan')"
    @continue-plan="(planId) => emit('continue-plan', planId)"
  />

  <div
    v-else
    class="space-y-3"
  >
    <UTabs
      v-model="activeKey"
      :items="tabItems"
      :ui="{ root: 'w-full' }"
      class="diagnosis-subtabs"
    />

    <div v-if="activeKey === 'odontogram'">
      <DiagnosisMode
        :patient-id="patientId"
        :readonly="readonly"
        @create-plan="emit('create-plan')"
        @continue-plan="(planId) => emit('continue-plan', planId)"
      />
    </div>

    <template
      v-for="entry in subtabs"
      :key="entry.id"
    >
      <div v-if="activeKey === entry.id">
        <component
          :is="entry.component"
          :patient-id="patientId"
          :readonly="readonly"
        />
      </div>
    </template>
  </div>
</template>
