<script setup lang="ts">
/**
 * CompletionNudgeModal - Wraps plan-item "mark complete" with a clinical note prompt.
 *
 * Lists all clinical-note templates so the clinician picks the one that fits,
 * lets them write a free-form body, and exposes an explicit "Skip note"
 * action that still completes the item but emits an audit event.
 */

import type { NoteTemplate, PlannedTreatmentItem } from '~~/app/types'

const props = defineProps<{
  open: boolean
  item: PlannedTreatmentItem | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'confirm': [payload: { itemId: string, noteBody: string | null }]
  'cancel': []
}>()

const { t } = useI18n()
const { listTemplates } = useClinicalNotes()

const noteBody = ref('')
const templates = ref<NoteTemplate[]>([])

async function refreshTemplates() {
  if (!props.open) return
  templates.value = await listTemplates()
}

function applyTemplate(tpl: NoteTemplate) {
  noteBody.value = tpl.body
}

function handleConfirmWithNote() {
  if (!props.item) return
  const body = noteBody.value.trim()
  emit('confirm', { itemId: props.item.id, noteBody: body || null })
  reset()
}

function handleSkip() {
  if (!props.item) return
  emit('confirm', { itemId: props.item.id, noteBody: null })
  reset()
}

function handleCancel() {
  emit('cancel')
  reset()
}

function reset() {
  noteBody.value = ''
}

watch(
  () => props.open,
  (opened) => {
    if (opened) {
      reset()
      refreshTemplates()
    }
  }
)
</script>

<template>
  <UModal
    :open="open"
    @update:open="(v) => emit('update:open', v)"
  >
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-full bg-[var(--color-success-soft)] flex items-center justify-center">
              <UIcon
                name="i-lucide-check"
                class="w-5 h-5 text-success-accent"
              />
            </div>
            <div>
              <h3 class="text-h2 text-default">
                {{ t('treatmentPlans.completionNudge.title') }}
              </h3>
              <p class="text-sm text-muted mt-1">
                {{ t('treatmentPlans.completionNudge.description') }}
              </p>
            </div>
          </div>
        </template>

        <div class="space-y-3">
          <div
            v-if="templates.length > 0"
            class="flex flex-wrap gap-2"
          >
            <span class="text-caption text-muted self-center">
              {{ t('treatmentPlans.notes.templatePicker') }}:
            </span>
            <UButton
              v-for="tpl in templates"
              :key="tpl.id"
              size="xs"
              variant="ghost"
              @click="applyTemplate(tpl)"
            >
              {{ t(tpl.i18n_key) }}
            </UButton>
          </div>

          <textarea
            v-model="noteBody"
            :rows="10"
            :placeholder="t('treatmentPlans.notes.bodyPlaceholder')"
            class="clinical-note-textarea"
          />
        </div>

        <template #footer>
          <div class="flex items-center justify-between w-full">
            <UButton
              variant="ghost"
              color="neutral"
              @click="handleCancel"
            >
              {{ t('actions.cancel') }}
            </UButton>
            <div class="flex gap-2">
              <UButton
                variant="ghost"
                color="neutral"
                @click="handleSkip"
              >
                {{ t('treatmentPlans.completionNudge.skip') }}
              </UButton>
              <UButton
                color="success"
                icon="i-lucide-check"
                :disabled="!noteBody.trim()"
                @click="handleConfirmWithNote"
              >
                {{ t('treatmentPlans.completionNudge.completeWithNote') }}
              </UButton>
            </div>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>

<style scoped>
.clinical-note-textarea {
  display: block;
  width: 100%;
  min-height: 14rem;
  padding: 0.625rem 0.75rem;
  border: 1px solid var(--ui-border);
  border-radius: var(--ui-radius, 6px);
  background: var(--ui-bg);
  color: var(--ui-text);
  font: inherit;
  line-height: 1.5;
  resize: vertical;
}

.clinical-note-textarea:focus {
  outline: none;
  border-color: var(--ui-primary);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--ui-primary) 25%, transparent);
}
</style>
