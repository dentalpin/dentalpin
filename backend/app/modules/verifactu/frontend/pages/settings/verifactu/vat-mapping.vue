<script setup lang="ts">
// AEAT VAT classification mapping.
//
// Lists every VAT type the clinic has in the catalog and lets the
// admin pin its AEAT ``CalificacionOperacion`` / ``OperacionExenta``
// override. When no override is set, the verifactu hook falls back to
// the rate-based heuristic.
import type { VatClassificationItem } from '~/composables/useVerifactu'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

const { t } = useI18n()
const toast = useToast?.()
const { listVatMapping, upsertVatMapping } = useVerifactu()
const { can } = usePermissions()

const canManage = computed(() => can(PERMISSIONS.verifactu.settingsConfigure))

const items = ref<VatClassificationItem[]>([])
const loading = ref(true)
const saving = ref<string | null>(null)

const CLASSIFICATIONS = [
  { value: 'S1', label: 'S1 — Sujeto, no exento (régimen general)' },
  { value: 'S2', label: 'S2 — Sujeto, no exento (inversión sujeto pasivo)' },
  { value: 'E1', label: 'E1 — Exento (art. 20 LIVA — sanitario, financiero…)' },
  { value: 'E2', label: 'E2 — Exento (art. 21 — exportación)' },
  { value: 'E3', label: 'E3 — Exento (art. 22 — operaciones asimiladas a exportación)' },
  { value: 'E4', label: 'E4 — Exento (art. 23-24 — zonas francas, regímenes suspensivos)' },
  { value: 'E5', label: 'E5 — Exento (art. 25 — entregas intracomunitarias)' },
  { value: 'E6', label: 'E6 — Exento (otros)' },
  { value: 'N1', label: 'N1 — No sujeta (art. 7, 14, otros — por reglas localización)' },
  { value: 'N2', label: 'N2 — No sujeta (por reglas de localización)' }
] as const

const AUTO_VALUE = '__auto__'

interface Row {
  data: VatClassificationItem
  selected: string // override classification or AUTO_VALUE
  notes: string
  dirty: boolean
}

const rows = ref<Row[]>([])

function rowFromItem(it: VatClassificationItem): Row {
  return {
    data: it,
    selected: it.override_classification || AUTO_VALUE,
    notes: it.override_notes || '',
    dirty: false
  }
}

async function refresh() {
  loading.value = true
  try {
    items.value = await listVatMapping()
    rows.value = items.value.map(rowFromItem)
  } finally {
    loading.value = false
  }
}

function effectiveClassification(row: Row): string {
  return row.selected === AUTO_VALUE
    ? row.data.inferred_classification
    : row.selected
}

function effectiveSource(row: Row): 'auto' | 'override' {
  return row.selected === AUTO_VALUE ? 'auto' : 'override'
}

function classificationColor(code: string): 'green' | 'amber' | 'gray' {
  if (code.startsWith('S')) return 'green'
  if (code.startsWith('E')) return 'amber'
  return 'gray'
}

async function save(row: Row) {
  if (!canManage.value) return
  saving.value = row.data.vat_type_id
  try {
    if (row.selected === AUTO_VALUE) {
      const updated = await upsertVatMapping(row.data.vat_type_id, {
        classification: null
      })
      row.data = updated
      row.notes = ''
    } else {
      const cause = row.selected.startsWith('E') ? row.selected : null
      const updated = await upsertVatMapping(row.data.vat_type_id, {
        classification: row.selected,
        exemption_cause: cause,
        notes: row.notes || null
      })
      row.data = updated
    }
    row.dirty = false
    toast?.add({ title: t('verifactu.vatMapping.saved'), color: 'green' })
  } catch (e: unknown) {
    toast?.add({ title: errorMessage(e, t('verifactu.vatMapping.saveFailed')), color: 'red' })
  } finally {
    saving.value = null
  }
}

function markDirty(row: Row) {
  row.dirty = true
}

onMounted(refresh)
</script>

<template>
  <div class="p-4 sm:p-6 max-w-5xl mx-auto space-y-6">
    <header>
      <NuxtLink
        to="/settings/verifactu"
        class="text-sm text-gray-500"
      >← Verifactu</NuxtLink>
      <h1 class="text-2xl font-semibold mt-2">
        {{ t('verifactu.vatMapping.title') }}
      </h1>
      <p class="text-sm text-gray-500">
        {{ t('verifactu.vatMapping.subtitle') }}
      </p>
    </header>

    <UAlert
      color="blue"
      variant="soft"
      icon="i-lucide-info"
      :title="t('verifactu.vatMapping.legalIntroTitle')"
      :description="t('verifactu.vatMapping.legalIntro')"
    />

    <USkeleton
      v-if="loading"
      class="h-64 w-full"
    />

    <div
      v-else-if="rows.length === 0"
      class="text-center text-sm text-gray-500 py-12"
    >
      {{ t('verifactu.vatMapping.empty') }}
    </div>

    <UCard v-else>
      <div class="divide-y divide-gray-200 dark:divide-gray-700">
        <div
          v-for="row in rows"
          :key="row.data.vat_type_id"
          class="py-4 grid grid-cols-1 lg:grid-cols-12 gap-3 items-start"
        >
          <!-- Identity -->
          <div class="lg:col-span-3">
            <p class="font-medium">
              {{ row.data.label }}
            </p>
            <p class="text-xs text-gray-500">
              {{ t('verifactu.vatMapping.rate') }}: {{ row.data.rate }}%
              <span
                v-if="row.data.is_default"
                class="ml-1"
              >· {{ t('verifactu.vatMapping.defaultBadge') }}</span>
            </p>
          </div>

          <!-- Effective classification preview -->
          <div class="lg:col-span-2 flex items-center gap-2">
            <UBadge
              :color="classificationColor(effectiveClassification(row))"
              variant="subtle"
            >
              {{ effectiveClassification(row) }}
            </UBadge>
            <span class="text-xs text-gray-500">
              {{ effectiveSource(row) === 'auto'
                ? t('verifactu.vatMapping.sourceAuto')
                : t('verifactu.vatMapping.sourceOverride') }}
            </span>
          </div>

          <!-- Override selector -->
          <div class="lg:col-span-5">
            <USelectMenu
              v-model="row.selected"
              :items="[
                { value: AUTO_VALUE, label: t('verifactu.vatMapping.autoOption', { code: row.data.inferred_classification }) },
                ...CLASSIFICATIONS
              ]"
              value-key="value"
              label-key="label"
              :disabled="!canManage"
              class="w-full"
              @update:model-value="markDirty(row)"
            />
            <UInput
              v-if="row.selected !== AUTO_VALUE && row.selected.startsWith('E')"
              v-model="row.notes"
              :placeholder="t('verifactu.vatMapping.notesPlaceholder')"
              size="xs"
              class="mt-2"
              @update:model-value="markDirty(row)"
            />
          </div>

          <!-- Save button -->
          <div class="lg:col-span-2 flex justify-end">
            <UButton
              v-if="canManage"
              :loading="saving === row.data.vat_type_id"
              :disabled="!row.dirty"
              size="sm"
              variant="soft"
              icon="i-lucide-save"
              @click="save(row)"
            >
              {{ t('verifactu.vatMapping.save') }}
            </UButton>
          </div>
        </div>
      </div>
    </UCard>
  </div>
</template>
