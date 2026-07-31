<script setup lang="ts">
import type { CopilotUiMessage } from '../composables/useCopilot'

const props = defineProps<{ message: CopilotUiMessage }>()
const emit = defineEmits<{ confirm: [callId: string, decision: 'confirm' | 'reject'] }>()
const { t } = useI18n()

const expanded = ref(true)

function copyText(text: string) {
  navigator.clipboard?.writeText(text)
}

const toolLabel = computed(() => {
  if (props.message.kind !== 'tool') return ''
  const key
    = props.message.status === 'running'
      ? 'copilot.tool.running'
      : props.message.status === 'failed'
        ? 'copilot.tool.failed'
        : 'copilot.tool.done'
  return t(key, { name: props.message.name })
})

// A finished tool with an object result gets an expandable rich card.
const hasCard = computed(
  () =>
    props.message.kind === 'tool'
    && props.message.status === 'done'
    && !!props.message.result
    && typeof props.message.result === 'object'
)

function toggleCard() {
  if (hasCard.value) expanded.value = !expanded.value
}
</script>

<template>
  <!-- User / assistant text bubble -->
  <div
    v-if="message.kind === 'text'"
    class="group flex flex-col"
    :class="message.role === 'user' ? 'items-end' : 'items-start'"
  >
    <div
      class="max-w-[85%] rounded-lg px-3 py-2 text-sm"
      :class="
        message.role === 'user'
          ? 'whitespace-pre-wrap bg-primary text-inverted'
          : 'bg-elevated text-default'
      "
    >
      <CopilotMarkdown
        v-if="message.role === 'assistant'"
        :text="message.text"
      />
      <template v-else>
        {{ message.text }}
      </template>
    </div>
    <UButton
      v-if="message.role === 'assistant' && !message.streaming && message.text"
      icon="i-lucide-copy"
      color="neutral"
      variant="ghost"
      size="xs"
      class="mt-0.5 opacity-0 transition focus:opacity-100 group-hover:opacity-100"
      :aria-label="t('copilot.copy')"
      @click="copyText(message.text)"
    />
  </div>

  <!-- Tool-call chip + expandable result card -->
  <div
    v-else-if="message.kind === 'tool'"
    class="px-1 text-xs text-muted"
  >
    <button
      type="button"
      class="flex items-center gap-2"
      :class="hasCard ? 'cursor-pointer hover:text-default' : 'cursor-default'"
      @click="toggleCard"
    >
      <UIcon
        :name="
          message.status === 'running'
            ? 'i-lucide-loader-circle'
            : message.status === 'failed'
              ? 'i-lucide-circle-x'
              : 'i-lucide-circle-check'
        "
        :class="message.status === 'running' ? 'animate-spin' : ''"
      />
      <span>{{ toolLabel }}</span>
      <UIcon
        v-if="hasCard"
        :name="expanded ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
      />
    </button>
    <div
      v-if="hasCard && expanded"
      class="mt-1.5"
    >
      <CopilotResultCard
        :name="message.name"
        :result="message.result"
      />
    </div>
  </div>

  <!-- Inline confirmation card -->
  <CopilotConfirmCard
    v-else-if="message.kind === 'confirmation'"
    :call-id="message.callId"
    :name="message.name"
    :args="message.args"
    :resolved="message.resolved"
    @confirm="(id, d) => emit('confirm', id, d)"
  />
</template>
