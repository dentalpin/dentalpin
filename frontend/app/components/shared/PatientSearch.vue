<script setup lang="ts">
import type { Patient, PaginatedResponse } from '~/types'

const props = defineProps<{
  modelValue?: Patient | null
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [patient: Patient | null]
}>()

const { t } = useI18n()
const api = useApi()

// Search state
const searchQuery = ref('')
const isOpen = ref(false)
const isLoading = ref(false)
const patients = ref<Patient[]>([])
const highlightedIndex = ref(-1)

// Debounce search
let searchTimeout: ReturnType<typeof setTimeout> | null = null

watch(searchQuery, (val) => {
  if (searchTimeout) clearTimeout(searchTimeout)

  if (val.length < 2) {
    patients.value = []
    return
  }

  searchTimeout = setTimeout(async () => {
    await searchPatients(val)
  }, 300)
})

async function searchPatients(query: string) {
  isLoading.value = true
  try {
    const params = new URLSearchParams({
      search: query,
      page: '1',
      page_size: '10'
    })
    const response = await api.get<PaginatedResponse<Patient>>(
      `/api/v1/patients?${params.toString()}`
    )
    patients.value = response.data
  } catch {
    patients.value = []
  } finally {
    isLoading.value = false
  }
}

function selectPatient(patient: Patient) {
  emit('update:modelValue', patient)
  searchQuery.value = `${patient.last_name}, ${patient.first_name}`
  isOpen.value = false
}

function clearSelection() {
  emit('update:modelValue', null)
  searchQuery.value = ''
  patients.value = []
}

// Initialize search query if modelValue is set
watch(() => props.modelValue, (patient) => {
  if (patient) {
    searchQuery.value = `${patient.last_name}, ${patient.first_name}`
  } else {
    searchQuery.value = ''
  }
}, { immediate: true })

function handleFocus() {
  isOpen.value = true
  if (searchQuery.value.length >= 2) {
    searchPatients(searchQuery.value)
  }
}

function handleBlur() {
  // Delay close to allow click on results
  setTimeout(() => {
    isOpen.value = false
    highlightedIndex.value = -1
  }, 200)
}

// Keyboard navigation
function handleKeydown(event: KeyboardEvent) {
  if (!isOpen.value || patients.value.length === 0) {
    return
  }

  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      highlightedIndex.value = Math.min(
        highlightedIndex.value + 1,
        patients.value.length - 1
      )
      break
    case 'ArrowUp':
      event.preventDefault()
      highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0)
      break
    case 'Enter':
      event.preventDefault()
      {
        const highlighted = patients.value[highlightedIndex.value]
        if (highlighted) selectPatient(highlighted)
      }
      break
    case 'Escape':
      event.preventDefault()
      isOpen.value = false
      highlightedIndex.value = -1
      break
  }
}

// Reset highlight when results change
watch(patients, () => {
  highlightedIndex.value = -1
})
</script>

<template>
  <div class="relative">
    <UInput
      v-model="searchQuery"
      :placeholder="placeholder || t('patients.searchPlaceholder')"
      icon="i-lucide-search"
      :loading="isLoading"
      @focus="handleFocus"
      @blur="handleBlur"
      @keydown="handleKeydown"
    >
      <template
        v-if="modelValue"
        #trailing
      >
        <UButton
          variant="ghost"
          color="neutral"
          icon="i-lucide-x"
          :aria-label="t('common.clear')"
          size="xs"
          class="-mr-2"
          @click.stop="clearSelection"
        />
      </template>
    </UInput>

    <!-- Results dropdown -->
    <div
      v-if="isOpen && (patients.length > 0 || isLoading)"
      class="absolute z-50 w-full mt-1 bg-surface border border-default rounded-lg shadow-lg max-h-60 overflow-auto"
    >
      <div
        v-if="isLoading"
        class="p-3 text-center text-subtle"
      >
        <UIcon
          name="i-lucide-loader-2"
          class="w-5 h-5 animate-spin mx-auto"
        />
      </div>

      <div
        v-else-if="patients.length === 0 && searchQuery.length >= 2"
        class="p-3 text-center text-subtle text-sm"
      >
        {{ t('patients.noResults') }}
      </div>

      <div
        v-for="(patient, index) in patients"
        :key="patient.id"
        class="flex items-center gap-3 p-3 cursor-pointer transition-colors"
        :class="index === highlightedIndex
          ? 'bg-[var(--color-primary-soft)]'
          : 'hover:bg-surface-muted'"
        @mousedown.prevent="selectPatient(patient)"
        @mouseenter="highlightedIndex = index"
      >
        <UAvatar
          :alt="patient.first_name"
          size="sm"
        />
        <div class="min-w-0 flex-1">
          <p class="font-medium text-default truncate">
            {{ patient.last_name }}, {{ patient.first_name }}
          </p>
          <p class="text-sm text-muted truncate">
            {{ patient.phone || patient.email || '-' }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
