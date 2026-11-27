<script setup lang="ts">
import { useConversation } from '../composables/useConversation'
import { errorDetail } from '~~/app/utils/error'

const props = defineProps<{ ctx: { patient: { id: string } } }>()
const { t } = useI18n()
const toast = useToast()

const patientId = props.ctx?.patient?.id ?? null
const conv = patientId ? useConversation(patientId) : null
const draft = ref('')

// The thread is WhatsApp-only for now. On a clinic without a configured
// WhatsApp channel every patient showed an empty card with a reply box
// that could only ever 409 — hide it until the channel is available
// (GET /notifications/channels asks each adapter's `supports`).
const api = useApi()
const channelReady = ref(false)
const replyAvailable = ref(false)

onMounted(async () => {
  if (!conv) return
  try {
    const res = await api.get<{ data: { available: string[], whatsapp_session_available: boolean } }>('/api/v1/notifications/channels')
    channelReady.value = res.data.available.includes('whatsapp')
    replyAvailable.value = res.data.whatsapp_session_available
  } catch {
    channelReady.value = false
  }
  if (channelReady.value) conv.fetchThread()
})

async function onSend() {
  if (!conv || conv.sending.value || !draft.value.trim()) return
  try {
    if (await conv.reply(draft.value.trim())) draft.value = ''
  } catch (e: unknown) {
    toast.add({
      title: t('notifications.conversation.replyError'),
      description: errorDetail(e) ?? t('notifications.conversation.windowClosed'),
      color: 'error'
    })
  }
}

function label(m: { body_text: string | null, subject: string | null, template_key: string }) {
  return m.body_text || m.subject || m.template_key
}
</script>

<template>
  <UCard v-if="patientId && conv && channelReady">
    <template #header>
      <span class="font-medium">{{ t('notifications.conversation.title') }}</span>
    </template>

    <USkeleton
      v-if="conv.loading.value"
      class="h-24 w-full"
    />
    <div v-else>
      <p
        v-if="!conv.messages.value.length"
        class="text-sm text-gray-500"
      >
        {{ t('notifications.conversation.empty') }}
      </p>
      <ul
        v-else
        class="space-y-2 max-h-72 overflow-y-auto"
      >
        <li
          v-for="m in conv.messages.value"
          :key="m.id"
          class="flex"
          :class="m.direction === 'inbound' ? 'justify-start' : 'justify-end'"
        >
          <div
            class="rounded-lg px-3 py-2 text-sm max-w-[80%]"
            :class="m.direction === 'inbound' ? 'bg-gray-100 dark:bg-gray-800' : 'bg-primary-100 dark:bg-primary-900'"
          >
            <div>{{ label(m) }}</div>
            <div class="text-[10px] text-gray-400 mt-1">
              <UBadge
                v-if="m.status === 'awaiting_manual'"
                color="warning"
                variant="soft"
                size="sm"
              >
                {{ t('notifications.conversation.awaitingManual') }}
              </UBadge>
              <span v-else-if="m.sent_manually">
                {{ t('notifications.conversation.manuallySent') }}
              </span>
              <span v-else>{{ m.status }}</span>
              · {{ new Date(m.created_at).toLocaleString() }}
            </div>
          </div>
        </li>
      </ul>

      <div
        v-if="replyAvailable"
        class="flex gap-2 mt-3"
      >
        <UInput
          v-model="draft"
          class="flex-1"
          :placeholder="t('notifications.conversation.placeholder')"
          @keydown.enter="onSend"
        />
        <UButton
          icon="i-lucide-send"
          :aria-label="t('notifications.conversation.send')"
          :loading="conv.sending.value"
          :disabled="!draft.trim()"
          @click="onSend"
        />
      </div>
    </div>
  </UCard>
</template>
