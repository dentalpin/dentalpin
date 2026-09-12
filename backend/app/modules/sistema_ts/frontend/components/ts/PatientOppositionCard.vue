<script setup lang="ts">
// Patient summary card: the patient's opposition to the Sistema TS
// (spec table 5 — documents still go, anonymised). Renders only for
// Italian clinics; toggling needs `sistema_ts.opposition.write`.
import { useSistemaTs, fmtDate, type Opposition } from '../../composables/useSistemaTs'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

interface Ctx {
  patient: { id: string }
}

const props = defineProps<{ ctx: Ctx }>()
const { t } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const country = useClinicCountry()
const { fetchOpposition, setOpposition } = useSistemaTs()

const isIT = computed(() => country.value === 'IT')
const state = ref<Opposition | null>(null)
const busy = ref(false)
const note = ref('')

async function load() {
  if (!isIT.value) return
  try {
    state.value = await fetchOpposition(props.ctx.patient.id)
    note.value = state.value.note ?? ''
  } catch {
    state.value = null
  }
}
onMounted(load)
watch(() => props.ctx.patient.id, load)

async function toggle(opposed: boolean) {
  busy.value = true
  try {
    state.value = await setOpposition(props.ctx.patient.id, opposed, note.value || null)
    toast.add({ title: t(opposed ? 'sistema_ts.opposition.recorded' : 'sistema_ts.opposition.revoked'), color: 'success' })
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorMessage(e, t('sistema_ts.opposition.failed')), color: 'error' })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <UCard v-if="isIT && state">
    <template #header>
      <div class="flex items-center justify-between gap-2">
        <span class="font-medium">{{ t('sistema_ts.opposition.title') }}</span>
        <UBadge
          :color="state.opposed ? 'warning' : 'success'"
          variant="subtle"
        >
          {{ state.opposed ? t('sistema_ts.opposition.opposed') : t('sistema_ts.opposition.notOpposed') }}
        </UBadge>
      </div>
    </template>
    <div class="space-y-2 text-sm">
      <p class="text-subtle">
        {{ t('sistema_ts.opposition.help') }}
      </p>
      <p
        v-if="state.opposed && state.opposed_since"
        class="text-xs text-subtle"
      >
        {{ t('sistema_ts.opposition.since', { date: fmtDate(state.opposed_since) }) }}
      </p>
      <template v-if="can(PERMISSIONS.sistemaTs.oppositionWrite)">
        <UInput
          v-model="note"
          :placeholder="t('sistema_ts.opposition.notePlaceholder')"
          maxlength="300"
          class="w-full"
        />
        <UButton
          v-if="!state.opposed"
          size="xs"
          color="warning"
          variant="soft"
          icon="i-lucide-eye-off"
          :loading="busy"
          @click="toggle(true)"
        >
          {{ t('sistema_ts.opposition.record') }}
        </UButton>
        <UButton
          v-else
          size="xs"
          variant="soft"
          icon="i-lucide-eye"
          :loading="busy"
          @click="toggle(false)"
        >
          {{ t('sistema_ts.opposition.revoke') }}
        </UButton>
      </template>
    </div>
  </UCard>
</template>
