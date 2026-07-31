<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Recall } from '../composables/useRecalls'
import { errorDetail } from '~~/app/utils/error'

interface Props { recall: Recall }
const props = defineProps<Props>()

const emit = defineEmits<{
  changed: [recall: Recall]
  delete: [recall: Recall]
}>()

const { t, locale } = useI18n()
const toast = useToast()
const recallsApi = useRecalls()

const logOpen = ref(false)
const snoozeOpen = ref(false)
const snoozeMonths = ref(3)
const isBusy = ref(false)

const patient = computed(() => props.recall.patient ?? null)

const callable = computed(
  () =>
    !!patient.value?.phone
    && !patient.value?.do_not_contact
    && patient.value?.status !== 'archived'
)

const phoneHref = computed(() =>
  patient.value?.phone ? `tel:${patient.value.phone}` : undefined
)

const monthLabel = computed(() => {
  const date = new Date(props.recall.due_month)
  return new Intl.DateTimeFormat(locale.value, {
    year: 'numeric',
    month: 'long'
  }).format(date)
})

async function quickNoAnswer() {
  if (isBusy.value) return
  isBusy.value = true
  try {
    await recallsApi.logAttempt(props.recall.id, {
      channel: 'phone',
      outcome: 'no_answer'
    })
    const updated = await recallsApi.get(props.recall.id)
    emit('changed', updated.data)
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorDetail(e), color: 'error' })
  } finally {
    isBusy.value = false
  }
}

async function bookAppointment() {
  await navigateTo(
    `/appointments?patient_id=${props.recall.patient_id}&recall_id=${props.recall.id}`
  )
}

async function snooze() {
  if (isBusy.value) return
  isBusy.value = true
  try {
    const res = await recallsApi.snooze(props.recall.id, snoozeMonths.value)
    snoozeOpen.value = false
    emit('changed', res.data)
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorDetail(e), color: 'error' })
  } finally {
    isBusy.value = false
  }
}

async function cancelRecall() {
  if (isBusy.value) return
  isBusy.value = true
  try {
    const res = await recallsApi.cancel(props.recall.id)
    emit('changed', res.data)
  } finally {
    isBusy.value = false
  }
}

async function markDone() {
  if (isBusy.value) return
  isBusy.value = true
  try {
    const res = await recallsApi.markDone(props.recall.id)
    emit('changed', res.data)
  } finally {
    isBusy.value = false
  }
}

const priorityChipColour = computed<'error' | 'info' | 'neutral'>(() => {
  switch (props.recall.priority) {
    case 'high': return 'error'
    case 'normal': return 'info'
    default: return 'neutral'
  }
})

async function onAttemptLogged() {
  logOpen.value = false
  const updated = await recallsApi.get(props.recall.id)
  emit('changed', updated.data)
}
</script>

<template>
  <div
    class="rounded-token-md border border-default bg-default p-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3"
  >
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 flex-wrap">
        <NuxtLink
          v-if="patient"
          :to="`/patients/${patient.id}`"
          class="font-medium text-default hover:underline"
        >
          {{ patient.first_name }} {{ patient.last_name }}
        </NuxtLink>
        <UBadge
          :color="priorityChipColour"
          variant="subtle"
          size="xs"
        >
          {{ t(`recalls.priority.${recall.priority}`) }}
        </UBadge>
        <UBadge
          variant="soft"
          size="xs"
        >
          {{ t(`recalls.reasons.${recall.reason}`) }}
        </UBadge>
        <UBadge
          variant="soft"
          color="neutral"
          size="xs"
        >
          {{ t(`recalls.status.${recall.status}`) }}
        </UBadge>
      </div>
      <div class="text-caption text-subtle mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
        <span>{{ monthLabel }}</span>
        <span v-if="patient?.phone">📞 {{ patient.phone }}</span>
        <span v-if="recall.contact_attempt_count > 0">
          {{ recall.contact_attempt_count }} {{ t('recalls.actions.logAttempt') }}
        </span>
      </div>
      <p
        v-if="recall.reason_note"
        class="text-sm text-subtle mt-1 line-clamp-2"
      >
        {{ recall.reason_note }}
      </p>
    </div>

    <div class="flex gap-1 sm:gap-2 flex-wrap">
      <UButton
        v-if="callable"
        :href="phoneHref"
        icon="i-lucide-phone"
        size="sm"
        color="primary"
        variant="soft"
      >
        {{ t('recalls.actions.call') }}
      </UButton>
      <UButton
        icon="i-lucide-phone-off"
        size="sm"
        variant="ghost"
        color="neutral"
        :loading="isBusy"
        :title="t('recalls.actions.noAnswer')"
        @click="quickNoAnswer"
      />
      <UButton
        icon="i-lucide-list-plus"
        size="sm"
        variant="ghost"
        color="neutral"
        :title="t('recalls.actions.logAttempt')"
        @click="logOpen = true"
      />
      <UButton
        icon="i-lucide-calendar-plus"
        size="sm"
        variant="ghost"
        color="neutral"
        :title="t('recalls.actions.book')"
        @click="bookAppointment"
      />
      <UDropdownMenu
        :items="[
          {
            label: t('recalls.actions.snooze'),
            icon: 'i-lucide-clock',
            onSelect: () => { snoozeOpen = true }
          },
          {
            label: t('recalls.actions.markDone'),
            icon: 'i-lucide-check',
            onSelect: () => markDone()
          },
          {
            label: t('recalls.actions.cancel'),
            icon: 'i-lucide-x',
            color: 'error',
            onSelect: () => cancelRecall()
          }
        ]"
      >
        <UButton
          icon="i-lucide-more-vertical"
          size="sm"
          variant="ghost"
          color="neutral"
        />
      </UDropdownMenu>
    </div>

    <UModal
      :open="logOpen"
      :title="t('recalls.actions.logAttempt')"
      @update:open="(v: boolean) => { logOpen = v }"
    >
      <template #body>
        <div class="p-4">
          <LogAttemptForm
            :recall-id="recall.id"
            @logged="onAttemptLogged"
            @cancel="logOpen = false"
          />
        </div>
      </template>
    </UModal>

    <UModal
      :open="snoozeOpen"
      :title="t('recalls.snoozePrompt')"
      @update:open="(v: boolean) => { snoozeOpen = v }"
    >
      <template #body>
        <div class="p-4">
          <UInput
            v-model.number="snoozeMonths"
            type="number"
            min="1"
            max="24"
          />
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2 p-2">
          <UButton
            color="neutral"
            variant="ghost"
            @click="snoozeOpen = false"
          >
            {{ t('actions.cancel') }}
          </UButton>
          <UButton
            color="primary"
            :loading="isBusy"
            @click="snooze"
          >
            {{ t('recalls.actions.snooze') }}
          </UButton>
        </div>
      </template>
    </UModal>
  </div>
</template>
