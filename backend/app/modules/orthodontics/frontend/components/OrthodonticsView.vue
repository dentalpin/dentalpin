<script setup lang="ts">
/**
 * Orthodontics sub-tab (patient clinical area, Diagnosis mode):
 * patient cases, new-case sheet, selected case sheet.
 */
import type { OrthoCase } from '../composables/useOrthodontics'
import { PERMISSIONS } from '~~/app/config/permissions'
import OrthoCaseSheet from './OrthoCaseSheet.vue'

const props = defineProps<{ patientId: string }>()

const { t } = useI18n()
const { can } = usePermissions()
const { listCases, createCase } = useOrthodontics()

const canWrite = computed(() => can(PERMISSIONS.orthodontics.casesWrite))

const cases = ref<OrthoCase[]>([])
const selectedId = ref<string | null>(null)
const showNew = ref(false)
const appliance = ref('brackets_metal')
const months = ref<number | null>(null)
const notes = ref('')

async function refresh() {
  cases.value = await listCases({ patient_id: props.patientId })
  const first = cases.value[0]
  if (!selectedId.value && first) selectedId.value = first.id
}

async function save() {
  const created = await createCase({
    patient_id: props.patientId,
    appliance_type: appliance.value,
    estimated_months: months.value,
    diagnosis_notes: notes.value || null
  })
  showNew.value = false
  appliance.value = 'brackets_metal'
  months.value = null
  notes.value = ''
  await refresh()
  selectedId.value = created.id
}

watch(() => props.patientId, () => {
  selectedId.value = null
  refresh()
}, { immediate: true })
</script>

<template>
  <div>
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <USelect
        v-if="cases.length > 0"
        :model-value="selectedId"
        :options="cases.map(c => ({ label: `${t(`orthodontics.appliance.${c.appliance_type}`)} · ${c.start_date}`, value: c.id }))"
          @update:model-value="selectedId = ($event as string | undefined) ?? null"
      />
      <UButton
        v-if="canWrite"
        size="sm"
        icon="i-lucide-plus"
        @click="showNew = true"
      >
        {{ t('orthodontics.case.new') }}
      </UButton>
    </div>

    <OrthoCaseSheet
      v-if="selectedId"
      :key="selectedId"
      :case-id="selectedId"
    />
    <p
      v-else
      class="text-sm text-gray-500"
    >
      {{ t('orthodontics.control.empty') }}
    </p>

    <UModal
      v-model:open="showNew"
      :title="t('orthodontics.case.new')"
    >
      <template #body>
        <div class="space-y-3">
          <div>
            <div class="mb-1 text-sm font-medium">
              {{ t('orthodontics.case.appliance') }}
            </div>
            <div class="flex flex-wrap gap-1">
              <UButton
                v-for="a in ['brackets_metal', 'brackets_esthetic', 'self_ligating', 'aligners', 'functional', 'retention']"
                :key="a"
                size="sm"
                :variant="appliance === a ? 'solid' : 'soft'"
                @click="appliance = a"
              >
                {{ t(`orthodontics.appliance.${a}`) }}
              </UButton>
            </div>
          </div>
          <UInput
            v-model.number="months"
            type="number"
            min="1"
            :placeholder="t('orthodontics.case.estimatedMonths')"
          />
          <UTextarea
            v-model="notes"
            :placeholder="t('orthodontics.case.notes')"
          />
        </div>
      </template>
      <template #footer>
        <UButton @click="save">
          {{ t('orthodontics.case.create') }}
        </UButton>
      </template>
    </UModal>
  </div>
</template>
