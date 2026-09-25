<script setup lang="ts">
/**
 * The one back control for settings pages (#469).
 *
 * Every settings screen used to draw its own: some on the left of the
 * header, some on the right, labelled "Back", "Settings" or nothing at
 * all, and all of them returning to the settings root rather than to
 * the category the page belongs to. One component keeps the position,
 * the wording and the destination identical.
 *
 * ``SettingsLayout`` passes ``class="lg:hidden"`` because the settings
 * rail replaces it on wide screens; standalone pages have no rail, so
 * they render it at every width.
 */
interface Props {
  /** Where back goes — the page's own category, not the settings root. */
  to: string
  /** Usually the category name, so the link says where it leads. */
  label?: string
}

defineProps<Props>()

const { t } = useI18n()
</script>

<template>
  <NuxtLink
    :to="to"
    class="inline-flex items-center gap-1 text-caption text-muted hover:text-default"
  >
    <UIcon
      name="i-lucide-arrow-left"
      class="w-4 h-4"
    />
    {{ label ?? t('settings.title') }}
  </NuxtLink>
</template>
