<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { parseDateOnly } from '~~/app/utils/wallClock'

// Slot entry into `patient.summary.actions`. `<ModuleSlot>` passes
// the slot ctx as a single `ctx` prop. Reads `do_not_contact` to
// hide the CTA + show the opt-out banner instead — receptionists
// must never schedule a recall against a patient flagged as
// no-contact.
const props = defineProps<{
  ctx: {
    patient: {
      id: string
      do_not_contact?: boolean
      status?: string
    }
  }
}>()

const { t, locale } = useI18n()
const open = ref(false)

const patient = computed(() => props.ctx?.patient)
const doNotContact = computed(() => patient.value?.do_not_contact === true)
const isArchived = computed(() => patient.value?.status === 'archived')
const canSchedule = computed(
  () => !!patient.value?.id && !doNotContact.value && !isArchived.value
)

// Shared per-patient list — same useState that `RecallSummaryFeed`
// reads, so the page fires one fetch and both surfaces stay in sync.
//
// ``useState`` (inside ``usePatientRecalls``) MUST be called from the
// component setup, never inside a computed — Vue throws "Must be
// called at the top of a setup function" when the lazy computed
// re-evaluates outside the setup pass. The patient id on this page
// is route-bound, so resolving it once at setup is enough.
const initialPatientId = props.ctx?.patient?.id ?? null
const patientRecalls = initialPatientId ? usePatientRecalls(initialPatientId) : null
const nextRecall = computed(() => patientRecalls?.nextActiveRecall.value ?? null)

onMounted(() => {
  patientRecalls?.ensureLoaded()
})

function formatMonth(iso: string): string {
  return new Intl.DateTimeFormat(locale.value, {
    year: 'numeric',
    month: 'long'
  }).format(parseDateOnly(iso))
}

function statusColour(status: string): 'success' | 'info' | 'warning' | 'neutral' {
  switch (status) {
    case 'contacted_scheduled': return 'info'
    case 'pending':
    case 'contacted_no_answer': return 'warning'
    default: return 'neutral'
  }
}

async function onSaved() {
  // Refresh the shared list so the inline card + summary feed both
  // pick up the new / updated recall without a page reload.
  await patientRecalls?.refresh()
}
</script>

<template>
  <div v-if="patient?.id">
    <!-- Opt-out banner replaces the CTA when the patient is flagged
         do_not_contact (and reuses the same surface for archived). -->
    <div
      v-if="doNotContact"
      class="alert-surface-warning rounded-token-md px-3 py-2 flex items-start gap-2"
      role="status"
    >
      <UIcon
        name="i-lucide-phone-off"
        class="w-4 h-4 mt-0.5 shrink-0"
        :style="{ color: 'var(--color-warning-accent)' }"
        aria-hidden="true"
      />
      <div class="text-sm leading-snug">
        <p class="font-medium text-default">
          {{ t('patients.doNotContact.badge') }}
        </p>
        <p class="text-subtle text-caption mt-0.5">
          {{ t('recalls.doNotContact.cannotSchedule') }}
        </p>
      </div>
    </div>

    <template v-else-if="canSchedule">
      <UButton
        color="primary"
        variant="soft"
        icon="i-lucide-bell"
        size="sm"
        class="w-full"
        @click="open = true"
      >
        {{ t('recalls.setRecall') }}
      </UButton>

      <!-- Inline active-recall card. Only renders when an active
           recall exists; otherwise the slot just shows the CTA. -->
      <NuxtLink
        v-if="nextRecall"
        :to="`/recalls?patient_id=${patient.id}`"
        class="block mt-2 rounded-token-md border border-default bg-default hover:bg-elevated px-3 py-2 transition-colors"
      >
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-bell-ring"
            class="w-4 h-4 text-primary-accent shrink-0"
          />
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-default truncate">
              {{ formatMonth(nextRecall.due_month) }} ·
              {{ t(`recalls.reasons.${nextRecall.reason}`) }}
            </p>
            <p class="text-caption text-subtle">
              {{ t('recalls.activeRecallHint') }}
            </p>
          </div>
          <UBadge
            :color="statusColour(nextRecall.status)"
            variant="subtle"
            size="xs"
          >
            {{ t(`recalls.status.${nextRecall.status}`) }}
          </UBadge>
        </div>
      </NuxtLink>
    </template>

    <SetRecallModal
      v-if="canSchedule"
      v-model:open="open"
      :patient-id="patient.id"
      @saved="onSaved"
    />
  </div>
</template>
