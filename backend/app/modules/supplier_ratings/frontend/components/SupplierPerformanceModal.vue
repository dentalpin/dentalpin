<script setup lang="ts">
import type { SupplierPerformanceDashboard } from '../composables/useSupplierRatings'

const props = defineProps<{ contactId: string, supplierName: string }>()
const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
const ratingsApi = useSupplierRatings()

const dashboard = ref<SupplierPerformanceDashboard | null>(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await ratingsApi.getDashboard(props.contactId)
    dashboard.value = res.data
  } finally {
    loading.value = false
  }
}
onMounted(load)

const newScore = ref(5)
const newNotes = ref('')
const saving = ref(false)

async function submitRating() {
  saving.value = true
  try {
    await ratingsApi.addRating(props.contactId, newScore.value, newNotes.value || null)
    newNotes.value = ''
    await load()
  } finally {
    saving.value = false
  }
}

function pct(v: number | null | undefined): string {
  return v == null ? '—' : `${v.toFixed(0)}%`
}
</script>

<template>
  <UModal :open="true" @update:open="(v) => !v && emit('close')">
    <template #content>
      <div class="p-4 space-y-4 max-w-xl">
        <h2 class="text-h3 text-default">
          {{ t('supplierRatings.title') }} — {{ supplierName }}
        </h2>

        <div v-if="loading" class="text-caption text-subtle">
          {{ t('common.loading') }}
        </div>

        <div v-else-if="dashboard" class="grid grid-cols-2 gap-3">
          <div class="p-3 rounded-lg bg-elevated">
            <div class="text-caption text-subtle">{{ t('supplierRatings.onTimeDelivery') }}</div>
            <div class="text-h4">{{ pct(dashboard.on_time_delivery_pct) }}</div>
            <div class="text-caption text-subtle">{{ dashboard.completed_order_count }} {{ t('supplierRatings.ordersCompleted') }}</div>
          </div>
          <div class="p-3 rounded-lg bg-elevated">
            <div class="text-caption text-subtle">{{ t('supplierRatings.qualityGoodRate') }}</div>
            <div class="text-h4">{{ pct(dashboard.quality_good_pct) }}</div>
            <div class="text-caption text-subtle">{{ dashboard.total_receipt_lines }} {{ t('supplierRatings.linesReceived') }}</div>
          </div>
          <div class="p-3 rounded-lg bg-elevated">
            <div class="text-caption text-subtle">{{ t('supplierRatings.avgUnitPrice') }}</div>
            <div class="text-h4">{{ dashboard.avg_unit_price ?? '—' }}</div>
          </div>
          <div class="p-3 rounded-lg bg-elevated">
            <div class="text-caption text-subtle">{{ t('supplierRatings.communication') }}</div>
            <div class="text-h4">{{ dashboard.avg_communication_score?.toFixed(1) ?? '—' }} / 5</div>
          </div>
        </div>

        <div class="space-y-2 p-3 rounded-lg border border-default">
          <div class="text-caption font-medium">{{ t('supplierRatings.addRating') }}</div>
          <div class="flex gap-2 items-center">
            <USelect
              v-model="newScore"
              :items="[1,2,3,4,5].map(n => ({ value: n, label: String(n) }))"
              class="w-20"
            />
            <UInput v-model="newNotes" :placeholder="t('supplierRatings.notesPlaceholder')" class="flex-1" />
            <UButton :loading="saving" @click="submitRating">
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>

        <div v-if="dashboard?.ratings.length" class="space-y-1">
          <div class="text-caption font-medium text-subtle">{{ t('supplierRatings.history') }}</div>
          <div v-for="r in dashboard.ratings" :key="r.id" class="text-body-sm flex justify-between">
            <span>{{ r.communication_score }}/5 {{ r.notes ? `— ${r.notes}` : '' }}</span>
            <span class="text-caption text-subtle">{{ r.rated_at.slice(0, 10) }}</span>
          </div>
        </div>

        <div class="flex justify-end">
          <UButton variant="ghost" @click="emit('close')">
            {{ t('actions.close') }}
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>
