<script setup lang="ts">
import type { Appointment } from '~~/app/types'
import type { TransitionDescriptor } from '../../composables/useAppointmentStatus'

const props = defineProps<{
  appointment: Appointment
  /** Compact icon-only button (for calendar/daily cards). Default: icon button. */
  dense?: boolean
}>()

const emit = defineEmits<{
  transitioned: [appointment: Appointment, to: TransitionDescriptor['to']]
  failed: [err: unknown]
}>()

const { t } = useI18n()
const toast = useToast()
const { transition } = useAppointments()
const { nextTransitions, statusIcon } = useAppointmentStatus()

const isBusy = ref(false)
const pendingDescriptor = ref<TransitionDescriptor | null>(null)
const pendingNote = ref('')

// Post-completion follow-up modal is hosted once at the agenda page
// level (`CompletionFollowupHost.vue`) so it stays consistent across
// the dropdown path and the kanban drag-drop path.
const completionFollowup = useCompletionFollowup()

const transitions = computed(() => nextTransitions(props.appointment.status))
const hasActions = computed(() => transitions.value.length > 0)

function dropdownItems() {
  return transitions.value.map((tr, idx) => ({
    label: t(tr.labelKey),
    icon: tr.icon,
    color: tr.destructive ? ('error' as const) : undefined,
    onSelect: (e?: Event) => {
      e?.preventDefault?.()
      if (tr.destructive) {
        pendingDescriptor.value = tr
        pendingNote.value = ''
      } else {
        void runTransition(tr)
      }
    },
    kbd: idx === 0 ? ['enter'] : undefined
  }))
}

async function runTransition(tr: TransitionDescriptor, note?: string) {
  if (isBusy.value) return
  isBusy.value = true
  try {
    await transition(props.appointment.id, tr.to, note?.trim() || undefined)
    emit('transitioned', props.appointment, tr.to)
    if (tr.to === 'completed') {
      completionFollowup.trigger(props.appointment)
    }
  } catch (err) {
    toast.add({ title: t('appointments.transitionFailed'), color: 'error' })
    emit('failed', err)
  } finally {
    isBusy.value = false
  }
}

function confirmPending() {
  if (!pendingDescriptor.value) return
  const tr = pendingDescriptor.value
  const note = pendingNote.value
  pendingDescriptor.value = null
  void runTransition(tr, note)
}

function cancelPending() {
  pendingDescriptor.value = null
  pendingNote.value = ''
}

const confirmMessage = computed(() => {
  if (!pendingDescriptor.value) return ''
  if (pendingDescriptor.value.to === 'no_show') {
    return t('appointments.confirmNoShowMessage')
  }
  return t('appointments.confirmCancelMessage')
})
</script>

<template>
  <UDropdownMenu
    v-if="hasActions"
    :items="dropdownItems()"
    :ui="{ content: 'min-w-56' }"
  >
    <UButton
      :icon="props.dense ? statusIcon(props.appointment.status) : 'i-lucide-chevrons-right'"
      :size="props.dense ? 'xs' : 'sm'"
      color="neutral"
      variant="ghost"
      :aria-label="t('appointments.transitions.checked_in')"
      :loading="isBusy"
      :disabled="isBusy"
      @click.stop
    />
  </UDropdownMenu>

  <UModal
    :open="!!pendingDescriptor"
    :title="t('appointments.confirmTransitionTitle')"
    @update:open="(v: boolean) => { if (!v) cancelPending() }"
  >
    <template #body>
      <div class="space-y-3 p-4">
        <p class="text-sm text-default">
          {{ confirmMessage }}
        </p>
        <UFormField :label="t('appointments.noteLabel')">
          <UTextarea
            v-model="pendingNote"
            :rows="2"
            :maxlength="500"
          />
        </UFormField>
      </div>
    </template>
    <template #footer>
      <div class="flex justify-end gap-2 p-2">
        <UButton
          color="neutral"
          variant="ghost"
          @click="cancelPending"
        >
          {{ t('actions.cancel') }}
        </UButton>
        <UButton
          color="error"
          :loading="isBusy"
          @click="confirmPending"
        >
          {{ pendingDescriptor ? t(pendingDescriptor.labelKey) : '' }}
        </UButton>
      </div>
    </template>
  </UModal>

  <!-- Post-completion modal lives once in `CompletionFollowupHost`
       at the page level, not here. -->
</template>
