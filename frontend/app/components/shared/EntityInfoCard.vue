<script setup lang="ts">
export interface InfoItem {
  key: string
  label: string
  value?: string | number | null
  link?: { to: string, label?: string }
  copyable?: boolean
}

interface Props {
  items: InfoItem[]
  title?: string
}

const props = withDefaults(defineProps<Props>(), {
  title: undefined
})

const { t } = useI18n()
const toast = useToast()

const heading = computed(() => props.title ?? t('shared.info'))

async function copy(value: string | number) {
  try {
    await navigator.clipboard.writeText(String(value))
    toast.add({ title: t('common.copied'), color: 'success' })
  } catch {
    toast.add({ title: t('common.copyFailed'), color: 'error' })
  }
}
</script>

<template>
  <UCard>
    <template #header>
      <h2 class="text-h2 text-default">
        {{ heading }}
      </h2>
    </template>

    <dl class="space-y-3">
      <div
        v-for="item in items"
        :key="item.key"
        class="flex items-baseline justify-between gap-3"
      >
        <dt class="text-body text-muted shrink-0">
          {{ item.label }}
        </dt>
        <dd class="text-body text-default text-end min-w-0 truncate flex items-center gap-1.5">
          <NuxtLink
            v-if="item.link"
            :to="item.link.to"
            class="text-primary-accent hover:underline truncate"
          >
            {{ item.link.label ?? item.value ?? '—' }}
          </NuxtLink>
          <span
            v-else
            class="truncate"
          >{{ item.value ?? '—' }}</span>

          <UButton
            v-if="item.copyable && item.value"
            variant="ghost"
            color="neutral"
            icon="i-lucide-copy"
            size="xs"
            :aria-label="t('common.copy')"
            @click="copy(item.value)"
          />
        </dd>
      </div>
    </dl>
  </UCard>
</template>
