<script setup lang="ts">
// One-page wizard for DPMF imports: upload → validate → preview → execute.
// Polls /jobs/{id} every 2s while a background step is running so the
// status, progress and error fields stay current without push.

import { computed, onUnmounted, ref } from 'vue'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

const { t } = useI18n()
const api = useApi()
const { can } = usePermissions()

type JobStatus
  = | 'uploaded'
    | 'validating'
    | 'validated'
    | 'previewing'
    | 'executing'
    | 'completed'
    | 'failed'

interface ImportJob {
  id: string
  status: JobStatus
  error: string | null
  original_filename: string
  file_size: number
  source_system: string | null
  format_version: string | null
  tenant_label: string | null
  total_entities: number
  processed_entities: number
}

interface ProfessionalPreviewBreakdown {
  deactivated_count: number
  agenda_orphan_count: number
  stale_24m_count: number
  no_activity_count: number
  by_role: Record<string, number>
}

interface EntityPreview {
  entity_type: string
  declared_count: number
  samples: Array<{ canonical_uuid: string, source_id: string, payload: Record<string, unknown> }>
  professional_breakdown?: ProfessionalPreviewBreakdown | null
}

interface PreviewResponse {
  job: ImportJob
  entities: EntityPreview[]
  warnings: Array<{ severity: string, code: string, message: string, entity_type: string | null }>
  files: { total: number, with_sha256: number, without_sha256: number }
  verifactu_data_detected: boolean
  verifactu_module_installed: boolean
}

interface ProposalSummary {
  total: number
  link: number
  fuzzy_link: number
  create: number
}

interface MappingProposal {
  id: string
  canonical_uuid: string
  source_label: string
  source_code: string | null
  source_tipo_odg: number | null
  proposed_action: string
  proposed_target_id: string | null
  proposed_target_label: string | null
  proposed_target_category_key: string | null
  proposed_score: number | null
  operator_action: string
}

const file = ref<File | null>(null)
const passphrase = ref('')
const uploading = ref(false)
const uploadError = ref('')

const job = ref<ImportJob | null>(null)
const preview = ref<PreviewResponse | null>(null)
const importFiscal = ref(false)
const minActivityMonths = ref(24)
const excludeAgendaOrphans = ref(true)
const excludeInactiveInSource = ref(true)
const excludeNonClinicalRoles = ref(false)
let pollHandle: ReturnType<typeof setInterval> | null = null

const professionalBreakdown = computed<ProfessionalPreviewBreakdown | null>(() => {
  const ep = preview.value?.entities.find(e => e.entity_type === 'professional')
  return ep?.professional_breakdown ?? null
})

const professionalTotal = computed<number>(() => {
  const ep = preview.value?.entities.find(e => e.entity_type === 'professional')
  return ep?.declared_count ?? 0
})

const proposalSummary = ref<ProposalSummary | null>(null)
const proposals = ref<MappingProposal[]>([])
const proposalsLoading = ref(false)
const proposalsBuilding = ref(false)
const proposalsError = ref('')
const bulkAcceptedNotice = ref<number | null>(null)

const canExecute = computed(() => can(PERMISSIONS.migrationImport.jobExecute))
const verifactuOptInVisible = computed(
  () => !!preview.value?.verifactu_data_detected && !!preview.value?.verifactu_module_installed
)

function onFileChange(evt: Event) {
  const input = evt.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
}

async function startUpload() {
  if (!file.value) return
  uploading.value = true
  uploadError.value = ''
  try {
    const formData = new FormData()
    formData.append('file', file.value)
    const res = await api.post<{ data: ImportJob }>('/api/v1/migration_import/jobs', formData)
    job.value = res.data
    await runValidate()
  } catch (err: unknown) {
    uploadError.value = errorMessage(err, t('migrationImport.upload.error'))
  } finally {
    uploading.value = false
  }
}

async function runValidate() {
  if (!job.value) return
  const res = await api.post<{ data: ImportJob }>(
    `/api/v1/migration_import/jobs/${job.value.id}/validate`,
    { passphrase: passphrase.value || null }
  )
  job.value = res.data
  if (job.value.status === 'validated') await loadPreview()
}

async function loadPreview() {
  if (!job.value) return
  const res = await api.post<{ data: PreviewResponse }>(
    `/api/v1/migration_import/jobs/${job.value.id}/preview`,
    { passphrase: passphrase.value || null }
  )
  preview.value = res.data
  job.value = res.data.job
}

async function execute() {
  if (!job.value || !canExecute.value) return
  await api.post(`/api/v1/migration_import/jobs/${job.value.id}/execute`, {
    import_fiscal_compliance: importFiscal.value,
    passphrase: passphrase.value || null,
    professional_min_activity_months: minActivityMonths.value,
    professional_exclude_agenda_orphans: excludeAgendaOrphans.value,
    professional_exclude_inactive_in_source: excludeInactiveInSource.value,
    professional_exclude_non_clinical_roles: excludeNonClinicalRoles.value
  })
  startPolling()
}

async function buildProposals() {
  if (!job.value) return
  proposalsBuilding.value = true
  proposalsError.value = ''
  try {
    const res = await api.post<{ data: ProposalSummary }>(
      `/api/v1/migration_import/jobs/${job.value.id}/proposals`,
      { passphrase: passphrase.value || null }
    )
    proposalSummary.value = res.data
    await loadProposals()
  } catch (err: unknown) {
    proposalsError.value = errorMessage(err, t('migrationImport.proposals.title'))
  } finally {
    proposalsBuilding.value = false
  }
}

async function loadProposals() {
  if (!job.value) return
  proposalsLoading.value = true
  try {
    const res = await api.get<{ data: MappingProposal[] }>(
      `/api/v1/migration_import/jobs/${job.value.id}/proposals?page_size=200`
    )
    proposals.value = res.data
  } finally {
    proposalsLoading.value = false
  }
}

async function bulkAccept() {
  if (!job.value) return
  const res = await api.post<{ data: { accepted: number } }>(
    `/api/v1/migration_import/jobs/${job.value.id}/proposals/bulk_accept`,
    { min_score: 0.9, include_exact: true }
  )
  bulkAcceptedNotice.value = res.data.accepted
  await loadProposals()
}

async function patchProposal(proposal: MappingProposal, operatorAction: string) {
  if (!job.value) return
  await api.patch<{ data: MappingProposal }>(
    `/api/v1/migration_import/jobs/${job.value.id}/proposals/${proposal.canonical_uuid}`,
    { operator_action: operatorAction }
  )
  await loadProposals()
}

function scoreBadgeColor(score: number | null): string {
  if (score === null) return 'gray'
  if (score >= 0.9) return 'green'
  if (score >= 0.8) return 'blue'
  return 'amber'
}

function operatorStatusKey(action: string): string {
  switch (action) {
    case 'accepted':
      return 'migrationImport.proposals.operatorAccepted'
    case 'relinked':
      return 'migrationImport.proposals.operatorRelinked'
    case 'create_new':
      return 'migrationImport.proposals.operatorCreated'
    case 'ignored':
      return 'migrationImport.proposals.operatorIgnored'
    default:
      return 'migrationImport.proposals.operatorPending'
  }
}

function startPolling() {
  if (pollHandle) clearInterval(pollHandle)
  pollHandle = setInterval(async () => {
    if (!job.value) return
    const res = await api.get<{ data: ImportJob }>(`/api/v1/migration_import/jobs/${job.value.id}`)
    job.value = res.data
    if (job.value.status === 'completed' || job.value.status === 'failed') {
      if (pollHandle) {
        clearInterval(pollHandle)
        pollHandle = null
      }
    }
  }, 2000)
}

onUnmounted(() => {
  if (pollHandle) clearInterval(pollHandle)
})
</script>

<template>
  <div class="space-y-6">
    <header>
      <h2 class="text-xl font-semibold">
        {{ t('migrationImport.page.title') }}
      </h2>
      <p class="text-sm text-gray-500">
        {{ t('migrationImport.page.subtitle') }}
      </p>
    </header>

    <!-- Upload step -->
    <UCard v-if="!job">
      <div class="space-y-4">
        <UFormField :label="t('migrationImport.upload.dropFile')">
          <UInput
            type="file"
            accept=".dpm,.zst,.enc"
            @change="onFileChange"
          />
        </UFormField>
        <UFormField
          :label="t('migrationImport.upload.passphrase')"
          :help="t('migrationImport.upload.passphraseHelp')"
        >
          <UInput
            v-model="passphrase"
            type="password"
          />
        </UFormField>
        <UAlert
          v-if="uploadError"
          color="red"
          :title="t('migrationImport.upload.error')"
          :description="uploadError"
        />
        <UButton
          :loading="uploading"
          :disabled="!file"
          @click="startUpload"
        >
          {{ t('migrationImport.upload.submit') }}
        </UButton>
      </div>
    </UCard>

    <!-- Status + validate/preview/execute -->
    <UCard v-else>
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <div>
            <p class="font-medium">
              {{ job.original_filename }}
            </p>
            <p class="text-xs text-gray-500">
              {{ job.source_system ?? '—' }} · {{ job.format_version ?? '—' }} ·
              {{ (job.file_size / 1024 / 1024).toFixed(1) }} MB
            </p>
          </div>
          <UBadge :color="job.status === 'failed' ? 'red' : job.status === 'completed' ? 'green' : 'blue'">
            {{ t(`migrationImport.status.${job.status}`) }}
          </UBadge>
        </div>
        <UAlert
          v-if="job.error"
          color="red"
          :description="job.error"
        />
      </div>

      <!-- Preview -->
      <div
        v-if="preview"
        class="mt-6 space-y-4"
      >
        <div>
          <h3 class="font-semibold">
            {{ t('migrationImport.preview.entities') }}
          </h3>
          <ul class="mt-2 text-sm">
            <li
              v-for="ent in preview.entities"
              :key="ent.entity_type"
              class="flex justify-between border-b py-1"
            >
              <span>{{ ent.entity_type }}</span>
              <span class="font-mono">{{ ent.declared_count }}</span>
            </li>
          </ul>
        </div>

        <div>
          <h3 class="font-semibold">
            {{ t('migrationImport.preview.files') }}
          </h3>
          <p class="text-sm">
            {{ t('migrationImport.preview.filesTotal') }}: {{ preview.files.total }} ·
            {{ t('migrationImport.preview.filesWithSha') }}: {{ preview.files.with_sha256 }} ·
            {{ t('migrationImport.preview.filesWithoutSha') }}: {{ preview.files.without_sha256 }}
          </p>
        </div>

        <div v-if="preview.warnings.length">
          <h3 class="font-semibold">
            {{ t('migrationImport.preview.warnings') }} ({{ preview.warnings.length }})
          </h3>
          <ul class="mt-2 max-h-48 overflow-y-auto text-xs">
            <li
              v-for="(w, i) in preview.warnings"
              :key="i"
              class="border-b py-1"
            >
              [{{ w.severity }}] {{ w.code }} — {{ w.message }}
            </li>
          </ul>
        </div>

        <!-- Catalog mapping proposals -->
        <div class="mt-2 rounded border border-amber-200 bg-amber-50 p-4">
          <h3 class="font-semibold">
            {{ t('migrationImport.proposals.title') }}
          </h3>
          <p class="text-sm text-gray-700">
            {{ t('migrationImport.proposals.subtitle') }}
          </p>
          <div class="mt-3 flex gap-2">
            <UButton
              :loading="proposalsBuilding"
              :disabled="!canExecute"
              variant="outline"
              @click="buildProposals"
            >
              {{ proposalsBuilding ? t('migrationImport.proposals.building') : t('migrationImport.proposals.build') }}
            </UButton>
            <UButton
              v-if="proposalSummary"
              variant="ghost"
              :disabled="!canExecute"
              @click="bulkAccept"
            >
              {{ t('migrationImport.proposals.bulkAccept') }}
            </UButton>
          </div>
          <UAlert
            v-if="proposalsError"
            color="red"
            :description="proposalsError"
            class="mt-2"
          />
          <p
            v-if="proposalSummary"
            class="mt-2 text-xs text-gray-600"
          >
            {{
              t('migrationImport.proposals.summary', {
                total: proposalSummary.total,
                link: proposalSummary.link,
                fuzzy: proposalSummary.fuzzy_link,
                create: proposalSummary.create
              })
            }}
          </p>
          <p
            v-if="bulkAcceptedNotice !== null"
            class="text-xs text-green-700"
          >
            {{ t('migrationImport.proposals.accepted', { n: bulkAcceptedNotice }) }}
          </p>

          <!-- Proposals table -->
          <div
            v-if="proposals.length"
            class="mt-3 max-h-96 overflow-auto rounded border border-gray-200 bg-white"
          >
            <table class="w-full text-xs">
              <thead class="sticky top-0 bg-gray-100">
                <tr>
                  <th class="px-2 py-1 text-left">
                    {{ t('migrationImport.proposals.columnSource') }}
                  </th>
                  <th class="px-2 py-1 text-left">
                    {{ t('migrationImport.proposals.columnProposed') }}
                  </th>
                  <th class="px-2 py-1 text-left">
                    {{ t('migrationImport.proposals.columnStatus') }}
                  </th>
                  <th class="px-2 py-1 text-left">
                    {{ t('migrationImport.proposals.columnAction') }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="p in proposals"
                  :key="p.id"
                  class="border-t"
                >
                  <td class="px-2 py-1">
                    <div class="font-medium">
                      {{ p.source_label }}
                    </div>
                    <div class="text-[10px] text-gray-500">
                      <span v-if="p.source_code">{{ p.source_code }} · </span>
                      <span v-if="p.source_tipo_odg">IdTipoODG={{ p.source_tipo_odg }}</span>
                    </div>
                  </td>
                  <td class="px-2 py-1">
                    <div
                      v-if="p.proposed_action === 'create'"
                      class="italic text-gray-600"
                    >
                      {{ t('migrationImport.proposals.actionCreate') }}
                      <span
                        v-if="p.proposed_target_category_key"
                        class="text-[10px]"
                      >
                        → {{ p.proposed_target_category_key }}
                      </span>
                    </div>
                    <div v-else>
                      <div>{{ p.proposed_target_label }}</div>
                      <UBadge
                        v-if="p.proposed_score !== null"
                        :color="scoreBadgeColor(p.proposed_score)"
                        size="xs"
                      >
                        {{ (p.proposed_score * 100).toFixed(0) }}%
                      </UBadge>
                    </div>
                  </td>
                  <td class="px-2 py-1">
                    <UBadge
                      size="xs"
                      :color="p.operator_action === 'pending' ? 'gray' : 'green'"
                    >
                      {{ t(operatorStatusKey(p.operator_action)) }}
                    </UBadge>
                  </td>
                  <td class="px-2 py-1">
                    <div class="flex gap-1">
                      <UButton
                        size="xs"
                        variant="ghost"
                        :disabled="!canExecute || p.operator_action === 'accepted'"
                        @click="patchProposal(p, 'accepted')"
                      >
                        {{ t('migrationImport.proposals.acceptRow') }}
                      </UButton>
                      <UButton
                        size="xs"
                        color="red"
                        variant="ghost"
                        :disabled="!canExecute || p.operator_action === 'ignored'"
                        @click="patchProposal(p, 'ignored')"
                      >
                        {{ t('migrationImport.proposals.ignoreRow') }}
                      </UButton>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <UFormField
          v-if="verifactuOptInVisible"
          :help="t('migrationImport.preview.verifactuHelp')"
        >
          <UCheckbox
            v-model="importFiscal"
            :label="t('migrationImport.preview.verifactuCheckbox')"
          />
        </UFormField>

        <div
          v-if="professionalTotal > 0"
          class="rounded-lg border border-(--ui-border) bg-(--ui-bg-muted) p-4 space-y-3"
        >
          <div>
            <h3 class="text-sm font-semibold text-(--ui-text-highlighted)">
              {{ t('migrationImport.filters.title') }}
            </h3>
            <p class="text-xs text-(--ui-text-muted)">
              {{ t('migrationImport.filters.description') }}
            </p>
          </div>

          <div
            v-if="professionalBreakdown"
            class="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs"
          >
            <div>
              <span class="text-(--ui-text-muted)">{{ t('migrationImport.filters.totalLabel') }}</span>
              <span class="ml-1 font-medium">{{ professionalTotal }}</span>
            </div>
            <div>
              <span class="text-(--ui-text-muted)">{{ t('migrationImport.filters.deactivatedLabel') }}</span>
              <span class="ml-1 font-medium">{{ professionalBreakdown.deactivated_count }}</span>
            </div>
            <div>
              <span class="text-(--ui-text-muted)">{{ t('migrationImport.filters.orphansLabel') }}</span>
              <span class="ml-1 font-medium">{{ professionalBreakdown.agenda_orphan_count }}</span>
            </div>
            <div>
              <span class="text-(--ui-text-muted)">{{ t('migrationImport.filters.stale24mLabel') }}</span>
              <span class="ml-1 font-medium">{{ professionalBreakdown.stale_24m_count }}</span>
            </div>
          </div>

          <UFormField
            :label="t('migrationImport.filters.minActivityLabel')"
            :help="t('migrationImport.filters.minActivityHelp')"
          >
            <UInput
              v-model.number="minActivityMonths"
              type="number"
              :min="0"
              :max="120"
              :step="1"
              class="w-32"
            />
          </UFormField>

          <div class="space-y-2">
            <UCheckbox
              v-model="excludeAgendaOrphans"
              :label="t('migrationImport.filters.excludeOrphans')"
            />
            <UCheckbox
              v-model="excludeInactiveInSource"
              :label="t('migrationImport.filters.excludeInactive')"
            />
            <UCheckbox
              v-model="excludeNonClinicalRoles"
              :label="t('migrationImport.filters.excludeNonClinical')"
            />
          </div>
        </div>

        <UAlert
          color="amber"
          :description="t('migrationImport.preview.warning')"
        />

        <UButton
          color="primary"
          :disabled="!canExecute || job.status === 'executing'"
          @click="execute"
        >
          {{ t('migrationImport.preview.confirm') }}
        </UButton>
      </div>

      <!-- Progress -->
      <div
        v-if="job.status === 'executing'"
        class="mt-6"
      >
        <p class="text-sm">
          {{ t('migrationImport.execute.progress', { processed: job.processed_entities, total: job.total_entities }) }}
        </p>
      </div>
    </UCard>
  </div>
</template>
