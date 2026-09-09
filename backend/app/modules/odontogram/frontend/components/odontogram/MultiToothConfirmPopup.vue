<script setup lang="ts">
import type { MultiToothTreatmentConfig, TreatmentStatus } from '~~/app/types'

type BridgeRole = 'pillar' | 'pontic'

const props = defineProps<{
  open: boolean
  config: MultiToothTreatmentConfig
  teeth: number[]
  status: TreatmentStatus
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  /** Bridge: emits teeth with chosen roles. Uniform: emits null. */
  'confirm': [teethRoles: Array<{ tooth_number: number, role: BridgeRole }> | null]
  'cancel': []
}>()

const { t } = useI18n()
const toast = useToast()

const isBridge = computed(() => props.config.mode === 'bridge')
const sortedTeeth = computed(() => [...props.teeth].sort((a, b) => a - b))

/** Per-tooth role state (bridge only). Default: first+last pillar, middle pontic. */
const roles = ref<Record<number, BridgeRole>>({})

function resetRoles() {
  const next: Record<number, BridgeRole> = {}
  const s = sortedTeeth.value
  if (s.length === 0) {
    roles.value = next
    return
  }
  if (s.length === 1) {
    next[s[0]!] = 'pillar'
  } else {
    const first = s[0]!
    const last = s[s.length - 1]!
    for (const n of s) {
      next[n] = (n === first || n === last) ? 'pillar' : 'pontic'
    }
  }
  roles.value = next
}

watch(
  () => [props.open, sortedTeeth.value.join(',')],
  ([isOpen]) => {
    if (isOpen && isBridge.value) resetRoles()
  },
  { immediate: true }
)

function toggleRole(tooth: number) {
  if (!isBridge.value) return
  const current = roles.value[tooth] ?? 'pontic'
  roles.value = { ...roles.value, [tooth]: current === 'pillar' ? 'pontic' : 'pillar' }
}

function roleFor(tooth: number): BridgeRole | null {
  if (!isBridge.value) return null
  return roles.value[tooth] ?? null
}

const pillarCount = computed(() =>
  Object.values(roles.value).filter(r => r === 'pillar').length
)

function handleCancel() {
  emit('cancel')
  emit('update:open', false)
}

function handleConfirm() {
  if (isBridge.value) {
    if (pillarCount.value < 1) {
      toast.add({ title: t('odontogram.multiTooth.needPillar'), color: 'warning' })
      return
    }
    const payload = sortedTeeth.value.map(tooth_number => ({
      tooth_number,
      role: roles.value[tooth_number] ?? 'pontic'
    }))
    emit('confirm', payload)
  } else {
    emit('confirm', null)
  }
}
</script>

<template>
  <UModal
    :open="open"
    @update:open="emit('update:open', $event)"
  >
    <template #content>
      <div class="p-6 space-y-4 max-w-md">
        <h3 class="text-h1 text-default">
          {{ t(config.labelKey) }}
        </h3>

        <p class="text-sm text-[var(--ui-text-muted)]">
          {{ t('odontogram.multiTooth.confirmHint', { n: teeth.length }) }}
        </p>

        <p
          v-if="isBridge"
          class="text-xs text-[var(--ui-text-muted)]"
        >
          {{ t('odontogram.multiTooth.roleHint') }}
        </p>

        <div class="flex flex-wrap gap-2">
          <UBadge
            v-for="tooth in sortedTeeth"
            :key="tooth"
            :color="roleFor(tooth) === 'pillar' ? 'primary' : 'neutral'"
            variant="subtle"
            size="lg"
            :class="isBridge ? 'cursor-pointer select-none' : ''"
            @click="toggleRole(tooth)"
          >
            {{ tooth }}
            <span
              v-if="roleFor(tooth)"
              class="ms-1 text-xs opacity-70"
            >
              ({{ t(`odontogram.multiTooth.${roleFor(tooth)}`) }})
            </span>
          </UBadge>
        </div>

        <div
          v-if="status === 'planned'"
          class="text-xs text-[var(--ui-text-muted)]"
        >
          {{ t('odontogram.multiTooth.willBePlanned') }}
        </div>
        <div
          v-else
          class="text-xs text-[var(--ui-text-muted)]"
        >
          {{ t('odontogram.multiTooth.willBeExisting') }}
        </div>

        <div class="flex justify-end gap-2 pt-2">
          <UButton
            variant="ghost"
            @click="handleCancel"
          >
            {{ t('common.cancel') }}
          </UButton>
          <UButton
            color="primary"
            @click="handleConfirm"
          >
            {{ t('common.confirm') }}
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>
