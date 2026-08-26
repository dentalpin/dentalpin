<script setup lang="ts">
import type { Patient, PaginatedResponse, ApiResponse } from '~/types'
import { PERMISSIONS } from '~/config/permissions'
import { splitName, normalizePhone } from './patientSelectorUtils'

const props = defineProps<{
  modelValue?: Patient | null
  placeholder?: string
  inModal?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [patient: Patient | null]
}>()

const { t } = useI18n()
const api = useApi()
const { can } = usePermissions()

const canCreate = computed(() => can(PERMISSIONS.patients.write))

type Mode = 'search' | 'create'
const mode = ref<Mode>('search')

const recentPatients = ref<Patient[]>([])
const searchResults = ref<Patient[]>([])
const isSearching = ref(false)
const isLoadingRecent = ref(false)
const selectedPatient = ref<Patient | null>(props.modelValue || null)
const newlyCreatedId = ref<string | null>(null)
const activeSearchQuery = ref('')

const emptyLabel = computed(() =>
  activeSearchQuery.value
    ? t('selector.noMatches')
    : t('selector.noRecentPatients')
)

// Create-mode state.
const form = reactive({
  first_name: '',
  last_name: '',
  phone: ''
})
const firstNameRef = ref<HTMLInputElement | null>(null)
const isSubmitting = ref(false)
const createError = ref<string | null>(null)
const duplicateMatch = ref<Patient | null>(null)
let dupLookupCtrl: AbortController | null = null
let dupLookupTimer: ReturnType<typeof setTimeout> | null = null
let createCtrl: AbortController | null = null

const canSubmit = computed(
  () => form.first_name.trim().length > 0 && form.last_name.trim().length > 0 && !isSubmitting.value
)

const duplicateName = computed(() => {
  const p = duplicateMatch.value
  if (!p) return ''
  return `${p.last_name}, ${p.first_name}`.trim()
})

onMounted(async () => {
  await loadRecentPatients()
})

onBeforeUnmount(() => {
  dupLookupCtrl?.abort()
  createCtrl?.abort()
  if (dupLookupTimer) clearTimeout(dupLookupTimer)
})

async function loadRecentPatients() {
  isLoadingRecent.value = true
  try {
    const response = await api.get<ApiResponse<Patient[]>>(
      '/api/v1/patients/recent?limit=8'
    )
    recentPatients.value = response.data
  } catch {
    recentPatients.value = []
  } finally {
    isLoadingRecent.value = false
  }
}

async function handleSearch(query: string) {
  activeSearchQuery.value = query
  if (!query || query.length < 2) {
    searchResults.value = []
    return
  }

  isSearching.value = true
  try {
    const params = new URLSearchParams({
      search: query,
      page: '1',
      page_size: '10'
    })
    const response = await api.get<PaginatedResponse<Patient>>(
      `/api/v1/patients?${params.toString()}`
    )
    searchResults.value = response.data
  } catch {
    searchResults.value = []
  } finally {
    isSearching.value = false
  }
}

function handleSelect(patient: Patient | null) {
  selectedPatient.value = patient
  emit('update:modelValue', patient)
}

// Sync with parent
watch(() => props.modelValue, (newVal) => {
  selectedPatient.value = newVal || null
})

// --- Create mode --------------------------------------------------------

function enterCreateMode(query: string) {
  const split = splitName(query)
  form.first_name = split.first
  form.last_name = split.last
  form.phone = ''
  createError.value = null
  duplicateMatch.value = null
  mode.value = 'create'
  nextTick(() => firstNameRef.value?.focus())
}

function cancelCreate() {
  mode.value = 'search'
  createError.value = null
  duplicateMatch.value = null
  if (dupLookupTimer) clearTimeout(dupLookupTimer)
  dupLookupCtrl?.abort()
}

// Soft-duplicate phone lookup. Debounce + AbortController so a fast typist
// can't trigger a stampede of requests, and a returning stale response
// can't overwrite the current state.
watch(() => form.phone, (val) => {
  if (dupLookupTimer) clearTimeout(dupLookupTimer)
  dupLookupCtrl?.abort()
  duplicateMatch.value = null

  const normalized = normalizePhone(val)
  if (normalized.length < 6) return

  dupLookupTimer = setTimeout(async () => {
    const ctrl = new AbortController()
    dupLookupCtrl = ctrl
    try {
      const params = new URLSearchParams({
        search: val,
        page: '1',
        page_size: '5'
      })
      const response = await api.get<PaginatedResponse<Patient>>(
        `/api/v1/patients?${params.toString()}`,
        { signal: ctrl.signal }
      )
      if (ctrl.signal.aborted) return
      const match = response.data.find(
        p => p.phone && normalizePhone(p.phone) === normalized
      )
      duplicateMatch.value = match ?? null
    } catch {
      // Network error or aborted: silently leave duplicateMatch null.
    }
  }, 400)
})

function useExisting() {
  if (!duplicateMatch.value) return
  handleSelect(duplicateMatch.value)
  mode.value = 'search'
  duplicateMatch.value = null
}

async function submitCreate() {
  if (!canSubmit.value) return
  isSubmitting.value = true
  createError.value = null
  createCtrl?.abort()
  const ctrl = new AbortController()
  createCtrl = ctrl
  try {
    const payload: Record<string, string> = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim()
    }
    if (form.phone.trim()) payload.phone = form.phone.trim()

    const response = await api.post<ApiResponse<Patient>>(
      '/api/v1/patients',
      payload,
      { signal: ctrl.signal }
    )
    if (ctrl.signal.aborted) return
    const created = response.data
    // Keep recents fresh for the session without a refetch.
    recentPatients.value = [created, ...recentPatients.value.filter(p => p.id !== created.id)].slice(0, 8)
    newlyCreatedId.value = created.id
    handleSelect(created)
    mode.value = 'search'
  } catch (err) {
    if ((err as { name?: string })?.name === 'AbortError') return
    createError.value = t('patientSelector.createForm.errorGeneric')
  } finally {
    if (createCtrl === ctrl) createCtrl = null
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="relative">
    <!-- Selected patient display -->
    <div
      v-if="selectedPatient"
      class="flex items-center gap-3 p-3 bg-surface-muted rounded-lg"
    >
      <UAvatar
        :alt="selectedPatient.first_name"
        size="sm"
      />
      <div class="min-w-0 flex-1">
        <p class="font-medium text-default truncate flex items-center gap-2">
          <span class="truncate">{{ selectedPatient.last_name }}, {{ selectedPatient.first_name }}</span>
          <UBadge
            v-if="newlyCreatedId === selectedPatient.id"
            color="neutral"
            variant="subtle"
            size="xs"
          >
            {{ t('patientSelector.newBadge') }}
          </UBadge>
        </p>
        <p class="text-sm text-muted truncate">
          {{ selectedPatient.phone || selectedPatient.email || '-' }}
        </p>
      </div>
      <UButton
        variant="ghost"
        color="neutral"
        icon="i-lucide-x"
        :aria-label="t('common.clear')"
        size="sm"
        @click="handleSelect(null)"
      />
    </div>

    <!-- Search mode -->
    <VisualSelector
      v-else-if="mode === 'search'"
      :model-value="selectedPatient"
      :initial-items="recentPatients"
      :search-results="searchResults"
      :is-searching="isSearching || isLoadingRecent"
      :placeholder="placeholder || t('patients.searchPlaceholder')"
      :empty-label="emptyLabel"
      :grid-cols="2"
      :in-modal="inModal"
      @update:model-value="handleSelect"
      @search="handleSearch"
      @footer-enter="enterCreateMode"
    >
      <template #item="{ item }">
        <div class="flex items-center gap-2">
          <UAvatar
            :alt="item.first_name"
            size="xs"
          />
          <div class="min-w-0 flex-1">
            <p class="text-sm font-medium text-default truncate">
              {{ item.last_name }}, {{ item.first_name }}
            </p>
            <p class="text-xs text-muted truncate">
              {{ item.phone || item.email || '-' }}
            </p>
          </div>
        </div>
      </template>

      <template
        v-if="canCreate"
        #footer="{ query }"
      >
        <button
          type="button"
          data-testid="patient-selector-create-row"
          class="w-full flex items-center gap-2 px-4 py-3 text-sm font-medium text-[var(--color-primary)] hover:bg-[var(--color-primary-soft)] transition-colors"
          @mousedown.prevent.stop
          @click="enterCreateMode(query)"
        >
          <UIcon
            name="i-lucide-user-plus"
            class="w-4 h-4"
          />
          <span class="truncate">
            {{ query ? t('patientSelector.createOption', { query }) : t('patientSelector.createOptionEmpty') }}
          </span>
        </button>
      </template>
    </VisualSelector>

    <!-- Create mode -->
    <div
      v-else
      data-testid="patient-selector-create-form"
      class="border border-default rounded-lg p-3 space-y-3 bg-surface"
    >
      <header class="flex items-center justify-between">
        <UButton
          variant="ghost"
          color="neutral"
          icon="i-lucide-arrow-left"
          size="sm"
          @click="cancelCreate"
        >
          {{ t('patientSelector.createForm.back') }}
        </UButton>
        <span class="text-sm font-medium text-default">
          {{ t('patientSelector.createForm.title') }}
        </span>
      </header>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <UFormField
          :label="t('patientSelector.createForm.firstName')"
          required
        >
          <UInput
            ref="firstNameRef"
            v-model="form.first_name"
            autocapitalize="words"
            autocomplete="given-name"
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('patientSelector.createForm.lastName')"
          required
        >
          <UInput
            v-model="form.last_name"
            autocapitalize="words"
            autocomplete="family-name"
            class="w-full"
          />
        </UFormField>
      </div>

      <UFormField
        :label="t('patientSelector.createForm.phone')"
        :description="t('patientSelector.createForm.phoneHint')"
      >
        <UInput
          v-model="form.phone"
          inputmode="tel"
          autocomplete="tel"
          class="w-full"
        />
      </UFormField>

      <div
        v-if="duplicateMatch"
        data-testid="patient-selector-duplicate-warning"
        class="flex items-center gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900"
      >
        <UIcon
          name="i-lucide-alert-triangle"
          class="w-4 h-4 shrink-0"
        />
        <span class="flex-1">{{ t('patientSelector.duplicateWarning', { name: duplicateName }) }}</span>
        <UButton
          size="xs"
          variant="soft"
          color="warning"
          @click="useExisting"
        >
          {{ t('patientSelector.useExisting') }}
        </UButton>
      </div>

      <p
        v-if="createError"
        class="text-sm text-red-600"
      >
        {{ createError }}
      </p>

      <div class="flex gap-2 justify-end pt-1">
        <UButton
          variant="ghost"
          color="neutral"
          size="sm"
          @click="cancelCreate"
        >
          {{ t('patientSelector.createForm.cancel') }}
        </UButton>
        <UButton
          data-testid="patient-selector-create-submit"
          size="sm"
          :disabled="!canSubmit"
          :loading="isSubmitting"
          @click="submitCreate"
        >
          {{ t('patientSelector.createForm.submit') }}
        </UButton>
      </div>
    </div>
  </div>
</template>
