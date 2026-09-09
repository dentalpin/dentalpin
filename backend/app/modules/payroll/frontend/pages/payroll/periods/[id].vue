<template>
  <div class="space-y-6">
    <div class="flex items-center gap-4">
      <UButton
        variant="ghost"
        icon="i-lucide-arrow-left"
        :to="'/payroll/periods'"
      >
        {{ t('payroll.common.back') }}
      </UButton>
      <div v-if="period">
        <h1 class="text-2xl font-bold">
          {{ period.month }}
        </h1>
        <UBadge
          :color="period.status === 'draft' ? 'primary' : 'neutral'"
          variant="soft"
        >
          {{ t(`payroll.periods.${period.status}`) }}
        </UBadge>
      </div>
      <USkeleton
        v-else
        class="h-8 w-48"
      />
      <div
        v-if="can(PERMISSIONS.payroll.write) && isDraft"
        class="ms-auto"
      >
        <UButton
          icon="i-lucide-plus"
          @click="openCreate"
        >
          {{ t('payroll.entries.add') }}
        </UButton>
      </div>
    </div>

    <div
      v-if="loading"
      class="space-y-4"
    >
      <USkeleton
        v-for="i in 5"
        :key="i"
        class="h-16"
      />
    </div>

    <UAlert
      v-else-if="error"
      color="error"
      :title="t('payroll.common.loadError')"
      :actions="[{ label: t('payroll.common.retry'), onClick: fetchAll }]"
    />

    <UCard v-else-if="entries.length === 0">
      <p class="text-sm text-muted-foreground">
        {{ t('payroll.entries.empty') }}
      </p>
    </UCard>

    <div
      v-else
      class="space-y-2"
    >
      <UCard
        v-for="entry in entries"
        :key="entry.id"
      >
        <div class="flex items-center justify-between gap-4">
          <div class="min-w-0">
            <p class="font-medium truncate">
              {{ staffName(entry.user_id) }}
            </p>
            <p
              class="text-sm text-muted-foreground"
              dir="ltr"
            >
              {{ entry.gross }} − {{ entry.deductions }} = {{ entry.net }}
            </p>
            <p
              v-if="entry.notes"
              class="text-sm text-muted-foreground truncate"
            >
              {{ entry.notes }}
            </p>
          </div>
          <div
            v-if="can(PERMISSIONS.payroll.write) && isDraft"
            class="flex shrink-0 gap-2"
          >
            <UButton
              variant="ghost"
              icon="i-lucide-pencil"
              @click="openEdit(entry)"
            >
              {{ t('payroll.common.edit') }}
            </UButton>
            <UButton
              variant="ghost"
              color="error"
              icon="i-lucide-trash-2"
              @click="askDelete(entry)"
            >
              {{ t('payroll.common.delete') }}
            </UButton>
          </div>
        </div>
      </UCard>
    </div>

    <UModal v-model:open="showForm">
      <template #content>
        <UCard>
          <div class="space-y-4">
            <UFormField
              v-if="!editing"
              :label="t('payroll.entries.staff')"
            >
              <USelect
                v-model="form.user_id"
                :items="staffOptions"
                class="w-full"
              />
            </UFormField>
            <div class="grid grid-cols-3 gap-4">
              <UFormField :label="t('payroll.entries.gross')">
                <UInput
                  v-model="form.gross"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="t('payroll.entries.deductions')">
                <UInput
                  v-model="form.deductions"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="t('payroll.entries.net')">
                <UInput
                  v-model="form.net"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-full"
                />
              </UFormField>
            </div>
            <p
              v-if="netMismatch"
              class="text-sm text-error"
            >
              {{ t('payroll.entries.netMismatch') }}
            </p>
            <UFormField :label="t('payroll.entries.notes')">
              <UInput
                v-model="form.notes"
                class="w-full"
              />
            </UFormField>
          </div>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                @click="showForm = false"
              >
                {{ t('payroll.common.cancel') }}
              </UButton>
              <UButton
                :loading="saving"
                :disabled="!formValid"
                @click="save"
              >
                {{ t('payroll.common.save') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>

    <UModal v-model:open="showDelete">
      <template #content>
        <UCard>
          <p class="text-sm">
            {{ t('payroll.entries.deleteConfirm') }}
          </p>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                @click="showDelete = false"
              >
                {{ t('payroll.common.cancel') }}
              </UButton>
              <UButton
                color="error"
                :loading="saving"
                @click="removeEntry"
              >
                {{ t('payroll.common.delete') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>
  </div>
</template>

<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'
import type { PayrollEntry, PayrollPeriod, StaffUser } from '../../../composables/usePayroll'

const { t } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const route = useRoute()
const { listEntries, createEntry, updateEntry, deleteEntry, listStaff } = usePayroll()
const api = useApi()

const periodId = computed(() => String(route.params.id))
const period = ref<PayrollPeriod | null>(null)
const entries = ref<PayrollEntry[]>([])
const staff = ref<StaffUser[]>([])
const loading = ref(true)
const error = ref(false)
const saving = ref(false)
const showForm = ref(false)
const showDelete = ref(false)
const deleting = ref<PayrollEntry | null>(null)
const editing = ref<PayrollEntry | null>(null)
const form = ref({
  user_id: '',
  gross: '',
  deductions: '',
  net: '',
  notes: ''
})

const isDraft = computed(() => period.value?.status === 'draft')

const staffOptions = computed(() =>
  staff.value.map(u => ({
    label: `${u.last_name}, ${u.first_name} (${u.email})`,
    value: u.id
  }))
)

const netMismatch = computed(() => {
  const g = Number(form.value.gross)
  const d = Number(form.value.deductions)
  const n = Number(form.value.net)
  if (form.value.gross === '' || form.value.deductions === '' || form.value.net === '') return false
  if (Number.isNaN(g) || Number.isNaN(d) || Number.isNaN(n)) return true
  return Math.abs(n - (g - d)) > 0.005
})

const formValid = computed(() => {
  if (!editing.value && !form.value.user_id) return false
  if (form.value.gross === '' || form.value.deductions === '' || form.value.net === '') return false
  return !netMismatch.value
})

function staffName(userId: string): string {
  const u = staff.value.find(s => s.id === userId)
  return u ? `${u.last_name}, ${u.first_name}` : userId
}

async function fetchAll() {
  loading.value = true
  error.value = false
  try {
    const [p, elist, slist] = await Promise.all([
      api.get<{ data: PayrollPeriod }>(`/api/v1/payroll/periods/${periodId.value}`),
      listEntries(periodId.value),
      listStaff()
    ])
    period.value = p.data
    entries.value = elist.data
    staff.value = slist.data
  } catch (e) {
    error.value = true
    toast.add({ title: t('payroll.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = { user_id: '', gross: '', deductions: '', net: '', notes: '' }
  showForm.value = true
}

function openEdit(entry: PayrollEntry) {
  editing.value = entry
  form.value = {
    user_id: entry.user_id,
    gross: entry.gross,
    deductions: entry.deductions,
    net: entry.net,
    notes: entry.notes ?? ''
  }
  showForm.value = true
}

async function save() {
  saving.value = true
  try {
    if (editing.value) {
      await updateEntry(editing.value.id, {
        gross: form.value.gross,
        deductions: form.value.deductions,
        net: form.value.net,
        notes: form.value.notes || null
      })
    } else {
      await createEntry({
        period_id: periodId.value,
        user_id: form.value.user_id,
        gross: form.value.gross,
        deductions: form.value.deductions,
        net: form.value.net,
        notes: form.value.notes || null
      })
    }
    showForm.value = false
    await fetchAll()
  } catch (e) {
    toast.add({ title: t('payroll.common.saveError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

function askDelete(entry: PayrollEntry) {
  deleting.value = entry
  showDelete.value = true
}

async function removeEntry() {
  if (!deleting.value) return
  saving.value = true
  try {
    await deleteEntry(deleting.value.id)
    showDelete.value = false
    deleting.value = null
    await fetchAll()
  } catch (e) {
    toast.add({ title: t('payroll.common.saveError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

onMounted(fetchAll)
</script>
