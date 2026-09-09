<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">
          {{ t('payroll.periods.title') }}
        </h1>
        <p class="text-sm text-muted-foreground">
          {{ t('payroll.periods.subtitle') }}
        </p>
      </div>
      <div
        v-if="can(PERMISSIONS.payroll.write)"
        class="flex gap-2"
      >
        <UInput
          v-model="newMonth"
          :placeholder="t('payroll.periods.month')"
          pattern="\d{4}-(0[1-9]|1[0-2])"
          class="w-40"
        />
        <UButton
          icon="i-lucide-plus"
          :disabled="!monthValid"
          :loading="saving"
          @click="openPeriod"
        >
          {{ t('payroll.periods.open') }}
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
      :actions="[{ label: t('payroll.common.retry'), onClick: fetchPeriods }]"
    />

    <UCard v-else-if="periods.length === 0">
      <p class="text-sm text-muted-foreground">
        {{ t('payroll.periods.empty') }}
      </p>
    </UCard>

    <div
      v-else
      class="space-y-2"
    >
      <UCard
        v-for="period in periods"
        :key="period.id"
      >
        <div class="flex items-center justify-between gap-4">
          <div class="min-w-0">
            <NuxtLink
              :to="`/payroll/periods/${period.id}`"
              class="font-medium text-primary-accent hover:underline"
            >
              {{ period.month }}
            </NuxtLink>
            <div class="mt-1">
              <UBadge
                :color="statusColor(period.status)"
                variant="soft"
              >
                {{ t(`payroll.periods.${period.status}`) }}
              </UBadge>
            </div>
          </div>
          <div
            v-if="can(PERMISSIONS.payroll.write)"
            class="flex shrink-0 gap-2"
          >
            <UButton
              v-if="period.status === 'draft'"
              variant="ghost"
              @click="askTransition(period, 'closed')"
            >
              {{ t('payroll.periods.close') }}
            </UButton>
            <UButton
              v-if="period.status === 'closed'"
              variant="ghost"
              @click="askTransition(period, 'paid')"
            >
              {{ t('payroll.periods.markPaid') }}
            </UButton>
            <UButton
              v-if="period.status === 'draft'"
              variant="ghost"
              color="error"
              icon="i-lucide-trash-2"
              @click="askDelete(period)"
            >
              {{ t('payroll.common.delete') }}
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

    <UModal v-model:open="showConfirm">
      <template #content>
        <UCard>
          <p class="text-sm">
            {{ t('payroll.periods.transitionConfirm', { month: pending?.month ?? '', status: pendingTo ? t(`payroll.periods.${pendingTo}`) : '' }) }}
          </p>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                @click="showConfirm = false"
              >
                {{ t('payroll.common.cancel') }}
              </UButton>
              <UButton
                :loading="saving"
                @click="confirmTransition"
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
            {{ t('payroll.periods.deleteConfirm', { month: deleting?.month ?? '' }) }}
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
                @click="removePeriod"
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
import type { PayrollPeriod, PayrollPeriodStatus } from '../../../composables/usePayroll'

const { t } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const { listPeriods, createPeriod, transitionPeriod, deletePeriod } = usePayroll()

const periods = ref<PayrollPeriod[]>([])
const loading = ref(true)
const error = ref(false)
const saving = ref(false)
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)
const newMonth = ref('')
const showConfirm = ref(false)
const showDelete = ref(false)
const deleting = ref<PayrollPeriod | null>(null)
const pending = ref<PayrollPeriod | null>(null)
const pendingTo = ref<PayrollPeriodStatus | null>(null)

const monthValid = computed(() => /^\d{4}-(0[1-9]|1[0-2])$/.test(newMonth.value))

function statusColor(status: string): 'success' | 'neutral' | 'primary' {
  if (status === 'paid') return 'success'
  if (status === 'closed') return 'neutral'
  return 'primary'
}

async function fetchPeriods() {
  loading.value = true
  error.value = false
  try {
    const response = await listPeriods(currentPage.value, pageSize)
    periods.value = response.data
    total.value = response.total
  } catch (e) {
    error.value = true
    toast.add({ title: t('payroll.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    loading.value = false
  }
}

async function openPeriod() {
  if (!monthValid.value) return
  saving.value = true
  try {
    await createPeriod(newMonth.value)
    newMonth.value = ''
    await fetchPeriods()
  } catch (e) {
    toast.add({ title: t('payroll.common.saveError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

function askTransition(period: PayrollPeriod, to: PayrollPeriodStatus) {
  pending.value = period
  pendingTo.value = to
  showConfirm.value = true
}

async function confirmTransition() {
  if (!pending.value || !pendingTo.value) return
  saving.value = true
  try {
    await transitionPeriod(pending.value.id, pendingTo.value)
    showConfirm.value = false
    pending.value = null
    pendingTo.value = null
    await fetchPeriods()
  } catch (e) {
    toast.add({ title: t('payroll.common.saveError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

function askDelete(period: PayrollPeriod) {
  deleting.value = period
  showDelete.value = true
}

async function removePeriod() {
  if (!deleting.value) return
  saving.value = true
  try {
    await deletePeriod(deleting.value.id)
    showDelete.value = false
    deleting.value = null
    await fetchPeriods()
  } catch (e) {
    // A period with entries refuses with 409 — the error renders.
    toast.add({ title: t('payroll.common.saveError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

watch(currentPage, fetchPeriods)

onMounted(fetchPeriods)
</script>
