<script setup lang="ts">
import { ref } from 'vue'
import type {
  RecallChannel,
  RecallOutcome,
  RecallContactAttempt
} from '../composables/useRecalls'
import { errorDetail } from '~~/app/utils/error'

interface Props {
  recallId: string
  defaultChannel?: RecallChannel
  /** Default outcome — call list "no_answer" tap uses this. */
  defaultOutcome?: RecallOutcome
}

const props = withDefaults(defineProps<Props>(), {
  defaultChannel: 'phone',
  defaultOutcome: 'no_answer'
})

const emit = defineEmits<{
  logged: [attempt: RecallContactAttempt]
  cancel: []
}>()

const { t } = useI18n()
const toast = useToast()
const recallsApi = useRecalls()

const channel = ref<RecallChannel>(props.defaultChannel)
const outcome = ref<RecallOutcome>(props.defaultOutcome)
const note = ref('')
const isSubmitting = ref(false)

const channelOptions = computed(() =>
  (['phone', 'whatsapp', 'sms', 'email'] as RecallChannel[]).map(c => ({
    value: c,
    label: t(`recalls.channel.${c}`)
  }))
)
const outcomeOptions = computed(() =>
  (['no_answer', 'voicemail', 'scheduled', 'declined', 'wrong_number'] as RecallOutcome[]).map(o => ({
    value: o,
    label: t(`recalls.outcome.${o}`)
  }))
)

async function submit() {
  if (isSubmitting.value) return
  isSubmitting.value = true
  try {
    const res = await recallsApi.logAttempt(props.recallId, {
      channel: channel.value,
      outcome: outcome.value,
      note: note.value || null
    })
    emit('logged', res.data)
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorDetail(e), color: 'error' })
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="space-y-3">
    <UFormField :label="t('recalls.logAttempt.channel')">
      <USelectMenu
        v-model="channel"
        :items="channelOptions"
        value-key="value"
        label-key="label"
      />
    </UFormField>
    <UFormField :label="t('recalls.logAttempt.outcome')">
      <USelectMenu
        v-model="outcome"
        :items="outcomeOptions"
        value-key="value"
        label-key="label"
      />
    </UFormField>
    <UFormField :label="t('recalls.logAttempt.note')">
      <UTextarea
        v-model="note"
        :rows="2"
        :maxlength="500"
      />
    </UFormField>

    <div class="flex justify-end gap-2">
      <UButton
        color="neutral"
        variant="ghost"
        :disabled="isSubmitting"
        @click="emit('cancel')"
      >
        {{ t('actions.cancel') }}
      </UButton>
      <UButton
        color="primary"
        :loading="isSubmitting"
        @click="submit"
      >
        {{ t('recalls.logAttempt.submit') }}
      </UButton>
    </div>
  </div>
</template>
