<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold">
        {{ t('payroll.reports.title') }}
      </h1>
      <p class="text-sm text-muted-foreground">
        {{ t('payroll.reports.subtitle') }}
      </p>
    </div>

    <div class="grid gap-6 md:grid-cols-2">
      <UCard>
        <template #header>
          <h2 class="font-medium">
            {{ t('payroll.reports.monthly') }}
          </h2>
        </template>
        <div class="space-y-4">
          <UFormField :label="t('payroll.reports.month')">
            <UInput
              v-model="month"
              placeholder="YYYY-MM"
              pattern="\d{4}-(0[1-9]|1[0-2])"
              class="w-full"
            />
          </UFormField>
          <UButton
            v-if="can(PERMISSIONS.payroll.reportsRead)"
            :disabled="!monthValid"
            :loading="loadingMonthly"
            @click="fetchMonthly"
          >
            {{ t('payroll.reports.monthly') }}
          </UButton>
          <dl
            v-if="monthly"
            class="space-y-1 text-sm"
          >
            <div class="flex justify-between">
              <dt>{{ t('payroll.reports.entryCount') }}</dt>
              <dd>{{ monthly.entry_count }}</dd>
            </div>
            <div class="flex justify-between">
              <dt>{{ t('payroll.reports.totalGross') }}</dt>
              <dd dir="ltr">
                {{ monthly.total_gross }} {{ monthly.currency }}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt>{{ t('payroll.reports.totalDeductions') }}</dt>
              <dd dir="ltr">
                {{ monthly.total_deductions }} {{ monthly.currency }}
              </dd>
            </div>
            <div class="flex justify-between font-medium">
              <dt>{{ t('payroll.reports.totalNet') }}</dt>
              <dd dir="ltr">
                {{ monthly.total_net }} {{ monthly.currency }}
              </dd>
            </div>
          </dl>
        </div>
      </UCard>

      <UCard>
        <template #header>
          <h2 class="font-medium">
            {{ t('payroll.reports.annual') }}
          </h2>
        </template>
        <div class="space-y-4">
          <UFormField :label="t('payroll.reports.year')">
            <UInput
              v-model="year"
              placeholder="YYYY"
              pattern="\d{4}"
              class="w-full"
            />
          </UFormField>
          <UButton
            v-if="can(PERMISSIONS.payroll.reportsRead)"
            :disabled="!yearValid"
            :loading="loadingAnnual"
            @click="fetchAnnual"
          >
            {{ t('payroll.reports.annual') }}
          </UButton>
          <dl
            v-if="annual"
            class="space-y-1 text-sm"
          >
            <div class="flex justify-between">
              <dt>{{ t('payroll.reports.periodCount') }}</dt>
              <dd>{{ annual.period_count }}</dd>
            </div>
            <div class="flex justify-between">
              <dt>{{ t('payroll.reports.entryCount') }}</dt>
              <dd>{{ annual.entry_count }}</dd>
            </div>
            <div class="flex justify-between">
              <dt>{{ t('payroll.reports.totalGross') }}</dt>
              <dd dir="ltr">
                {{ annual.total_gross }} {{ annual.currency }}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt>{{ t('payroll.reports.totalDeductions') }}</dt>
              <dd dir="ltr">
                {{ annual.total_deductions }} {{ annual.currency }}
              </dd>
            </div>
            <div class="flex justify-between font-medium">
              <dt>{{ t('payroll.reports.totalNet') }}</dt>
              <dd dir="ltr">
                {{ annual.total_net }} {{ annual.currency }}
              </dd>
            </div>
          </dl>
        </div>
      </UCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'
import type { AnnualReport, PeriodReport } from '../../../composables/usePayroll'

const { t } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const { monthlyReport, annualReport } = usePayroll()

const month = ref('')
const year = ref(String(new Date().getFullYear()))
const monthly = ref<PeriodReport | null>(null)
const annual = ref<AnnualReport | null>(null)
const loadingMonthly = ref(false)
const loadingAnnual = ref(false)

const monthValid = computed(() => /^\d{4}-(0[1-9]|1[0-2])$/.test(month.value))
const yearValid = computed(() => /^\d{4}$/.test(year.value))

function fail(e: unknown) {
  toast.add({ title: t('payroll.common.loadError'), description: errorMessage(e, ''), color: 'error' })
}

async function fetchMonthly() {
  if (!monthValid.value) return
  loadingMonthly.value = true
  try {
    monthly.value = (await monthlyReport(month.value)).data
  } catch (e) {
    monthly.value = null
    fail(e)
  } finally {
    loadingMonthly.value = false
  }
}

async function fetchAnnual() {
  if (!yearValid.value) return
  loadingAnnual.value = true
  try {
    annual.value = (await annualReport(year.value)).data
  } catch (e) {
    annual.value = null
    fail(e)
  } finally {
    loadingAnnual.value = false
  }
}
</script>
