<script setup lang="ts">
import type { VatType, VatTypeCreate, VatTypeUpdate } from '~~/app/types'

const { t, locale } = useI18n()
const { isAdmin } = usePermissions()
const {
  vatTypes,
  isLoading,
  activeVatTypes,
  fetchVatTypes,
  createVatType,
  updateVatType,
  deleteVatType,
  getVatTypeName,
  getVatTypeLabel
} = useVatTypes()

// Create modal state
const showCreateModal = ref(false)
const isCreating = ref(false)
const newVatType = ref({
  name: '',
  rate: 0,
  is_default: false
})

// Edit modal state
const showEditModal = ref(false)
const isEditing = ref(false)
const editingVatType = ref<VatType | null>(null)
const editData = ref({
  name: '',
  rate: 0,
  is_default: false,
  is_active: true
})

// Delete modal state
const showDeleteModal = ref(false)
const isDeleting = ref(false)
const vatTypeToDelete = ref<VatType | null>(null)

// Include inactive toggle
const showInactive = ref(false)

// Fetch VAT types on mount
onMounted(() => {
  fetchVatTypes(showInactive.value)
})

// Watch for inactive toggle
watch(showInactive, (value) => {
  fetchVatTypes(value)
})

// Display list based on filter
const displayVatTypes = computed(() =>
  showInactive.value ? vatTypes.value : activeVatTypes.value
)

function openCreateModal() {
  newVatType.value = {
    name: '',
    rate: 0,
    is_default: false
  }
  showCreateModal.value = true
}

async function handleCreate() {
  isCreating.value = true
  const data: VatTypeCreate = {
    names: { [locale.value]: newVatType.value.name },
    rate: newVatType.value.rate,
    is_default: newVatType.value.is_default
  }
  const result = await createVatType(data)
  isCreating.value = false
  if (result) {
    showCreateModal.value = false
  }
}

function openEditModal(vatType: VatType) {
  editingVatType.value = vatType
  editData.value = {
    name: getVatTypeName(vatType),
    rate: vatType.rate,
    is_default: vatType.is_default,
    is_active: vatType.is_active
  }
  showEditModal.value = true
}

async function handleUpdate() {
  if (!editingVatType.value) return

  isEditing.value = true
  const data: VatTypeUpdate = {
    names: { [locale.value]: editData.value.name },
    rate: editData.value.rate,
    is_default: editData.value.is_default,
    is_active: editData.value.is_active
  }

  // System types can only change is_default
  if (editingVatType.value.is_system) {
    delete data.names
    delete data.rate
    delete data.is_active
  }

  const result = await updateVatType(editingVatType.value.id, data)
  isEditing.value = false
  if (result) {
    showEditModal.value = false
    editingVatType.value = null
  }
}

function openDeleteModal(vatType: VatType) {
  vatTypeToDelete.value = vatType
  showDeleteModal.value = true
}

async function handleDelete() {
  if (!vatTypeToDelete.value) return

  isDeleting.value = true
  const result = await deleteVatType(vatTypeToDelete.value.id)
  isDeleting.value = false
  if (result) {
    showDeleteModal.value = false
    vatTypeToDelete.value = null
  }
}

function canDelete(vatType: VatType): boolean {
  return !vatType.is_system && !vatType.is_default
}

function canEdit(_vatType: VatType): boolean {
  // Can always edit to change default status
  return true
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
            {{ t('vatTypes.title') }}
          </h1>
          <p class="text-caption text-subtle">
            {{ t('vatTypes.description') }}
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <!-- Show inactive toggle -->
        <div class="flex items-center gap-2">
          <USwitch v-model="showInactive" />
          <span class="text-sm text-muted dark:text-subtle">
            {{ t('vatTypes.showInactive') }}
          </span>
        </div>

        <!-- Create button -->
        <UButton
          v-if="isAdmin"
          icon="i-lucide-plus"
          @click="openCreateModal"
        >
          {{ t('vatTypes.new') }}
        </UButton>
      </div>
    </div>

    <!-- VAT Types list -->
    <UCard>
      <div
        v-if="isLoading"
        class="space-y-3"
      >
        <USkeleton class="h-12 w-full" />
        <USkeleton class="h-12 w-full" />
        <USkeleton class="h-12 w-full" />
      </div>

      <div
        v-else-if="displayVatTypes.length === 0"
        class="text-center py-8 text-muted"
      >
        {{ t('vatTypes.noItems') }}
      </div>

      <div
        v-else
        class="divide-y divide-[var(--color-border-subtle)]"
      >
        <div
          v-for="vatType in displayVatTypes"
          :key="vatType.id"
          class="flex items-center justify-between py-4"
        >
          <div class="flex items-center gap-4">
            <div>
              <p class="font-medium text-default">
                {{ getVatTypeName(vatType) }}
              </p>
              <p class="text-caption text-subtle">
                {{ vatType.rate }}%
              </p>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <!-- Badges -->
            <UBadge
              v-if="vatType.is_default"
              color="info"
              variant="subtle"
            >
              {{ t('vatTypes.default') }}
            </UBadge>
            <UBadge
              v-if="vatType.is_system"
              color="neutral"
              variant="subtle"
            >
              {{ t('vatTypes.system') }}
            </UBadge>
            <UBadge
              v-if="!vatType.is_active"
              color="error"
              variant="subtle"
            >
              {{ t('common.inactive') }}
            </UBadge>

            <!-- Actions -->
            <UButton
              v-if="isAdmin && canEdit(vatType)"
              icon="i-lucide-pencil"
              :aria-label="t('common.edit')"
              size="xs"
              variant="ghost"
              color="neutral"
              @click="openEditModal(vatType)"
            />
            <UButton
              v-if="isAdmin && canDelete(vatType)"
              icon="i-lucide-trash-2"
              :aria-label="t('common.delete')"
              size="xs"
              variant="ghost"
              color="error"
              @click="openDeleteModal(vatType)"
            />
          </div>
        </div>
      </div>
    </UCard>

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
                {{ t('vatTypes.new') }}
              </h3>
            </div>
          </template>

          <form
            class="space-y-4"
            @submit.prevent="handleCreate"
          >
            <UFormField :label="t('vatTypes.name')">
              <UInput
                v-model="newVatType.name"
                required
                :placeholder="t('vatTypes.namePlaceholder')"
              />
            </UFormField>

            <UFormField :label="t('vatTypes.rate')">
              <UInput
                v-model.number="newVatType.rate"
                type="number"
                step="0.1"
                min="0"
                max="100"
                required
              >
                <template #trailing>
                  %
                </template>
              </UInput>
            </UFormField>

            <div class="flex items-center gap-3">
              <USwitch v-model="newVatType.is_default" />
              <span class="text-sm text-muted">
                {{ t('vatTypes.setAsDefault') }}
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
                {{ t('vatTypes.edit') }}
              </h3>
            </div>
          </template>

          <form
            class="space-y-4"
            @submit.prevent="handleUpdate"
          >
            <UFormField :label="t('vatTypes.name')">
              <UInput
                v-model="editData.name"
                required
                :disabled="editingVatType?.is_system"
                :placeholder="t('vatTypes.namePlaceholder')"
              />
            </UFormField>

            <UFormField :label="t('vatTypes.rate')">
              <UInput
                v-model.number="editData.rate"
                type="number"
                step="0.1"
                min="0"
                max="100"
                required
                :disabled="editingVatType?.is_system"
              >
                <template #trailing>
                  %
                </template>
              </UInput>
            </UFormField>

            <div class="flex items-center gap-3">
              <USwitch v-model="editData.is_default" />
              <span class="text-sm text-muted">
                {{ t('vatTypes.setAsDefault') }}
              </span>
            </div>

            <div
              v-if="!editingVatType?.is_system"
              class="flex items-center gap-3"
            >
              <USwitch v-model="editData.is_active" />
              <span class="text-sm text-muted">
                {{ t('vatTypes.active') }}
              </span>
            </div>

            <p
              v-if="editingVatType?.is_system"
              class="text-caption text-subtle"
            >
              {{ t('vatTypes.systemNote') }}
            </p>

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

    <!-- Delete Confirmation Modal -->
    <UModal v-model:open="showDeleteModal">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-alert-triangle"
                class="w-5 h-5 text-danger-accent"
              />
              <h3 class="font-semibold text-default">
                {{ t('vatTypes.delete') }}
              </h3>
            </div>
          </template>

          <p class="text-muted dark:text-subtle">
            {{ t('vatTypes.deleteConfirm') }}
            <strong class="text-default">
              {{ getVatTypeLabel(vatTypeToDelete!) }}
            </strong>?
          </p>
          <p class="mt-2 text-caption text-subtle">
            {{ t('vatTypes.deleteNote') }}
          </p>

          <div class="flex justify-end gap-2 pt-6">
            <UButton
              variant="ghost"
              @click="showDeleteModal = false"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              color="error"
              :loading="isDeleting"
              @click="handleDelete"
            >
              {{ t('common.delete') }}
            </UButton>
          </div>
        </UCard>
      </template>
    </UModal>
  </div>
</template>
