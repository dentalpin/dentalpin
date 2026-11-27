<script setup lang="ts">
import type { Cabinet } from '~/types'

const { t } = useI18n()
const clinic = useClinic()
const { isAdmin } = usePermissions()

const showForm = ref(false)
const editing = ref<Cabinet | null>(null)

const showDelete = ref(false)
const isDeleting = ref(false)
const toDelete = ref<Cabinet | null>(null)

function openCreate() {
  editing.value = null
  showForm.value = true
}

function openEdit(cabinet: Cabinet) {
  editing.value = cabinet
  showForm.value = true
}

function openDelete(cabinet: Cabinet) {
  toDelete.value = cabinet
  showDelete.value = true
}

async function handleDelete() {
  if (!toDelete.value) return
  isDeleting.value = true
  const result = await clinic.deleteCabinet(toDelete.value.id)
  isDeleting.value = false
  if (result) {
    showDelete.value = false
    toDelete.value = null
  }
}
</script>

<template>
  <SectionCard
    icon="i-lucide-door-open"
    :title="t('settings.cabinets')"
  >
    <template
      v-if="isAdmin"
      #actions
    >
      <UButton
        icon="i-lucide-plus"
        size="xs"
        variant="ghost"
        @click="openCreate"
      >
        {{ t('settings.addCabinet') }}
      </UButton>
    </template>

    <p class="text-caption text-subtle mb-4">
      {{ t('settings.cabinetsDescription') }}
    </p>

    <div
      v-if="clinic.isLoading.value"
      class="space-y-3"
    >
      <USkeleton class="h-8 w-full" />
      <USkeleton class="h-8 w-full" />
    </div>

    <div v-else>
      <div
        v-if="clinic.cabinets.value.length === 0"
        class="text-muted py-2"
      >
        {{ t('settings.noCabinets') }}
      </div>

      <ul
        v-else
        class="divide-y divide-[var(--color-border-subtle)]"
      >
        <li
          v-for="cabinet in clinic.cabinets.value"
          :key="cabinet.id"
          class="flex items-center justify-between gap-3 py-3 min-h-[44px]"
        >
          <div class="flex items-center gap-3 min-w-0">
            <span
              class="w-3 h-3 rounded-full shrink-0"
              :style="{ backgroundColor: cabinet.color }"
            />
            <span
              class="truncate"
              :class="cabinet.is_active === false ? 'text-muted' : 'text-default'"
            >{{ cabinet.name }}</span>
            <UBadge
              v-if="cabinet.is_active === false"
              color="neutral"
              variant="subtle"
              size="sm"
            >
              {{ t('settings.cabinetInactive') }}
            </UBadge>
          </div>
          <div
            v-if="isAdmin"
            class="flex items-center gap-1 shrink-0"
          >
            <UButton
              icon="i-lucide-pencil"
              size="xs"
              variant="ghost"
              color="neutral"
              :aria-label="t('settings.editCabinet')"
              @click="openEdit(cabinet)"
            />
            <UButton
              icon="i-lucide-trash-2"
              size="xs"
              variant="ghost"
              color="error"
              :aria-label="t('settings.deleteCabinet')"
              @click="openDelete(cabinet)"
            />
          </div>
        </li>
      </ul>
    </div>

    <!-- Create / edit modal -->
    <CabinetFormModal
      v-model:open="showForm"
      :cabinet="editing"
    />

    <!-- Delete modal -->
    <UModal v-model:open="showDelete">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-alert-triangle"
                class="w-5 h-5 text-danger-accent"
              />
              <h3 class="font-semibold text-default">
                {{ t('settings.deleteCabinet') }}
              </h3>
            </div>
          </template>

          <p class="text-muted dark:text-subtle">
            {{ t('settings.deleteCabinetConfirm') }}
            <strong class="text-default">
              {{ toDelete?.name }}
            </strong>?
          </p>
          <p class="mt-2 text-caption text-subtle">
            {{ t('settings.deleteCabinetNote') }}
          </p>

          <div class="flex justify-end gap-2 pt-6">
            <UButton
              variant="ghost"
              @click="showDelete = false"
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
  </SectionCard>
</template>
