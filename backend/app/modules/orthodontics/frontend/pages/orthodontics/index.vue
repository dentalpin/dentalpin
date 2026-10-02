<script setup lang="ts">
/**
 * /orthodontics inbox: active / overdue / unscheduled / finished tabs,
 * case sheet inline. Deep-linkable via ?case_id=.
 */
import type { OrthoCase } from '../../composables/useOrthodontics'
import { PERMISSIONS } from '~~/app/config/permissions'
import OrthoCaseSheet from '../../components/OrthoCaseSheet.vue'

const { t, locale } = useI18n()
const { can } = usePermissions()
const route = useRoute()
const toast = useToast()
const { listCases, getSettings, updateSettings } = useOrthodontics()

const canRead = computed(() => can(PERMISSIONS.orthodontics.casesRead))
const canSettings = computed(() => can(PERMISSIONS.orthodontics.settingsManage))

const tab = ref<'active' | 'overdue' | 'unscheduled' | 'finished'>('active')
const rows = ref<OrthoCase[]>([])
const selectedId = ref<string | null>((route.query.case_id as string) || null)
const isLoading = ref(false)

const showSettings = ref(false)
const editWires = ref('')
const editProcedures = ref('')

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium' }).format(new Date(iso))
}

function isOverdue(c: OrthoCase): boolean {
  if (!c.next_due || c.status === 'finished' || c.status === 'transferred_out') return false
  return new Date(c.next_due) < new Date(new Date().toDateString())
}

const filtered = computed(() => {
  switch (tab.value) {
    case 'active':
      return rows.value.filter(c => c.status === 'active' || c.status === 'paused')
    case 'overdue':
      return rows.value.filter(isOverdue)
    case 'unscheduled':
      return rows.value.filter(c => !c.next_due && (c.status === 'active' || c.status === 'paused'))
    case 'finished':
      return rows.value.filter(c => c.status === 'finished' || c.status === 'transferred_out')
  }
  return rows.value
})

async function refresh() {
  isLoading.value = true
  try {
    rows.value = await listCases()
  } catch {
    toast.add({ title: t('orthodontics.errors.loadFailed'), color: 'error' })
  } finally {
    isLoading.value = false
  }
}

async function openSettings() {
  const s = await getSettings()
  editWires.value = s.wires.join('\n')
  editProcedures.value = s.procedures.join('\n')
  showSettings.value = true
}

async function saveSettings() {
  try {
    await updateSettings(
      editWires.value.split('\n'),
      editProcedures.value.split('\n')
    )
    showSettings.value = false
  } catch {
    toast.add({ title: t('orthodontics.errors.saveFailed'), color: 'error' })
  }
}

onMounted(refresh)
</script>

<template>
  <div
    v-if="canRead"
    class="p-4"
  >
    <h1 class="mb-3 text-xl font-semibold">
      {{ t('orthodontics.inbox.title') }}
    </h1>
    <div class="mb-3">
      <UButton
        v-if="canSettings"
        size="sm"
        variant="soft"
        @click="openSettings()"
      >
        {{ t('orthodontics.settings.title') }}
      </UButton>
    </div>
    <div class="grid gap-4 md:grid-cols-[320px_1fr]">
      <div>
        <div class="mb-2 flex flex-wrap gap-1">
          <UButton
            v-for="k in (['active', 'overdue', 'unscheduled', 'finished'] as const)"
            :key="k"
            size="sm"
            :variant="tab === k ? 'solid' : 'soft'"
            @click="tab = k; selectedId = null"
          >
            {{ t(`orthodontics.inbox.${k}`) }}
          </UButton>
        </div>
        <USkeleton
          v-if="isLoading"
          class="h-24"
        />
        <p
          v-else-if="filtered.length === 0"
          class="text-sm text-gray-500"
        >
          {{ t('orthodontics.inbox.empty') }}
        </p>
        <UCard
          v-for="c in filtered"
          :key="c.id"
          class="mb-2 cursor-pointer"
          :class="{ 'ring-2': selectedId === c.id }"
          @click="selectedId = c.id"
        >
          <div class="text-sm font-medium">
            {{ c.patient_name || '—' }}
          </div>
          <div class="text-xs text-gray-500">
            {{ t(`orthodontics.appliance.${c.appliance_type}`) }} ·
            {{ t(`orthodontics.status.${c.status}`) }}
            <span v-if="c.next_due">· {{ t('orthodontics.inbox.nextDue') }}: {{ formatDate(c.next_due) }}</span>
          </div>
        </UCard>
      </div>
      <div>
        <OrthoCaseSheet
          v-if="selectedId"
          :key="selectedId"
          :case-id="selectedId"
        />
      </div>
    </div>

    <UModal
      v-model:open="showSettings"
      :title="t('orthodontics.settings.title')"
    >
      <template #body>
        <div class="space-y-3">
          <div>
            <div class="mb-1 text-sm font-medium">
              {{ t('orthodontics.settings.wires') }}
            </div>
            <UTextarea
              v-model="editWires"
              :rows="6"
            />
          </div>
          <div>
            <div class="mb-1 text-sm font-medium">
              {{ t('orthodontics.settings.procedures') }}
            </div>
            <UTextarea
              v-model="editProcedures"
              :rows="6"
            />
          </div>
        </div>
      </template>
      <template #footer>
        <UButton @click="saveSettings()">
          {{ t('orthodontics.settings.save') }}
        </UButton>
      </template>
    </UModal>
  </div>
</template>
