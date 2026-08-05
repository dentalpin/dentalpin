<!--
  Matches the confirmed real inventory page pattern: definePageMeta auth
  middleware, usePermissions().can() page guard, UTable with
  :data/:columns (accessorKey/header) + #<key>-cell slots using
  row.original, UModal v-model:open + #content slot, USelect :items.

  Staff picker: uses the host's useUsers() composable (GET /api/v1/auth/users,
  already confirmed working — see useUsers.ts) to search clinic staff by
  name/email in a USelectMenu, replacing the earlier raw UUID input.
-->
<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import {
  usePayroll,
  type AnnualSummary,
  type MonthlySummary,
  type PayrollEntry,
  type PayrollPeriod,
  type StaffPayrollProfile
} from '../../composables/usePayroll'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const payroll = usePayroll()

if (!can(PERMISSIONS.payroll.read)) {
  await navigateTo('/')
}
const canWrite = computed(() => can(PERMISSIONS.payroll.write))

const activeTab = ref<'employees' | 'periods' | 'reports'>('employees')

// --- Employees tab ---------------------------------------------------------

const staff = ref<StaffPayrollProfile[]>([])
const staffLoading = ref(false)

async function loadStaff() {
  staffLoading.value = true
  try {
    const res = await payroll.listStaff()
    staff.value = res.data
  } finally {
    staffLoading.value = false
  }
}

const staffColumns = [
  { accessorKey: 'user_id', header: t('payroll.staff.user') },
  { accessorKey: 'base_salary', header: t('payroll.staff.baseSalary') },
  { accessorKey: 'hourly_rate', header: t('payroll.staff.hourlyRate') },
  { accessorKey: 'tax_regime', header: t('payroll.staff.taxRegime') },
  { accessorKey: 'bank_tax', header: t('payroll.staff.bankTax') },
  { accessorKey: 'is_active', header: t('payroll.staff.status') },
  { accessorKey: 'actions', header: '' }
]

const showStaffModal = ref(false)
const staffSaving = ref(false)
const editingStaffId = ref<string | null>(null)
const staffForm = ref({
  user_id: '',
  base_salary: null as number | null,
  hourly_rate: null as number | null,
  tax_regime: '',
  bank_account: '',
  tax_id: '',
  is_active: true
})

// Staff picker: existing GET /api/v1/auth/users composable, no new
// backend endpoint needed. Excludes users who already have a payroll
// profile (user_id is unique — creating a second would just 409), except
// the profile currently being edited stays selectable/visible.
const { users: clinicUsers, fetchUsers: fetchClinicUsers } = useUsers()
const selectedStaffUser = computed({
  get: () => staffUserOptions.value.find(o => o.id === staffForm.value.user_id) ?? null,
  set: (option: { id: string, label: string } | null) => {
    staffForm.value.user_id = option?.id ?? ''
  }
})
const staffUserOptions = computed(() => {
  const alreadyLinked = new Set(
    staff.value.filter(s => s.id !== editingStaffId.value).map(s => s.user_id)
  )
  return clinicUsers.value
    .filter(u => !alreadyLinked.has(u.id))
    .map(u => ({ id: u.id, label: `${u.first_name} ${u.last_name} (${u.email})` }))
})

function openCreateStaff() {
  editingStaffId.value = null
  staffForm.value = {
    user_id: '',
    base_salary: null,
    hourly_rate: null,
    tax_regime: '',
    bank_account: '',
    tax_id: '',
    is_active: true
  }
  showStaffModal.value = true
}

function openEditStaff(profile: StaffPayrollProfile) {
  editingStaffId.value = profile.id
  staffForm.value = {
    user_id: profile.user_id,
    base_salary: profile.base_salary,
    hourly_rate: profile.hourly_rate,
    tax_regime: profile.tax_regime ?? '',
    bank_account: '', // never pre-filled — write-only field, existing value stays unless replaced
    tax_id: '',
    is_active: profile.is_active
  }
  showStaffModal.value = true
}

async function submitStaff() {
  staffSaving.value = true
  try {
    const payload = {
      base_salary: staffForm.value.base_salary,
      hourly_rate: staffForm.value.hourly_rate,
      tax_regime: staffForm.value.tax_regime || null,
      bank_account: staffForm.value.bank_account || undefined,
      tax_id: staffForm.value.tax_id || undefined,
      is_active: staffForm.value.is_active
    }
    if (editingStaffId.value) {
      await payroll.updateStaff(editingStaffId.value, payload)
    } else {
      await payroll.createStaff({ user_id: staffForm.value.user_id, ...payload })
    }
    showStaffModal.value = false
    await loadStaff()
  } finally {
    staffSaving.value = false
  }
}

// --- Periods tab ------------------------------------------------------------

const periods = ref<PayrollPeriod[]>([])
const periodsLoading = ref(false)
const selectedPeriod = ref<PayrollPeriod | null>(null)
const periodEntries = ref<PayrollEntry[]>([])

async function loadPeriods() {
  periodsLoading.value = true
  try {
    const res = await payroll.listPeriods()
    periods.value = res.data
  } finally {
    periodsLoading.value = false
  }
}

const periodColumns = [
  { accessorKey: 'month_year', header: t('payroll.periods.period') },
  { accessorKey: 'status', header: t('payroll.periods.status') },
  { accessorKey: 'actions', header: '' }
]

const showNewPeriodModal = ref(false)
const newPeriod = ref({ month: new Date().getMonth() + 1, year: new Date().getFullYear() })
const creatingPeriod = ref(false)

async function submitNewPeriod() {
  creatingPeriod.value = true
  try {
    await payroll.createPeriod(newPeriod.value.month, newPeriod.value.year)
    showNewPeriodModal.value = false
    await loadPeriods()
  } finally {
    creatingPeriod.value = false
  }
}

async function viewEntries(period: PayrollPeriod) {
  selectedPeriod.value = period
  periodEntries.value = await payroll.listPeriodEntries(period.id)
}

async function generate(period: PayrollPeriod) {
  await payroll.generateEntries(period.id)
  await viewEntries(period)
}

async function process(period: PayrollPeriod) {
  await payroll.processPeriod(period.id)
  await loadPeriods()
}

async function markPaid(period: PayrollPeriod) {
  await payroll.markPeriodPaid(period.id)
  await loadPeriods()
}

const entryColumns = [
  { accessorKey: 'staff_payroll_profile_id', header: t('payroll.entries.staff') },
  { accessorKey: 'gross_pay', header: t('payroll.entries.gross') },
  { accessorKey: 'deductions', header: t('payroll.entries.deductions') },
  { accessorKey: 'net_pay', header: t('payroll.entries.net') },
  { accessorKey: 'is_paid', header: t('payroll.entries.paid') },
  { accessorKey: 'actions', header: '' }
]

const editingEntry = ref<PayrollEntry | null>(null)
const entryForm = ref({ gross_pay: 0, deductions: 0 })

function openEditEntry(entry: PayrollEntry) {
  editingEntry.value = entry
  entryForm.value = { gross_pay: Number(entry.gross_pay), deductions: Number(entry.deductions) }
}

async function submitEntry() {
  if (!editingEntry.value) return
  await payroll.updateEntry(editingEntry.value.id, {
    staff_payroll_profile_id: editingEntry.value.staff_payroll_profile_id,
    gross_pay: entryForm.value.gross_pay,
    deductions: entryForm.value.deductions
  })
  editingEntry.value = null
  if (selectedPeriod.value) await viewEntries(selectedPeriod.value)
}

async function payEntry(entry: PayrollEntry) {
  await payroll.markEntryPaid(entry.id)
  if (selectedPeriod.value) await viewEntries(selectedPeriod.value)
}

// --- Reports tab -------------------------------------------------------------

const reportMonth = ref(new Date().getMonth() + 1)
const reportYear = ref(new Date().getFullYear())
const monthly = ref<MonthlySummary | null>(null)
const annual = ref<AnnualSummary | null>(null)

async function loadMonthly() {
  monthly.value = await payroll.monthlySummary(reportMonth.value, reportYear.value)
}
async function loadAnnual() {
  annual.value = await payroll.annualSummary(reportYear.value)
}

onMounted(() => {
  loadStaff()
  loadPeriods()
  fetchClinicUsers()
})
</script>

<template>
  <div class="p-4 space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-h2 text-default">{{ t('payroll.title') }}</h1>
    </div>

    <div class="flex gap-2 border-b pb-2">
      <UButton :variant="activeTab === 'employees' ? 'solid' : 'ghost'" @click="activeTab = 'employees'">
        {{ t('payroll.tabs.employees') }}
      </UButton>
      <UButton :variant="activeTab === 'periods' ? 'solid' : 'ghost'" @click="activeTab = 'periods'">
        {{ t('payroll.tabs.periods') }}
      </UButton>
      <UButton :variant="activeTab === 'reports' ? 'solid' : 'ghost'" @click="activeTab = 'reports'">
        {{ t('payroll.tabs.reports') }}
      </UButton>
    </div>

    <!-- Employees -->
    <div v-if="activeTab === 'employees'" class="space-y-4">
      <div class="flex justify-end">
        <UButton v-if="canWrite" icon="i-lucide-plus" @click="openCreateStaff">
          {{ t('payroll.staff.add') }}
        </UButton>
      </div>
      <UTable :data="staff" :columns="staffColumns" :loading="staffLoading">
        <template #base_salary-cell="{ row }">{{ row.original.base_salary ?? '—' }}</template>
        <template #hourly_rate-cell="{ row }">{{ row.original.hourly_rate ?? '—' }}</template>
        <template #tax_regime-cell="{ row }">{{ row.original.tax_regime ?? '—' }}</template>
        <template #bank_tax-cell="{ row }">
          <UBadge v-if="row.original.has_bank_account" color="success" variant="soft">{{ t('payroll.staff.bank') }}</UBadge>
          <UBadge v-if="row.original.has_tax_id" color="success" variant="soft">{{ t('payroll.staff.tax') }}</UBadge>
        </template>
        <template #is_active-cell="{ row }">
          <UBadge :color="row.original.is_active ? 'success' : 'neutral'">
            {{ t(row.original.is_active ? 'payroll.staff.active' : 'payroll.staff.inactive') }}
          </UBadge>
        </template>
        <template #actions-cell="{ row }">
          <UButton v-if="canWrite" icon="i-lucide-pencil" variant="ghost" size="xs" @click="openEditStaff(row.original)" />
        </template>
      </UTable>
    </div>

    <!-- Periods -->
    <div v-else-if="activeTab === 'periods'" class="space-y-4">
      <div class="flex justify-end">
        <UButton v-if="canWrite" icon="i-lucide-plus" @click="showNewPeriodModal = true">
          {{ t('payroll.periods.add') }}
        </UButton>
      </div>
      <UTable :data="periods" :columns="periodColumns" :loading="periodsLoading">
        <template #month_year-cell="{ row }">{{ row.original.month }}/{{ row.original.year }}</template>
        <template #status-cell="{ row }">
          <UBadge :color="row.original.status === 'paid' ? 'success' : row.original.status === 'processed' ? 'info' : 'neutral'">
            {{ t(`payroll.periods.statusValues.${row.original.status}`) }}
          </UBadge>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex gap-1">
            <UButton icon="i-lucide-eye" variant="ghost" size="xs" @click="viewEntries(row.original)" />
            <template v-if="canWrite && row.original.status === 'draft'">
              <UButton icon="i-lucide-list-plus" variant="ghost" size="xs" @click="generate(row.original)" />
              <UButton icon="i-lucide-check" variant="ghost" size="xs" @click="process(row.original)" />
            </template>
            <UButton
              v-if="canWrite && row.original.status === 'processed'"
              icon="i-lucide-banknote"
              variant="ghost"
              size="xs"
              @click="markPaid(row.original)"
            />
          </div>
        </template>
      </UTable>

      <div v-if="selectedPeriod" class="space-y-2">
        <h2 class="text-h3 text-default">
          {{ t('payroll.entries.title') }} — {{ selectedPeriod.month }}/{{ selectedPeriod.year }}
        </h2>
        <UTable :data="periodEntries" :columns="entryColumns">
          <template #is_paid-cell="{ row }">
            <UBadge :color="row.original.is_paid ? 'success' : 'neutral'">
              {{ t(row.original.is_paid ? 'payroll.entries.paidYes' : 'payroll.entries.paidNo') }}
            </UBadge>
          </template>
          <template #actions-cell="{ row }">
            <div class="flex gap-1">
              <UButton v-if="canWrite" icon="i-lucide-pencil" variant="ghost" size="xs" @click="openEditEntry(row.original)" />
              <UButton v-if="canWrite && !row.original.is_paid" icon="i-lucide-banknote" variant="ghost" size="xs" @click="payEntry(row.original)" />
            </div>
          </template>
        </UTable>
      </div>
    </div>

    <!-- Reports -->
    <div v-else class="space-y-6">
      <div class="space-y-2">
        <h2 class="text-h3 text-default">{{ t('payroll.reports.monthly') }}</h2>
        <div class="flex gap-2 items-end">
          <UInput v-model.number="reportMonth" type="number" min="1" max="12" :placeholder="t('payroll.reports.month')" class="w-24" />
          <UInput v-model.number="reportYear" type="number" :placeholder="t('payroll.reports.year')" class="w-28" />
          <UButton @click="loadMonthly">{{ t('payroll.reports.run') }}</UButton>
        </div>
        <div v-if="monthly" class="grid grid-cols-4 gap-4 pt-2">
          <div><div class="text-dimmed text-sm">{{ t('payroll.reports.gross') }}</div><div class="text-lg">{{ monthly.total_gross }}</div></div>
          <div><div class="text-dimmed text-sm">{{ t('payroll.reports.deductions') }}</div><div class="text-lg">{{ monthly.total_deductions }}</div></div>
          <div><div class="text-dimmed text-sm">{{ t('payroll.reports.net') }}</div><div class="text-lg">{{ monthly.total_net }}</div></div>
          <div><div class="text-dimmed text-sm">{{ t('payroll.reports.employees') }}</div><div class="text-lg">{{ monthly.employee_count }}</div></div>
        </div>
      </div>

      <div class="space-y-2">
        <h2 class="text-h3 text-default">{{ t('payroll.reports.annual') }}</h2>
        <div class="flex gap-2 items-end">
          <UInput v-model.number="reportYear" type="number" :placeholder="t('payroll.reports.year')" class="w-28" />
          <UButton @click="loadAnnual">{{ t('payroll.reports.run') }}</UButton>
        </div>
        <div v-if="annual" class="grid grid-cols-4 gap-4 pt-2">
          <div><div class="text-dimmed text-sm">{{ t('payroll.reports.gross') }}</div><div class="text-lg">{{ annual.total_gross }}</div></div>
          <div><div class="text-dimmed text-sm">{{ t('payroll.reports.deductions') }}</div><div class="text-lg">{{ annual.total_deductions }}</div></div>
          <div><div class="text-dimmed text-sm">{{ t('payroll.reports.net') }}</div><div class="text-lg">{{ annual.total_net }}</div></div>
          <div><div class="text-dimmed text-sm">{{ t('payroll.reports.monthsProcessed') }}</div><div class="text-lg">{{ annual.months_processed }}</div></div>
        </div>
      </div>
    </div>

    <!-- Staff modal -->
    <UModal v-model:open="showStaffModal">
      <template #content>
        <div class="p-4 space-y-3">
          <h2 class="text-h3 text-default">
            {{ editingStaffId ? t('payroll.staff.edit') : t('payroll.staff.add') }}
          </h2>
          <USelectMenu
            v-if="!editingStaffId"
            v-model="selectedStaffUser"
            :items="staffUserOptions"
            label-key="label"
            searchable
            :placeholder="t('payroll.staff.selectUser')"
          />
          <UInput v-model.number="staffForm.base_salary" type="number" step="0.01" :placeholder="t('payroll.staff.baseSalary')" />
          <UInput v-model.number="staffForm.hourly_rate" type="number" step="0.01" :placeholder="t('payroll.staff.hourlyRate')" />
          <UInput v-model="staffForm.tax_regime" :placeholder="t('payroll.staff.taxRegime')" />
          <UInput v-model="staffForm.bank_account" type="password" :placeholder="t('payroll.staff.bankAccountPlaceholder')" />
          <UInput v-model="staffForm.tax_id" type="password" :placeholder="t('payroll.staff.taxIdPlaceholder')" />
          <div class="flex justify-end gap-2 pt-2">
            <UButton variant="ghost" @click="showStaffModal = false">{{ t('actions.cancel') }}</UButton>
            <UButton :loading="staffSaving" @click="submitStaff">{{ t('actions.save') }}</UButton>
          </div>
        </div>
      </template>
    </UModal>

    <!-- New period modal -->
    <UModal v-model:open="showNewPeriodModal">
      <template #content>
        <div class="p-4 space-y-3">
          <h2 class="text-h3 text-default">{{ t('payroll.periods.add') }}</h2>
          <UInput v-model.number="newPeriod.month" type="number" min="1" max="12" :placeholder="t('payroll.reports.month')" />
          <UInput v-model.number="newPeriod.year" type="number" :placeholder="t('payroll.reports.year')" />
          <div class="flex justify-end gap-2 pt-2">
            <UButton variant="ghost" @click="showNewPeriodModal = false">{{ t('actions.cancel') }}</UButton>
            <UButton :loading="creatingPeriod" @click="submitNewPeriod">{{ t('actions.save') }}</UButton>
          </div>
        </div>
      </template>
    </UModal>

    <!-- Edit entry modal -->
    <UModal :open="!!editingEntry" @update:open="(v) => { if (!v) editingEntry = null }">
      <template #content>
        <div class="p-4 space-y-3">
          <h2 class="text-h3 text-default">{{ t('payroll.entries.edit') }}</h2>
          <UInput v-model.number="entryForm.gross_pay" type="number" step="0.01" :placeholder="t('payroll.entries.gross')" />
          <UInput v-model.number="entryForm.deductions" type="number" step="0.01" :placeholder="t('payroll.entries.deductions')" />
          <div class="flex justify-end gap-2 pt-2">
            <UButton variant="ghost" @click="editingEntry = null">{{ t('actions.cancel') }}</UButton>
            <UButton @click="submitEntry">{{ t('actions.save') }}</UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
