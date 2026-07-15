<script setup lang="ts">
/**
 * Top header for the periodontogram chart. Combines:
 *
 * - Status pill (Borrador / Cerrada) + recorded date so the dentist
 *   always knows which session they're looking at.
 * - Autosave indicator — informational, not a button. Surfaces
 *   Guardando / Cambios pendientes / Guardado as a small pill that
 *   updates while the dentist types.
 * - Primary session actions (Cerrar sesión / Descartar borrador) on
 *   the right — only when the snapshot is an editable draft.
 * - The four SEPA indices below, frozen on closed snapshots and
 *   live-computed on drafts.
 *
 * Replaces the former sticky bottom action bar so the periodontogram
 * follows the same "actions live in the top of the card" convention
 * as the rest of the patient file.
 */
import { computed, ref } from 'vue'
import type { PerioIndices, PerioSnapshotSummary } from '../types'

const props = defineProps<{
  indices: PerioIndices | null
  snapshot: PerioSnapshotSummary | null
  saving?: boolean
  dirty?: boolean
}>()

const emit = defineEmits<{
  close: [notes: string | null]
  discard: []
}>()

const { t, locale } = useI18n()

const showClose = ref(false)
const showDiscard = ref(false)
const notes = ref('')

const isDraft = computed(() => props.snapshot?.status === 'draft')

const saveState = computed<'saving' | 'dirty' | 'saved'>(() => {
  if (props.saving) return 'saving'
  if (props.dirty) return 'dirty'
  return 'saved'
})

function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString(locale.value, {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    })
  } catch {
    return iso
  }
}

function confirmClose() {
  emit('close', notes.value.trim() || null)
  showClose.value = false
  notes.value = ''
}

function confirmDiscard() {
  emit('discard')
  showDiscard.value = false
}
</script>

<template>
  <UCard>
    <!-- Row 1: status + date + autosave state | session actions -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-3">
        <UBadge
          v-if="isDraft"
          color="warning"
          variant="soft"
          icon="i-lucide-pencil"
        >
          {{ t('periodontogram.session.draftBadge') }}
        </UBadge>
        <UBadge
          v-else
          color="success"
          variant="soft"
          icon="i-lucide-lock"
        >
          {{ t('periodontogram.session.closedBadge') }}
        </UBadge>

        <span v-if="snapshot?.closed_at" class="text-sm text-muted">
          {{ t('periodontogram.session.recordedAt', { date: formatDate(snapshot.closed_at) }) }}
        </span>
        <span v-else-if="snapshot?.recorded_at" class="text-sm text-muted">
          {{ t('periodontogram.session.recordedAt', { date: formatDate(snapshot.recorded_at) }) }}
        </span>

        <!-- Autosave indicator. Informational only, styled as a pill so
             the dentist doesn't confuse it with a button. -->
        <span
          v-if="isDraft"
          class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px]"
          :class="{
            'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300': saveState === 'saving',
            'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300': saveState === 'dirty',
            'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300': saveState === 'saved'
          }"
          role="status"
          aria-live="polite"
        >
          <UIcon
            :name="saveState === 'saving'
              ? 'i-lucide-loader-2'
              : saveState === 'dirty'
                ? 'i-lucide-cloud-off'
                : 'i-lucide-cloud-check'"
            :class="{ 'animate-spin': saveState === 'saving' }"
            class="text-xs"
            aria-hidden="true"
          />
          <span v-if="saveState === 'saving'">{{ t('periodontogram.saveState.saving') }}</span>
          <span v-else-if="saveState === 'dirty'">{{ t('periodontogram.saveState.dirty') }}</span>
          <span v-else>{{ t('periodontogram.saveState.saved') }}</span>
        </span>
      </div>

      <!-- Session actions — only on drafts. Cerrar sesión = finalize,
           Descartar borrador = throw away. -->
      <div v-if="isDraft" class="flex items-center gap-2">
        <UButton
          variant="ghost"
          color="error"
          icon="i-lucide-trash-2"
          size="sm"
          @click="showDiscard = true"
        >
          {{ t('periodontogram.session.discardDraft') }}
        </UButton>
        <UButton
          icon="i-lucide-check"
          size="sm"
          color="primary"
          @click="showClose = true"
        >
          {{ t('periodontogram.session.closeSession') }}
        </UButton>
      </div>
    </div>

    <!-- Row 2: SEPA indices -->
    <div
      v-if="indices"
      class="mt-3 grid grid-cols-2 gap-4 border-t border-subtle pt-3 text-sm sm:grid-cols-4"
    >
      <div>
        <div class="text-[10px] uppercase tracking-wide text-muted">
          {{ t('periodontogram.indices.bop') }}
        </div>
        <div class="font-mono text-lg font-semibold tabular-nums">
          {{ indices.bop_pct.toFixed(1) }}%
        </div>
      </div>
      <div>
        <div class="text-[10px] uppercase tracking-wide text-muted">
          {{ t('periodontogram.indices.pi') }}
        </div>
        <div class="font-mono text-lg font-semibold tabular-nums">
          {{ indices.pi_pct.toFixed(1) }}%
        </div>
      </div>
      <div>
        <div class="text-[10px] uppercase tracking-wide text-muted">
          {{ t('periodontogram.indices.calMean') }}
        </div>
        <div class="font-mono text-lg font-semibold tabular-nums">
          {{ indices.cal_mean_mm.toFixed(1) }}mm
        </div>
      </div>
      <div>
        <div class="text-[10px] uppercase tracking-wide text-muted">
          {{ t('periodontogram.indices.deepPockets') }}
        </div>
        <div class="font-mono text-lg font-semibold tabular-nums">
          {{ indices.deep_pockets_count }}
        </div>
      </div>
    </div>

    <!-- Close-session confirmation modal -->
    <UModal
      :open="showClose"
      :title="t('periodontogram.session.closeTitle')"
      @update:open="(v) => { showClose = v }"
    >
      <template #body>
        <div class="space-y-3 p-4">
          <p class="text-sm text-muted">
            {{ t('periodontogram.session.closeDescription') }}
          </p>
          <UFormField :label="t('periodontogram.indicesBanner.noteLabel')">
            <UTextarea
              v-model="notes"
              :rows="3"
              :placeholder="t('periodontogram.indicesBanner.observationsPlaceholder')"
            />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2 p-2">
          <UButton variant="outline" color="neutral" @click="showClose = false">
            {{ t('periodontogram.session.cancel') }}
          </UButton>
          <UButton color="primary" icon="i-lucide-check" @click="confirmClose">
            {{ t('periodontogram.session.closeButton') }}
          </UButton>
        </div>
      </template>
    </UModal>

    <!-- Discard-draft confirmation modal -->
    <UModal
      :open="showDiscard"
      :title="t('periodontogram.session.discardTitle')"
      @update:open="(v) => { showDiscard = v }"
    >
      <template #body>
        <div class="p-4">
          <p class="text-sm text-muted">
            {{ t('periodontogram.session.discardDescription') }}
          </p>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2 p-2">
          <UButton variant="outline" color="neutral" @click="showDiscard = false">
            {{ t('periodontogram.session.cancel') }}
          </UButton>
          <UButton color="error" icon="i-lucide-trash-2" @click="confirmDiscard">
            {{ t('periodontogram.session.discardButton') }}
          </UButton>
        </div>
      </template>
    </UModal>
  </UCard>
</template>
