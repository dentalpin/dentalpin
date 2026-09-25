<script setup lang="ts">
/**
 * PrescriptionsCard — recent prescriptions on the patient summary.
 * Links out to the full prescriptions page; no inline editing here.
 */
import type { PatientExtended } from '~~/app/types'
import type { Prescription } from '../../composables/usePrescriptions'

interface Ctx {
  patient: PatientExtended
}

const props = defineProps<{ ctx: Ctx }>()

const { t, locale } = useI18n()
const { listForPatient } = usePrescriptions()

const items = ref<Prescription[]>([])
const isLoading = ref(false)

function formatDate(iso: string | null): string {
  if (!iso) return ''
  return new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium' }).format(new Date(iso))
}

onMounted(async () => {
  isLoading.value = true
  try {
    items.value = (await listForPatient(props.ctx.patient.id)).slice(0, 3)
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-2">
      <h3 class="font-semibold">
        {{ t('prescriptions.title') }}
      </h3>
      <NuxtLink
        :to="`/prescriptions?patient_id=${props.ctx.patient.id}`"
        class="text-sm text-primary"
      >
        {{ t('prescriptions.openAll') }}
      </NuxtLink>
    </div>
    <USkeleton
      v-if="isLoading"
      class="h-6 w-32"
    />
    <p
      v-else-if="items.length === 0"
      class="text-sm text-muted"
    >
      {{ t('prescriptions.emptyHint') }}
    </p>
    <ul
      v-else
      class="space-y-1 text-sm"
    >
      <li
        v-for="rx in items"
        :key="rx.id"
        class="flex justify-between gap-2"
      >
        <span class="truncate">{{ formatDate(rx.issued_at) }} — {{ rx.items.length }} {{ t('prescriptions.items') }}</span>
        <UBadge :color="rx.status === 'issued' ? 'success' : rx.status === 'cancelled' ? 'neutral' : 'warning'">
          {{ t(`prescriptions.status.${rx.status}`) }}
        </UBadge>
      </li>
    </ul>
  </div>
</template>
