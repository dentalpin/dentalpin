<script setup lang="ts">
/**
 * Manage treatment categories: create, rename/reorder, deactivate,
 * reactivate. System categories (seeded) are read-only — the backend
 * enforces it, the UI just hides the controls.
 */
import type { TreatmentCatalogCategory } from '~~/app/types'

const open = defineModel<boolean>('open', { default: false })

const { t, locale } = useI18n()
const catalog = useCatalog()

const showInactive = ref(false)
const isSaving = ref(false)

// New category form
const newName = ref('')
const newOrder = ref(0)

// Inline edit
const editingId = ref<string | null>(null)
const editName = ref('')
const editOrder = ref(0)

// Confirm deactivate
const toDelete = ref<TreatmentCatalogCategory | null>(null)

// Load every category (incl. inactive) while the modal is open; restore the
// active-only list the page relies on when it closes.
watch(open, async (isOpen) => {
  if (isOpen) {
    await catalog.fetchCategories(true)
    newOrder.value = nextOrder()
  } else {
    editingId.value = null
    toDelete.value = null
    await catalog.fetchCategories()
  }
})

const sorted = computed(() =>
  [...catalog.categories.value].sort((a, b) => a.display_order - b.display_order)
)
const activeList = computed(() => sorted.value.filter(c => c.is_active))
const inactiveList = computed(() => sorted.value.filter(c => !c.is_active))

function nextOrder(): number {
  return sorted.value.reduce((max, c) => Math.max(max, c.display_order), 0) + 10
}

// ponytail: latin-only slug; a clinic naming categories in Tamil gets "cat-<n>",
// which is still a valid unique key. Add a transliterator if keys ever surface.
function slugify(name: string): string {
  const slug = name
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
    .slice(0, 50)
  return slug || `cat-${catalog.categories.value.length + 1}`
}

async function handleCreate() {
  const name = newName.value.trim()
  if (!name) return
  isSaving.value = true
  const created = await catalog.createCategory({
    key: slugify(name),
    names: { [locale.value]: name },
    display_order: newOrder.value
  })
  isSaving.value = false
  if (created) {
    newName.value = ''
    await catalog.fetchCategories(true)
    newOrder.value = nextOrder()
  }
}

function startEdit(category: TreatmentCatalogCategory) {
  editingId.value = category.id
  editName.value = catalog.getCategoryName(category)
  editOrder.value = category.display_order
}

async function handleUpdate(category: TreatmentCatalogCategory) {
  const name = editName.value.trim()
  if (!name) return
  isSaving.value = true
  const updated = await catalog.updateCategory(category.id, {
    names: { ...category.names, [locale.value]: name },
    display_order: editOrder.value
  })
  isSaving.value = false
  if (updated) {
    editingId.value = null
    await catalog.fetchCategories(true)
  }
}

async function handleDeactivate() {
  if (!toDelete.value) return
  isSaving.value = true
  const ok = await catalog.deleteCategory(toDelete.value.id)
  isSaving.value = false
  if (ok) {
    toDelete.value = null
    await catalog.fetchCategories(true)
  }
}

async function handleReactivate(category: TreatmentCatalogCategory) {
  isSaving.value = true
  const updated = await catalog.updateCategory(category.id, { is_active: true })
  isSaving.value = false
  if (updated) await catalog.fetchCategories(true)
}
</script>

<template>
  <UModal
    v-model:open="open"
    :ui="{ content: 'sm:max-w-2xl' }"
  >
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-tags"
                class="w-5 h-5 text-primary-accent"
              />
              <h3 class="font-semibold text-default">
                {{ t('catalog.manageCategories') }}
              </h3>
            </div>
            <UButton
              variant="ghost"
              icon="i-lucide-x"
              :aria-label="t('common.close')"
              size="sm"
              @click="open = false"
            />
          </div>
        </template>

        <div class="space-y-4">
          <!-- New category -->
          <form
            class="flex flex-col sm:flex-row gap-2 sm:items-end"
            @submit.prevent="handleCreate"
          >
            <UFormField
              :label="t('catalog.newCategory')"
              class="flex-1"
            >
              <UInput
                v-model="newName"
                :placeholder="t('catalog.categoryNamePlaceholder')"
                required
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('catalog.categoryOrder')"
              class="w-full sm:w-24"
            >
              <UInput
                v-model.number="newOrder"
                type="number"
                min="0"
                class="w-full"
              />
            </UFormField>
            <UButton
              type="submit"
              icon="i-lucide-plus"
              :loading="isSaving"
              :disabled="!newName.trim()"
              class="min-h-11 sm:min-h-0"
            >
              {{ t('common.add') }}
            </UButton>
          </form>

          <!-- Empty -->
          <p
            v-if="activeList.length === 0"
            class="text-center py-6 text-muted"
          >
            {{ t('catalog.noCategories') }}
          </p>

          <!-- Active list -->
          <ul
            v-else
            class="divide-y divide-[var(--color-border-subtle)] border border-default rounded-lg"
          >
            <li
              v-for="category in activeList"
              :key="category.id"
              class="flex items-center gap-2 px-3 py-2"
            >
              <!-- Inline edit -->
              <template v-if="editingId === category.id">
                <UInput
                  v-model="editName"
                  class="flex-1"
                  autofocus
                  @keyup.enter="handleUpdate(category)"
                  @keyup.esc="editingId = null"
                />
                <UInput
                  v-model.number="editOrder"
                  type="number"
                  min="0"
                  class="w-20"
                />
                <UButton
                  icon="i-lucide-check"
                  :aria-label="t('common.save')"
                  size="sm"
                  :loading="isSaving"
                  :disabled="!editName.trim()"
                  @click="handleUpdate(category)"
                />
                <UButton
                  icon="i-lucide-x"
                  :aria-label="t('common.cancel')"
                  size="sm"
                  variant="ghost"
                  @click="editingId = null"
                />
              </template>

              <!-- Row -->
              <template v-else>
                <span class="w-8 text-caption text-subtle tabular-nums text-right">
                  {{ category.display_order }}
                </span>
                <span class="flex-1 truncate text-default">
                  {{ catalog.getCategoryName(category) }}
                </span>
                <UBadge
                  variant="subtle"
                  color="neutral"
                  class="hidden sm:inline-flex font-mono"
                >
                  {{ category.key }}
                </UBadge>
                <UBadge
                  v-if="category.is_system"
                  variant="subtle"
                  color="neutral"
                  icon="i-lucide-lock"
                >
                  {{ t('catalog.system') }}
                </UBadge>
                <template v-else>
                  <UButton
                    icon="i-lucide-pencil"
                    size="sm"
                    variant="ghost"
                    :aria-label="t('common.edit')"
                    @click="startEdit(category)"
                  />
                  <UButton
                    icon="i-lucide-trash-2"
                    size="sm"
                    variant="ghost"
                    color="error"
                    :aria-label="t('common.delete')"
                    @click="toDelete = category"
                  />
                </template>
              </template>
            </li>
          </ul>

          <!-- Inactive -->
          <div v-if="inactiveList.length > 0">
            <UButton
              variant="link"
              size="xs"
              :icon="showInactive ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
              @click="showInactive = !showInactive"
            >
              {{ t('catalog.inactiveCategories') }} ({{ inactiveList.length }})
            </UButton>
            <ul
              v-if="showInactive"
              class="mt-2 divide-y divide-[var(--color-border-subtle)] border border-default rounded-lg"
            >
              <li
                v-for="category in inactiveList"
                :key="category.id"
                class="flex items-center gap-2 px-3 py-2 text-muted"
              >
                <span class="flex-1 truncate line-through">
                  {{ catalog.getCategoryName(category) }}
                </span>
                <UButton
                  size="sm"
                  variant="ghost"
                  icon="i-lucide-rotate-ccw"
                  :loading="isSaving"
                  @click="handleReactivate(category)"
                >
                  {{ t('catalog.reactivate') }}
                </UButton>
              </li>
            </ul>
          </div>

          <p class="text-caption text-subtle">
            {{ t('catalog.systemCategoryNote') }}
          </p>
        </div>
      </UCard>
    </template>
  </UModal>

  <!-- Deactivate confirmation -->
  <UModal :open="!!toDelete">
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-alert-triangle"
              class="w-5 h-5 text-danger-accent"
            />
            <h3 class="font-semibold text-default">
              {{ toDelete ? catalog.getCategoryName(toDelete) : '' }}
            </h3>
          </div>
        </template>
        <p class="text-muted">
          {{ t('catalog.deleteCategoryConfirm') }}
        </p>
        <div class="flex justify-end gap-2 pt-6">
          <UButton
            variant="ghost"
            @click="toDelete = null"
          >
            {{ t('common.cancel') }}
          </UButton>
          <UButton
            color="error"
            :loading="isSaving"
            @click="handleDeactivate"
          >
            {{ t('common.delete') }}
          </UButton>
        </div>
      </UCard>
    </template>
  </UModal>
</template>
