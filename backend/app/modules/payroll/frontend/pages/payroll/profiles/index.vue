<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">
          {{ t('payroll.profiles.title') }}
        </h1>
        <p class="text-sm text-muted-foreground">
          {{ t('payroll.profiles.subtitle') }}
        </p>
      </div>
      <UButton
        v-if="can(PERMISSIONS.payroll.write)"
        icon="i-lucide-plus"
        @click="openCreate"
      >
        {{ t('payroll.profiles.new') }}
      </UButton>
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
      :actions="[{ label: t('payroll.common.retry'), onClick: fetchProfiles }]"
    />

    <UCard v-else-if="profiles.length === 0">
      <p class="text-sm text-muted-foreground">
        {{ t('payroll.profiles.empty') }}
      </p>
    </UCard>

    <div
      v-else
      class="space-y-2"
    >
      <UCard
        v-for="profile in profiles"
        :key="profile.id"
      >
        <div class="flex items-center justify-between gap-4">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <p class="font-medium truncate">
                {{ staffName(profile.user_id) }}
              </p>
              <UBadge
                color="primary"
                variant="soft"
              >
                {{ profile.payment_type === 'hourly' ? t('payroll.profiles.hourly') : t('payroll.profiles.monthly') }}
              </UBadge>
              <UBadge
                v-if="!profile.is_active"
                color="neutral"
                variant="soft"
              >
                {{ t('payroll.profiles.inactive') }}
              </UBadge>
            </div>
            <p class="text-sm text-muted-foreground truncate">
              {{ profile.base_amount ?? '—' }} {{ profile.currency }}
              <span v-if="profile.has_bank_account"> · {{ t('payroll.profiles.hasBank') }} (···{{ profile.bank_last_4 }})</span>
              <span v-if="profile.has_tax_id"> · {{ t('payroll.profiles.hasTax') }}</span>
            </p>
          </div>
          <div
            v-if="can(PERMISSIONS.payroll.write)"
            class="flex shrink-0 gap-2"
          >
            <UButton
              variant="ghost"
              icon="i-lucide-pencil"
              @click="openEdit(profile)"
            >
              {{ t('payroll.common.edit') }}
            </UButton>
          </div>
        </div>
      </UCard>

      <div class="flex justify-center pt-2">
        <UPagination
          v-model:page="currentPage"
          :items-per-page="pageSize"
          :total="total"
        />
      </div>
    </div>

    <UModal v-model:open="showForm">
      <template #content>
        <UCard>
          <div class="space-y-4">
            <UFormField
              v-if="!editing"
              :label="t('payroll.profiles.staff')"
            >
              <USelect
                v-model="form.user_id"
                :items="staffOptions"
                :placeholder="t('payroll.profiles.staffPlaceholder')"
                class="w-full"
              />
            </UFormField>
            <div class="grid grid-cols-2 gap-4">
              <UFormField :label="t('payroll.profiles.paymentType')">
                <USelect
                  v-model="form.payment_type"
                  :items="paymentTypeOptions"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="t('payroll.profiles.currency')">
                <UInput
                  v-model="form.currency"
                  maxlength="3"
                  class="w-full"
                />
              </UFormField>
            </div>
            <UFormField :label="t('payroll.profiles.baseAmount')">
              <UInput
                v-model="form.base_amount"
                type="number"
                min="0"
                step="0.01"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('payroll.profiles.bankAccount')">
              <UInput
                v-model="form.bank_account"
                :placeholder="editing ? t('payroll.profiles.bankAccountPlaceholder') : ''"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('payroll.profiles.taxId')">
              <UInput
                v-model="form.tax_id"
                :placeholder="editing ? t('payroll.profiles.taxIdPlaceholder') : ''"
                class="w-full"
              />
            </UFormField>
            <UCheckbox
              v-if="editing"
              v-model="form.is_active"
              :label="t('payroll.profiles.active')"
            />
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
  </div>
</template>

<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'
import type { PayrollProfile, StaffUser } from '../../../composables/usePayroll'

const { t } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const { listProfiles, createProfile, updateProfile, listStaff } = usePayroll()
const { currency: clinicCurrency } = useCurrency()

const profiles = ref<PayrollProfile[]>([])
const staff = ref<StaffUser[]>([])
const loading = ref(true)
const error = ref(false)
const saving = ref(false)
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)
const showForm = ref(false)
const editing = ref<PayrollProfile | null>(null)
const form = ref({
  user_id: '',
  payment_type: 'monthly' as 'monthly' | 'hourly',
  base_amount: '' as string,
  currency: clinicCurrency.value,
  bank_account: '',
  tax_id: '',
  is_active: true
})

const staffOptions = computed(() =>
  staff.value.map(u => ({
    label: `${u.last_name}, ${u.first_name} (${u.email})`,
    value: u.id
  }))
)

const paymentTypeOptions = computed(() => [
  { label: t('payroll.profiles.monthly'), value: 'monthly' },
  { label: t('payroll.profiles.hourly'), value: 'hourly' }
])

const formValid = computed(() => {
  if (!editing.value && !form.value.user_id) return false
  return true
})

function staffName(userId: string): string {
  const u = staff.value.find(s => s.id === userId)
  return u ? `${u.last_name}, ${u.first_name}` : userId
}

async function fetchProfiles() {
  loading.value = true
  error.value = false
  try {
    const [plist, slist] = await Promise.all([
      listProfiles(currentPage.value, pageSize),
      listStaff()
    ])
    profiles.value = plist.data
    total.value = plist.total
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
  form.value = {
    user_id: '',
    payment_type: 'monthly',
    base_amount: '',
    currency: clinicCurrency.value,
    bank_account: '',
    tax_id: '',
    is_active: true
  }
  showForm.value = true
}

function openEdit(profile: PayrollProfile) {
  editing.value = profile
  // Secrets are write-only: inputs start empty (leave empty to keep).
  form.value = {
    user_id: profile.user_id,
    payment_type: profile.payment_type,
    base_amount: profile.base_amount ?? '',
    currency: profile.currency,
    bank_account: '',
    tax_id: '',
    is_active: profile.is_active
  }
  showForm.value = true
}

async function save() {
  saving.value = true
  try {
    if (editing.value) {
      const payload: Record<string, unknown> = {
        payment_type: form.value.payment_type,
        currency: form.value.currency,
        is_active: form.value.is_active
      }
      if (form.value.base_amount !== '') payload.base_amount = form.value.base_amount
      // Replace-to-edit: only send secrets when filled.
      if (form.value.bank_account !== '') payload.bank_account = form.value.bank_account
      if (form.value.tax_id !== '') payload.tax_id = form.value.tax_id
      await updateProfile(editing.value.id, payload)
    } else {
      const payload: Record<string, unknown> = {
        user_id: form.value.user_id,
        payment_type: form.value.payment_type,
        currency: form.value.currency
      }
      if (form.value.base_amount !== '') payload.base_amount = form.value.base_amount
      if (form.value.bank_account !== '') payload.bank_account = form.value.bank_account
      if (form.value.tax_id !== '') payload.tax_id = form.value.tax_id
      await createProfile(payload as never)
    }
    showForm.value = false
    await fetchProfiles()
  } catch (e) {
    toast.add({ title: t('payroll.common.saveError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

watch(currentPage, fetchProfiles)

onMounted(fetchProfiles)
</script>
