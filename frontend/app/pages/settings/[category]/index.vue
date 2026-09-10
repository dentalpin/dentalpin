<script setup lang="ts">
import type { SettingsCategoryId } from '~/composables/useSettingsRegistry'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const registry = useSettingsRegistry()

const categoryId = computed(() => route.params.category as SettingsCategoryId)
const category = computed(() => registry.findCategory(categoryId.value))

// Unknown category id → 404. We don't redirect because the URL
// might be a legitimate share link with a typo and silently jumping
// to /settings hides the bug.
watchEffect(() => {
  if (!category.value) {
    const known = ['general', 'workspace', 'people', 'clinical', 'billing', 'communications', 'integrations', 'modules', 'account']
    if (!known.includes(categoryId.value)) {
      throw createError({ statusCode: 404, statusMessage: 'Settings category not found' })
    }
  }
})

const visiblePages = computed(() => category.value?.pages ?? [])

const showOnboarding = computed(() => categoryId.value === (registry.firstVisibleCategory()?.id ?? 'general'))
</script>

<template>
  <SettingsLayout
    :active-id="categoryId"
    :title="category ? t(category.labelKey) : t('settings.title')"
    :subtitle="category ? t(category.descriptionKey) : undefined"
    :hide-rail="false"
  >
    <!-- No-access state for known but gated categories -->
    <div
      v-if="!category"
      class="rounded-[var(--radius-lg)] ring-1 ring-[var(--color-border)] bg-(--color-surface) p-8"
    >
      <EmptyState
        icon="i-lucide-lock"
        :title="t('settings.locked.title')"
        :description="t('settings.locked.description')"
      >
        <template #actions>
          <UButton
            variant="soft"
            icon="i-lucide-arrow-left"
            @click="router.push('/settings')"
          >
            {{ t('settings.title') }}
          </UButton>
        </template>
      </EmptyState>
    </div>

    <template v-else>
      <OnboardingChecklist
        v-if="showOnboarding"
        class="mb-6"
      />

      <!-- Mobile: full-screen category nav when on first-visible category landing -->
      <div
        v-if="showOnboarding"
        class="mb-6 lg:hidden"
      >
        <h2 class="text-h2 text-default mb-3">
          {{ t('settings.allCategories') }}
        </h2>
        <SettingsCategoryNav
          :active-id="null"
          :full-width="true"
        />
      </div>

      <!-- Registered pages -->
      <div
        v-if="visiblePages.length > 0"
        class="grid grid-cols-1 md:grid-cols-2 gap-4"
      >
        <SettingsSection
          v-for="page in visiblePages"
          :key="page.path"
          :icon="page.icon"
          :title="t(page.labelKey)"
          :subtitle="page.descriptionKey ? t(page.descriptionKey) : undefined"
          :attention="page.attention?.() === true"
          :to="page.to ?? `/settings/${categoryId}/${page.path}`"
        />
      </div>

      <!-- Module-contributed inline sections, filtered by category -->
      <div class="mt-6 space-y-4">
        <ModuleSlot
          name="settings.sections"
          :ctx="{}"
          :category-filter="categoryId"
        />
      </div>

      <!-- Empty state -->
      <div
        v-if="visiblePages.length === 0"
        class="mt-4"
      >
        <EmptyState
          icon="i-lucide-inbox"
          :title="t('settings.emptyCategory.title')"
          :description="t('settings.emptyCategory.description')"
        />
      </div>
    </template>
  </SettingsLayout>
</template>
