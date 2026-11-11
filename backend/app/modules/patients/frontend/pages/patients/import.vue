<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'
import {
  CSV_IMPORT_COLUMNS,
  CSV_IMPORT_MAX_ROWS,
  CSV_IMPORT_REQUIRED_COLUMNS,
  csvImportTemplate,
  usePatientCsvImport,
  type CsvRowDuplicate,
  type PatientImportReport
} from '../../composables/usePatientCsvImport'

/**
 * /patients/import — CSV patient import (#819).
 *
 * Wraps ``POST /api/v1/patients/import.csv`` in three steps: check the
 * file (the endpoint's dry run, nothing written), confirm, and show what
 * was created. Validation, duplicate detection and the caps all live on
 * the server; this page only presents the report.
 */

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const csvImport = usePatientCsvImport()

if (!can(PERMISSIONS.patients.write)) {
  await navigateTo('/patients')
}

const optionalColumns = CSV_IMPORT_COLUMNS.filter(
  c => !(CSV_IMPORT_REQUIRED_COLUMNS as readonly string[]).includes(c)
)

const file = ref<File | null>(null)
const report = ref<PatientImportReport | null>(null)
const result = ref<PatientImportReport | null>(null)
const allowDuplicates = ref(false)
const checking = ref(false)
const importing = ref(false)
const fileError = ref('')
// Bumped to remount the file input, which is the only way to clear it.
const inputKey = ref(0)

function onFileChange(evt: Event) {
  const input = evt.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
  // A report belongs to the file it was made from.
  report.value = null
  allowDuplicates.value = false
  fileError.value = ''
}

async function check() {
  if (!file.value) return
  checking.value = true
  fileError.value = ''
  report.value = null
  try {
    report.value = await csvImport.check(file.value)
  } catch (err: unknown) {
    fileError.value = errorMessage(err, t('patients.import.checkFailed'))
  } finally {
    checking.value = false
  }
}

/** Rows the commit will create: valid ones, minus duplicates unless allowed. */
const toCreate = computed(() => {
  if (!report.value) return 0
  return allowDuplicates.value
    ? report.value.valid
    : report.value.valid - report.value.duplicates.length
})

async function commit() {
  if (!file.value || !toCreate.value) return
  importing.value = true
  fileError.value = ''
  try {
    result.value = await csvImport.commit(file.value, allowDuplicates.value)
    report.value = null
  } catch (err: unknown) {
    fileError.value = errorMessage(err, t('patients.import.commitFailed'))
  } finally {
    importing.value = false
  }
}

function reset() {
  file.value = null
  report.value = null
  result.value = null
  allowDuplicates.value = false
  fileError.value = ''
  inputKey.value++
}

function downloadTemplate() {
  const blob = new Blob([csvImportTemplate()], { type: 'text/csv;charset=utf-8' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'patients_template.csv'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

function matchedOnLabel(dup: CsvRowDuplicate): string {
  if (dup.matched_on === 'national_id') return t('patients.import.matchedOn.nationalId')
  if (dup.matched_on === 'email+date_of_birth') return t('patients.import.matchedOn.emailAndBirthDate')
  if (dup.matched_on === 'same_file') return t('patients.import.matchedOn.sameFile')
  return dup.matched_on
}
</script>

<template>
  <div class="container mx-auto p-4 space-y-4 max-w-4xl">
    <div>
      <UButton
        to="/patients"
        variant="link"
        color="neutral"
        icon="i-lucide-arrow-left"
        class="px-0"
      >
        {{ t('patients.import.back') }}
      </UButton>
      <PageHeader
        :title="t('patients.import.title')"
        :subtitle="t('patients.import.subtitle')"
      />
    </div>

    <!-- Done -->
    <UCard v-if="result">
      <div class="space-y-4">
        <UAlert
          color="success"
          variant="subtle"
          icon="i-lucide-circle-check"
          :title="t('patients.import.done.title')"
          :description="t('patients.import.done.summary', { created: result.created, skipped: result.skipped })"
        />
        <p
          v-if="result.errors.length"
          class="text-sm text-subtle"
        >
          {{ t('patients.import.done.notImported', { count: result.errors.length }) }}
        </p>
        <div class="flex flex-wrap gap-2">
          <UButton
            to="/patients"
            color="primary"
          >
            {{ t('patients.import.done.goToList') }}
          </UButton>
          <UButton
            variant="soft"
            color="neutral"
            @click="reset"
          >
            {{ t('patients.import.done.another') }}
          </UButton>
        </div>
      </div>
    </UCard>

    <template v-else>
      <!-- Upload -->
      <UCard>
        <div class="space-y-4">
          <div class="space-y-2 text-sm">
            <h2 class="text-h2">
              {{ t('patients.import.format.title') }}
            </h2>
            <p>
              {{ t('patients.import.format.required') }}
              <code
                v-for="column in CSV_IMPORT_REQUIRED_COLUMNS"
                :key="column"
                class="mx-0.5"
              >{{ column }}</code>
            </p>
            <p>
              {{ t('patients.import.format.optional') }}
              <code
                v-for="column in optionalColumns"
                :key="column"
                class="mx-0.5"
              >{{ column }}</code>
            </p>
            <p class="text-subtle">
              {{ t('patients.import.format.rules') }}
            </p>
            <p class="text-subtle">
              {{ t('patients.import.format.limits', { rows: CSV_IMPORT_MAX_ROWS }) }}
            </p>
            <UButton
              variant="soft"
              color="neutral"
              size="sm"
              icon="i-lucide-download"
              @click="downloadTemplate"
            >
              {{ t('patients.import.format.template') }}
            </UButton>
          </div>

          <UFormField :label="t('patients.import.file')">
            <UInput
              :key="inputKey"
              type="file"
              accept=".csv,text/csv"
              @change="onFileChange"
            />
          </UFormField>

          <UAlert
            v-if="fileError"
            color="error"
            variant="subtle"
            icon="i-lucide-circle-alert"
            :description="fileError"
          />

          <UButton
            color="primary"
            icon="i-lucide-file-search"
            :disabled="!file"
            :loading="checking"
            @click="check"
          >
            {{ t('patients.import.check') }}
          </UButton>
        </div>
      </UCard>

      <!-- Report (dry run) -->
      <UCard v-if="report">
        <div class="space-y-4">
          <h2 class="text-h2">
            {{ t('patients.import.report.title') }}
          </h2>
          <dl class="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <dt class="text-xs text-subtle">
                {{ t('patients.import.report.total') }}
              </dt>
              <dd class="text-lg font-semibold">
                {{ report.total }}
              </dd>
            </div>
            <div>
              <dt class="text-xs text-subtle">
                {{ t('patients.import.report.valid') }}
              </dt>
              <dd class="text-lg font-semibold">
                {{ report.valid }}
              </dd>
            </div>
            <div>
              <dt class="text-xs text-subtle">
                {{ t('patients.import.report.errors') }}
              </dt>
              <dd class="text-lg font-semibold">
                {{ report.errors.length }}
              </dd>
            </div>
            <div>
              <dt class="text-xs text-subtle">
                {{ t('patients.import.report.duplicates') }}
              </dt>
              <dd class="text-lg font-semibold">
                {{ report.duplicates.length }}
              </dd>
            </div>
          </dl>

          <div
            v-if="report.errors.length"
            class="space-y-2"
          >
            <h3 class="font-medium">
              {{ t('patients.import.report.errorsTitle') }}
            </h3>
            <p class="text-sm text-subtle">
              {{ t('patients.import.report.errorsHint') }}
            </p>
            <ul class="text-sm divide-y divide-default border border-default rounded-md">
              <li
                v-for="error in report.errors"
                :key="`e-${error.row}`"
                class="px-3 py-2 flex gap-3"
              >
                <span class="text-subtle shrink-0">{{ t('patients.import.report.row', { row: error.row }) }}</span>
                <span class="break-words min-w-0">{{ error.message }}</span>
              </li>
            </ul>
          </div>

          <div
            v-if="report.duplicates.length"
            class="space-y-2"
          >
            <h3 class="font-medium">
              {{ t('patients.import.report.duplicatesTitle') }}
            </h3>
            <ul class="text-sm divide-y divide-default border border-default rounded-md">
              <li
                v-for="dup in report.duplicates"
                :key="`d-${dup.row}`"
                class="px-3 py-2 flex flex-wrap gap-x-3 gap-y-1"
              >
                <span class="text-subtle shrink-0">{{ t('patients.import.report.row', { row: dup.row }) }}</span>
                <span>{{ matchedOnLabel(dup) }}</span>
                <NuxtLink
                  v-if="dup.patient_id"
                  :to="`/patients/${dup.patient_id}`"
                  target="_blank"
                  class="text-primary underline"
                >
                  {{ t('patients.import.report.openPatient') }}
                </NuxtLink>
              </li>
            </ul>
            <UCheckbox
              v-model="allowDuplicates"
              :label="t('patients.import.report.allowDuplicates')"
              :description="t('patients.import.report.allowDuplicatesHelp')"
            />
          </div>

          <UAlert
            v-if="!toCreate"
            color="warning"
            variant="subtle"
            icon="i-lucide-triangle-alert"
            :description="t('patients.import.report.nothingToImport')"
          />
          <UButton
            v-else
            color="primary"
            icon="i-lucide-upload"
            :loading="importing"
            @click="commit"
          >
            {{ t('patients.import.report.commit', { count: toCreate }) }}
          </UButton>
        </div>
      </UCard>
    </template>
  </div>
</template>
