<script setup lang="ts">
/**
 * DiagnosisCTA - Contextual call-to-action for treatment plan creation
 *
 * Shows different CTAs based on draft plans state:
 * - No drafts:"Create Plan" button
 * - 1 draft:"Continue Plan {name}" button
 * - N drafts: Dropdown to select which plan to continue
 */

import type { TreatmentPlan } from '~~/app/types'

const props = defineProps<{
  draftPlans: TreatmentPlan[]
}>()

const emit = defineEmits<{
  create: []
  continue: [planId: string]
}>()

const { t } = useI18n()

const selectedDraftId = ref<string>('')

/** The one draft to continue when exactly one exists (narrows for the template). */
const soleDraft = computed(() => (props.draftPlans.length === 1 ? props.draftPlans[0] : undefined))

// Options for dropdown when multiple drafts exist
const draftOptions = computed(() =>
  props.draftPlans.map(plan => ({
    label: plan.title || t('treatmentPlans.untitledPlan'),
    value: plan.id
  }))
)

function handleContinue() {
  if (selectedDraftId.value) {
    emit('continue', selectedDraftId.value)
  }
}
</script>

<template>
  <div class="flex flex-col sm:flex-row gap-2">
      <!-- No drafts: Create new plan -->
      <UButton
        v-if="draftPlans.length === 0"
        color="primary"
        icon="i-lucide-plus"
        size="lg"
        class="w-full sm:flex-1 justify-center"
        @click="emit('create')"
      >
        {{ t('clinical.diagnosis.createPlan') }}
      </UButton>

      <!-- 1 draft: Continue that plan -->
      <UButton
        v-else-if="soleDraft"
        color="primary"
        icon="i-lucide-arrow-right"
        size="lg"
        class="w-full sm:flex-1 justify-center"
        @click="emit('continue', soleDraft.id)"
      >
        {{ t('clinical.diagnosis.continuePlan', { name: soleDraft.title || t('treatmentPlans.untitledPlan') }) }}
      </UButton>

      <!-- N drafts: Dropdown to select -->
      <div
        v-else
        class="flex w-full items-center gap-2"
      >
        <USelectMenu
          v-model="selectedDraftId"
          :items="draftOptions"
          value-key="value"
          label-key="label"
          :placeholder="t('clinical.diagnosis.selectPlan')"
          class="min-w-0 flex-1"
        />
        <UButton
          color="primary"
          icon="i-lucide-arrow-right"
          size="lg"
          :disabled="!selectedDraftId"
          @click="handleContinue"
        >
          {{ t('clinical.diagnosis.continue') }}
        </UButton>
      </div>
  </div>
</template>
