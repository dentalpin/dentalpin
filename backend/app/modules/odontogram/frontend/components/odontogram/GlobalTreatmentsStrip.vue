<script setup lang="ts">
/**
 * GlobalTreatmentsStrip - shows global_mouth / global_arch treatments as chips
 * under the odontogram chart. Plan items like cleaning, whitening or full-arch
 * splints don't target specific teeth, so they live here rather than on the
 * chart itself.
 *
 * Hover on a chip emits the treatment id, so the parent can highlight the
 * corresponding row in the plan list. Hover on `global_arch` chips also emits
 * the arch so the chart can paint an arch halo.
 */
import type { Treatment } from '~~/app/types'

const props = defineProps<{
  treatments: Treatment[]
  /** Ids of items currently highlighted by the parent (hover linking). */
  highlightedIds?: string[]
}>()

const emit = defineEmits<{
  'treatment-hover': [treatmentId: string | null]
  'arch-hover': [arch: 'upper' | 'lower' | null]
}>()

const { t, locale } = useI18n()

const globals = computed(() =>
  props.treatments.filter(t => t.scope === 'global_mouth' || t.scope === 'global_arch')
)

function labelFor(tr: Treatment): string {
  const name
    = tr.catalog_item?.names?.[locale.value]
      || tr.catalog_item?.names?.es
      || tr.catalog_item?.names?.en
  if (name) {
    if (tr.scope === 'global_arch' && tr.arch) {
      const archLabel = tr.arch === 'upper'
        ? t('odontogram.globals.upperArch')
        : t('odontogram.globals.lowerArch')
      return `${name} · ${archLabel}`
    }
    return name
  }
  // Migrated free-text treatments often arrive without a catalog link
  // (Gesdén TtosMed.IdTto is null when the receptionist typed it
  // free-form). Show the notes as the label so the chip is meaningful
  // instead of repeating the placeholder "migrated" clinical_type.
  if (tr.clinical_type === 'migrated' && tr.notes) {
    const trimmed = tr.notes.trim()
    return trimmed.length > 60 ? `${trimmed.slice(0, 60)}…` : trimmed
  }
  const key = `odontogram.treatments.types.${tr.clinical_type}`
  const translated = t(key)
  return translated === key ? tr.clinical_type : translated
}

function iconFor(tr: Treatment): string {
  if (tr.scope === 'global_arch') return 'i-lucide-layers-2'
  return 'i-lucide-scan-face'
}

function isHighlighted(tr: Treatment): boolean {
  return !!props.highlightedIds?.includes(tr.id)
}

function onEnter(tr: Treatment) {
  emit('treatment-hover', tr.id)
  if (tr.scope === 'global_arch' && tr.arch) {
    emit('arch-hover', tr.arch)
  }
}

function onLeave() {
  emit('treatment-hover', null)
  emit('arch-hover', null)
}
</script>

<template>
  <div
    v-if="globals.length > 0"
    class="global-strip"
    role="list"
    :aria-label="t('odontogram.globals.category')"
  >
    <span class="global-strip-label">
      <UIcon
        name="i-lucide-scan-face"
        class="w-3.5 h-3.5"
      />
      {{ t('odontogram.globals.category') }}
    </span>

    <button
      v-for="tr in globals"
      :key="tr.id"
      type="button"
      class="global-chip"
      :class="{
        'highlighted': isHighlighted(tr),
        'global-chip-existing': tr.status === 'existing',
        'global-chip-planned': tr.status === 'planned'
      }"
      role="listitem"
      @mouseenter="onEnter(tr)"
      @mouseleave="onLeave"
    >
      <UIcon
        :name="iconFor(tr)"
        class="w-3.5 h-3.5"
      />
      <span>{{ labelFor(tr) }}</span>
    </button>
  </div>
</template>

<style scoped>
.global-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  margin-top: 8px;
  background: #F4F4F5;
  border: 1px solid #E4E4E7;
  border-radius: 8px;
}

:root.dark .global-strip {
  background: #27272A;
  border-color: #3F3F46;
}

.global-strip-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 500;
  color: #71717A;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-right: 4px;
}

:root.dark .global-strip-label {
  color: #A1A1AA;
}

.global-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
  color: #3F3F46;
  background: white;
  border: 1px solid #D4D4D8;
  border-radius: 999px;
  cursor: default;
  transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}

.global-chip:hover,
.global-chip.highlighted {
  border-color: #3B82F6;
  background: #EFF6FF;
  color: #1E40AF;
  box-shadow: 0 2px 6px rgba(59, 130, 246, 0.2);
  transform: translateY(-1px);
}

:root.dark .global-chip {
  background: #18181B;
  color: #D4D4D8;
  border-color: #3F3F46;
}

:root.dark .global-chip:hover,
:root.dark .global-chip.highlighted {
  background: rgba(59, 130, 246, 0.15);
  border-color: #3B82F6;
  color: #93C5FD;
}

/* Planned treatments carry a striped accent (same convention as tooth chart). */
.global-chip.global-chip-planned {
  background: repeating-linear-gradient(
    45deg,
    white,
    white 3px,
    #F4F4F5 3px,
    #F4F4F5 6px
  );
}

:root.dark .global-chip.global-chip-planned {
  background: repeating-linear-gradient(
    45deg,
    #18181B,
    #18181B 3px,
    #27272A 3px,
    #27272A 6px
  );
}

.global-chip.global-chip-existing {
  /* Solid background already; no override needed. */
}
</style>
