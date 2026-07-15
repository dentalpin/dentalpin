<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import type { RecallSettings } from '../composables/useRecalls'

const { t } = useI18n()
const toast = useToast()
const recallsApi = useRecalls()
const { getCategoryLabel } = useTreatmentCatalog()
const { categories: catalogCategories, getCategoryName, fetchCategories } = useCatalog()

function resolveCategoryName(key: string): string {
  const cat = catalogCategories.value.find(c => c.key === key)
  if (cat) return getCategoryName(cat)
  return t(getCategoryLabel(key))
}

const settings = ref<RecallSettings | null>(null)
const isLoading = ref(false)
const isSaving = ref(false)

const reasons = ['hygiene', 'checkup', 'ortho_review', 'implant_review', 'post_op', 'treatment_followup', 'other'] as const

async function load() {
  isLoading.value = true
  try {
    const res = await recallsApi.getSettings()
    settings.value = res.data
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  load()
  fetchCategories()
})

async function save() {
  if (!settings.value || isSaving.value) return
  isSaving.value = true
  try {
    const res = await recallsApi.updateSettings({
      reason_intervals: settings.value.reason_intervals,
      category_to_reason: settings.value.category_to_reason,
      auto_suggest_on_treatment_completed: settings.value.auto_suggest_on_treatment_completed,
      auto_link_on_appointment_scheduled: settings.value.auto_link_on_appointment_scheduled
    })
    settings.value = res.data
    toast.add({ title: t('recalls.settings.saved'), color: 'success' })
  } catch {
    toast.add({ title: t('common.error'), color: 'error' })
  } finally {
    isSaving.value = false
  }
}

function ensureInterval(reason: string) {
  if (!settings.value) return
  if (typeof settings.value.reason_intervals[reason] !== 'number') {
    settings.value.reason_intervals[reason] = 6
  }
}

watch(settings, () => {
  if (!settings.value) return
  for (const r of reasons) ensureInterval(r)
}, { deep: true })

const categoryRows = computed(() => {
  if (!settings.value) return []
  return Object.entries(settings.value.category_to_reason).map(([key, reason]) => ({ key, reason }))
})

const newCategoryKey = ref('')
const newCategoryReason = ref<string>('hygiene')

function addCategory() {
  if (!settings.value || !newCategoryKey.value) return
  settings.value.category_to_reason = {
    ...settings.value.category_to_reason,
    [newCategoryKey.value]: newCategoryReason.value
  }
  newCategoryKey.value = ''
}

function removeCategory(key: string) {
  if (!settings.value) return
  const next = { ...settings.value.category_to_reason }
  delete next[key]
  settings.value.category_to_reason = next
}
</script>

<template>
  <div class="space-y-4">
    <div>
      <h2 class="text-h2">
        {{ t('recalls.settings.title') }}
      </h2>
      <p class="text-subtle">
        {{ t('recalls.settings.description') }}
      </p>
    </div>

    <USkeleton
      v-if="isLoading || !settings"
      class="h-32 w-full"
    />

    <template v-else>
      <UCard>
        <template #header>
          <h3 class="text-h3">
            {{ t('recalls.settings.intervals') }}
          </h3>
        </template>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <UFormField
            v-for="r in reasons"
            :key="r"
            :label="t(`recalls.reasons.${r}`)"
          >
            <UInput
              v-model.number="settings.reason_intervals[r]"
              type="number"
              min="0"
              max="60"
            />
          </UFormField>
        </div>
      </UCard>

      <UCard>
        <template #header>
          <h3 class="text-h3">
            {{ t('recalls.settings.categoryMap') }}
          </h3>
        </template>
        <ul class="divide-y divide-default">
          <li
            v-for="row in categoryRows"
            :key="row.key"
            class="flex items-center justify-between gap-3 py-2"
          >
            <span class="font-mono text-sm">{{ resolveCategoryName(row.key) }}</span>
            <span class="text-subtle">→</span>
            <span class="flex-1">{{ t(`recalls.reasons.${row.reason}`) }}</span>
            <UButton
              icon="i-lucide-trash-2"
              variant="ghost"
              color="error"
              size="xs"
              @click="removeCategory(row.key)"
            />
          </li>
        </ul>
        <div class="flex gap-2 mt-3">
          <UInput
            v-model="newCategoryKey"
            :placeholder="t('recalls.settings.categoryKeyPlaceholder')"
            class="flex-1"
          />
          <USelectMenu
            v-model="newCategoryReason"
            :items="reasons.map(r => ({ value: r, label: t(`recalls.reasons.${r}`) }))"
            value-key="value"
            label-key="label"
          />
          <UButton
            icon="i-lucide-plus"
            color="primary"
            variant="soft"
            :disabled="!newCategoryKey"
            @click="addCategory"
          />
        </div>
      </UCard>

      <UCard>
        <div class="space-y-3">
          <UFormField :label="t('recalls.settings.autoSuggest')">
            <USwitch v-model="settings.auto_suggest_on_treatment_completed" />
          </UFormField>
          <UFormField :label="t('recalls.settings.autoLink')">
            <USwitch v-model="settings.auto_link_on_appointment_scheduled" />
          </UFormField>
        </div>
      </UCard>

      <div class="flex justify-end">
        <UButton
          color="primary"
          :loading="isSaving"
          @click="save"
        >
          {{ t('recalls.actions.save') }}
        </UButton>
      </div>
    </template>
  </div>
</template>
