<script setup lang="ts">
import type { InvoiceSeries, InvoiceSeriesCreate, InvoiceSeriesUpdate, SeriesResetRequest } from '~~/app/types'

const { t } = useI18n()
const { isAdmin } = usePermissions()
const toast = useToast()
const {
  fetchSeries,
  createSeries,
  updateSeries,
  resetSeriesCounter
} = useInvoices()

// State
const series = ref<InvoiceSeries[]>([])
const isLoading = ref(false)
const showInactive = ref(false)

// Computed: filter by type
const invoiceSeries = computed(() =>
  series.value.filter(s => s.series_type === 'invoice' && (showInactive.value || s.is_active))
)
const creditNoteSeries = computed(() =>
  series.value.filter(s => s.series_type === 'credit_note' && (showInactive.value || s.is_active))
)

// Create modal state
const showCreateModal = ref(false)
const isCreating = ref(false)
const newSeries = ref({
  prefix: '',
  series_type: 'invoice' as 'invoice' | 'credit_note',
  description: '',
  reset_yearly: true,
  is_default: false
})

// Edit modal state
const showEditModal = ref(false)
const isEditing = ref(false)
const editingSeries = ref<InvoiceSeries | null>(null)
const editData = ref({
  prefix: '',
  description: '',
  reset_yearly: true,
  is_default: false,
  is_active: true
})

// Reset modal state
const showResetModal = ref(false)
const isResetting = ref(false)
const resetSeries = ref<InvoiceSeries | null>(null)
const newNumber = ref(1)

// Fetch series on mount
onMounted(async () => {
  await loadSeries()
})

async function loadSeries() {
  isLoading.value = true
  try {
    series.value = await fetchSeries(undefined, !showInactive.value)
  } finally {
    isLoading.value = false
  }
}

// Watch for inactive toggle
watch(showInactive, () => {
  loadSeries()
})

// Preview number format
function getPreview(s: InvoiceSeries): string {
  const year = new Date().getFullYear()
  const nextNumber = s.current_number + 1
  return `${s.prefix}-${year}-${nextNumber}`
}

// Create
function openCreateModal(seriesType: 'invoice' | 'credit_note') {
  newSeries.value = {
    prefix: seriesType === 'invoice' ? 'FAC' : 'RECT',
    series_type: seriesType,
    description: '',
    reset_yearly: true,
    is_default: false
  }
  showCreateModal.value = true
}

async function handleCreate() {
  isCreating.value = true
  try {
    const data: InvoiceSeriesCreate = {
      prefix: newSeries.value.prefix,
      series_type: newSeries.value.series_type,
      description: newSeries.value.description || undefined,
      reset_yearly: newSeries.value.reset_yearly,
      is_default: newSeries.value.is_default
    }
    await createSeries(data)
    showCreateModal.value = false
    toast.add({ title: t('invoiceSeries.created'), color: 'success' })
    await loadSeries()
  } catch (e: unknown) {
    const error = e as { data?: { message?: string } }
    toast.add({ title: error.data?.message || t('common.error'), color: 'error' })
  } finally {
    isCreating.value = false
  }
}

// Edit
function openEditModal(s: InvoiceSeries) {
  editingSeries.value = s
  editData.value = {
    prefix: s.prefix,
    description: s.description || '',
    reset_yearly: s.reset_yearly,
    is_default: s.is_default,
    is_active: s.is_active
  }
  showEditModal.value = true
}

async function handleUpdate() {
  if (!editingSeries.value) return

  isEditing.value = true
  try {
    const data: InvoiceSeriesUpdate = {
      prefix: editData.value.prefix,
      description: editData.value.description || undefined,
      reset_yearly: editData.value.reset_yearly,
      is_default: editData.value.is_default,
      is_active: editData.value.is_active
    }
    await updateSeries(editingSeries.value.id, data)
    showEditModal.value = false
    editingSeries.value = null
    toast.add({ title: t('invoiceSeries.saved'), color: 'success' })
    await loadSeries()
  } catch (e: unknown) {
    const error = e as { data?: { message?: string } }
    toast.add({ title: error.data?.message || t('common.error'), color: 'error' })
  } finally {
    isEditing.value = false
  }
}

// Reset
function openResetModal(s: InvoiceSeries) {
  resetSeries.value = s
  newNumber.value = s.current_number + 1
  showResetModal.value = true
}

async function handleReset() {
  if (!resetSeries.value) return

  isResetting.value = true
  try {
    const data: SeriesResetRequest = {
      new_number: newNumber.value
    }
    await resetSeriesCounter(resetSeries.value.id, data)
    showResetModal.value = false
    resetSeries.value = null
    toast.add({ title: t('invoiceSeries.resetSuccess'), color: 'success' })
    await loadSeries()
  } catch (e: unknown) {
    const error = e as { data?: { message?: string } }
    toast.add({ title: error.data?.message || t('common.error'), color: 'error' })
  } finally {
    isResetting.value = false
  }
}

// Series type label
function getSeriesTypeLabel(type: string): string {
  return type === 'invoice' ? t('invoiceSeries.regularInvoices') : t('invoiceSeries.creditNotes')
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header with back button -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-4">
        <NuxtLink to="/settings">
          <UButton
            icon="i-lucide-arrow-left"
            :aria-label="t('common.back')"
            variant="ghost"
            color="neutral"
          />
        </NuxtLink>
        <div>
          <h1 class="text-display text-default">
            {{ t('invoiceSeries.title') }}
          </h1>
          <p class="text-caption text-subtle">
            {{ t('invoiceSeries.description') }}
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <!-- Show inactive toggle -->
        <div class="flex items-center gap-2">
          <USwitch v-model="showInactive" />
          <span class="text-sm text-muted dark:text-subtle">
            {{ t('invoiceSeries.showInactive') }}
          </span>
        </div>
      </div>
    </div>

    <!-- Loading skeleton -->
    <template v-if="isLoading">
      <UCard>
        <USkeleton class="h-20 w-full" />
      </UCard>
      <UCard>
        <USkeleton class="h-20 w-full" />
      </UCard>
    </template>

    <template v-else>
      <!-- Regular Invoices Section -->
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="text-h1 text-default">
              {{ t('invoiceSeries.regularInvoices') }}
            </h2>
            <UButton
              v-if="isAdmin"
              icon="i-lucide-plus"
              size="sm"
              @click="openCreateModal('invoice')"
            >
              {{ t('invoiceSeries.new') }}
            </UButton>
          </div>
        </template>

        <div
          v-if="invoiceSeries.length === 0"
          class="text-center py-6 text-muted"
        >
          {{ t('invoiceSeries.noItems') }}
        </div>

        <div
          v-else
          class="divide-y divide-[var(--color-border-subtle)]"
        >
          <div
            v-for="s in invoiceSeries"
            :key="s.id"
            class="py-4"
          >
            <div class="flex items-center justify-between">
              <div class="flex-1">
                <div class="flex items-center gap-3">
                  <span class="font-mono text-h1 text-default">
                    {{ s.prefix }}-
                  </span>
                  <div class="flex items-center gap-2">
                    <UBadge
                      v-if="s.is_default"
                      color="info"
                      variant="subtle"
                    >
                      {{ t('common.default') }}
                    </UBadge>
                    <UBadge
                      v-if="!s.is_active"
                      color="error"
                      variant="subtle"
                    >
                      {{ t('common.inactive') }}
                    </UBadge>
                    <UBadge
                      v-if="s.reset_yearly"
                      color="neutral"
                      variant="subtle"
                    >
                      {{ t('invoiceSeries.resetYearly') }}
                    </UBadge>
                  </div>
                </div>
                <div class="mt-1 flex items-center gap-4 text-caption text-subtle">
                  <span>{{ t('invoiceSeries.nextNumber') }}: <strong>{{ s.current_number + 1 }}</strong></span>
                  <span>{{ t('invoiceSeries.preview') }}: <code class="font-mono bg-surface-muted px-1 rounded">{{ getPreview(s) }}</code></span>
                </div>
                <p
                  v-if="s.description"
                  class="mt-1 text-xs text-subtle"
                >
                  {{ s.description }}
                </p>
              </div>

              <!-- Actions -->
              <div
                v-if="isAdmin"
                class="flex items-center gap-1"
              >
                <UButton
                  icon="i-lucide-pencil"
                  :aria-label="t('common.edit')"
                  size="xs"
                  variant="ghost"
                  color="neutral"
                  :title="t('common.edit')"
                  @click="openEditModal(s)"
                />
                <UButton
                  icon="i-lucide-rotate-ccw"
                  :aria-label="t('invoiceSeries.resetCounter')"
                  size="xs"
                  variant="ghost"
                  color="neutral"
                  :title="t('invoiceSeries.resetCounter')"
                  @click="openResetModal(s)"
                />
              </div>
            </div>
          </div>
        </div>
      </UCard>

      <!-- Credit Notes Section -->
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="text-h1 text-default">
              {{ t('invoiceSeries.creditNotes') }}
            </h2>
            <UButton
              v-if="isAdmin"
              icon="i-lucide-plus"
              size="sm"
              @click="openCreateModal('credit_note')"
            >
              {{ t('invoiceSeries.new') }}
            </UButton>
          </div>
        </template>

        <div
          v-if="creditNoteSeries.length === 0"
          class="text-center py-6 text-muted"
        >
          {{ t('invoiceSeries.noItems') }}
        </div>

        <div
          v-else
          class="divide-y divide-[var(--color-border-subtle)]"
        >
          <div
            v-for="s in creditNoteSeries"
            :key="s.id"
            class="py-4"
          >
            <div class="flex items-center justify-between">
              <div class="flex-1">
                <div class="flex items-center gap-3">
                  <span class="font-mono text-h1 text-default">
                    {{ s.prefix }}-
                  </span>
                  <div class="flex items-center gap-2">
                    <UBadge
                      v-if="s.is_default"
                      color="info"
                      variant="subtle"
                    >
                      {{ t('common.default') }}
                    </UBadge>
                    <UBadge
                      v-if="!s.is_active"
                      color="error"
                      variant="subtle"
                    >
                      {{ t('common.inactive') }}
                    </UBadge>
                    <UBadge
                      v-if="s.reset_yearly"
                      color="neutral"
                      variant="subtle"
                    >
                      {{ t('invoiceSeries.resetYearly') }}
                    </UBadge>
                  </div>
                </div>
                <div class="mt-1 flex items-center gap-4 text-caption text-subtle">
                  <span>{{ t('invoiceSeries.nextNumber') }}: <strong>{{ s.current_number + 1 }}</strong></span>
                  <span>{{ t('invoiceSeries.preview') }}: <code class="font-mono bg-surface-muted px-1 rounded">{{ getPreview(s) }}</code></span>
                </div>
                <p
                  v-if="s.description"
                  class="mt-1 text-xs text-subtle"
                >
                  {{ s.description }}
                </p>
              </div>

              <!-- Actions -->
              <div
                v-if="isAdmin"
                class="flex items-center gap-1"
              >
                <UButton
                  icon="i-lucide-pencil"
                  :aria-label="t('common.edit')"
                  size="xs"
                  variant="ghost"
                  color="neutral"
                  :title="t('common.edit')"
                  @click="openEditModal(s)"
                />
                <UButton
                  icon="i-lucide-rotate-ccw"
                  :aria-label="t('invoiceSeries.resetCounter')"
                  size="xs"
                  variant="ghost"
                  color="neutral"
                  :title="t('invoiceSeries.resetCounter')"
                  @click="openResetModal(s)"
                />
              </div>
            </div>
          </div>
        </div>
      </UCard>
    </template>

    <!-- Create Modal -->
    <UModal v-model:open="showCreateModal">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-plus"
                class="w-5 h-5 text-primary-accent"
              />
              <h3 class="font-semibold text-default">
                {{ t('invoiceSeries.newTitle', { type: getSeriesTypeLabel(newSeries.series_type) }) }}
              </h3>
            </div>
          </template>

          <form
            class="space-y-4"
            @submit.prevent="handleCreate"
          >
            <UFormField :label="t('invoiceSeries.prefix')">
              <UInput
                v-model="newSeries.prefix"
                required
                :placeholder="newSeries.series_type === 'invoice' ? 'FAC' : 'RECT'"
                class="font-mono"
              />
              <template #hint>
                <span class="text-xs">{{ t('invoiceSeries.prefixHint') }}</span>
              </template>
            </UFormField>

            <UFormField :label="t('invoiceSeries.descriptionLabel')">
              <UInput
                v-model="newSeries.description"
                :placeholder="t('invoiceSeries.descriptionPlaceholder')"
              />
            </UFormField>

            <div class="flex items-center gap-3">
              <USwitch v-model="newSeries.reset_yearly" />
              <span class="text-sm text-muted">
                {{ t('invoiceSeries.resetYearlyLabel') }}
              </span>
            </div>

            <div class="flex items-center gap-3">
              <USwitch v-model="newSeries.is_default" />
              <span class="text-sm text-muted">
                {{ t('invoiceSeries.setAsDefault') }}
              </span>
            </div>

            <div class="flex justify-end gap-2 pt-4">
              <UButton
                variant="ghost"
                @click="showCreateModal = false"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                type="submit"
                :loading="isCreating"
              >
                {{ t('common.save') }}
              </UButton>
            </div>
          </form>
        </UCard>
      </template>
    </UModal>

    <!-- Edit Modal -->
    <UModal v-model:open="showEditModal">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-pencil"
                class="w-5 h-5 text-primary-accent"
              />
              <h3 class="font-semibold text-default">
                {{ t('invoiceSeries.editTitle') }}
              </h3>
            </div>
          </template>

          <form
            class="space-y-4"
            @submit.prevent="handleUpdate"
          >
            <UFormField :label="t('invoiceSeries.prefix')">
              <UInput
                v-model="editData.prefix"
                required
                class="font-mono"
              />
            </UFormField>

            <UFormField :label="t('invoiceSeries.descriptionLabel')">
              <UInput
                v-model="editData.description"
                :placeholder="t('invoiceSeries.descriptionPlaceholder')"
              />
            </UFormField>

            <div class="flex items-center gap-3">
              <USwitch v-model="editData.reset_yearly" />
              <span class="text-sm text-muted">
                {{ t('invoiceSeries.resetYearlyLabel') }}
              </span>
            </div>

            <div class="flex items-center gap-3">
              <USwitch v-model="editData.is_default" />
              <span class="text-sm text-muted">
                {{ t('invoiceSeries.setAsDefault') }}
              </span>
            </div>

            <div class="flex items-center gap-3">
              <USwitch v-model="editData.is_active" />
              <span class="text-sm text-muted">
                {{ t('invoiceSeries.activeLabel') }}
              </span>
            </div>

            <div class="flex justify-end gap-2 pt-4">
              <UButton
                variant="ghost"
                @click="showEditModal = false"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                type="submit"
                :loading="isEditing"
              >
                {{ t('common.save') }}
              </UButton>
            </div>
          </form>
        </UCard>
      </template>
    </UModal>

    <!-- Reset Counter Modal -->
    <UModal v-model:open="showResetModal">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-rotate-ccw"
                class="w-5 h-5 text-warning-accent"
              />
              <h3 class="font-semibold text-default">
                {{ t('invoiceSeries.resetCounter') }}
              </h3>
            </div>
          </template>

          <div class="space-y-4">
            <div class="p-3 bg-surface-muted rounded-lg">
              <p class="text-sm text-muted dark:text-subtle">
                {{ t('invoiceSeries.currentNumber') }}:
                <strong class="text-default font-mono">{{ resetSeries?.current_number }}</strong>
              </p>
              <p class="text-sm text-muted dark:text-subtle">
                {{ t('invoiceSeries.seriesPrefix') }}:
                <strong class="text-default font-mono">{{ resetSeries?.prefix }}</strong>
              </p>
            </div>

            <UFormField :label="t('invoiceSeries.newNumber')">
              <UInput
                v-model.number="newNumber"
                type="number"
                :min="1"
                required
                class="font-mono"
              />
              <template #hint>
                <span class="text-xs">{{ t('invoiceSeries.newNumberHint') }}</span>
              </template>
            </UFormField>

            <UAlert
              color="warning"
              variant="subtle"
              icon="i-lucide-alert-triangle"
              :title="t('invoiceSeries.resetWarningTitle')"
              :description="t('invoiceSeries.resetWarning')"
            />

            <div class="flex justify-end gap-2 pt-4">
              <UButton
                variant="ghost"
                @click="showResetModal = false"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                color="warning"
                :loading="isResetting"
                @click="handleReset"
              >
                {{ t('invoiceSeries.confirmReset') }}
              </UButton>
            </div>
          </div>
        </UCard>
      </template>
    </UModal>
  </div>
</template>
