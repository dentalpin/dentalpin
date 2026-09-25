<script setup lang="ts">
/**
 * Prescriptions page: per-patient list, draft editor (free-text lines,
 * template fill), issue/cancel actions, PDF download, safety banner.
 * Deep-linkable via ?patient_id= (&new=1 starts a draft).
 */
import type { Prescription, PrescriptionItem, PrescriptionTemplate } from '../../composables/usePrescriptions'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorDetail } from '~~/app/utils/error'

const { t, locale } = useI18n()
const { can } = usePermissions()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const {
  listForPatient, createDraft, updateDraft, issue, cancel, downloadPdf,
  getPatientName, getPrescriberProfile,
  warnings, listTemplates, createTemplate
} = usePrescriptions()

const canWrite = computed(() => can(PERMISSIONS.prescriptions.write))
const canIssue = computed(() => can(PERMISSIONS.prescriptions.issue))

const patientId = ref((route.query.patient_id as string) || '')
const patientName = ref<string | null>(null)
const prescriberLicense = ref<string | null>(null)
const items = ref<Prescription[]>([])
const isLoading = ref(false)
const allergyWarnings = ref<string[]>([])
const flagWarnings = ref<string[]>([])

const editing = ref<Prescription | null>(null)
const editItems = ref<DraftItem[]>([])
const editNotes = ref('')
const showEditor = ref(false)

const templates = ref<PrescriptionTemplate[]>([])
const newTemplateName = ref('')
const errorMessage = ref('')
const pendingConfirm = ref<{ kind: 'issue' | 'cancel', rx: Prescription } | null>(null)
const lastKind = ref<'issue' | 'cancel'>('issue')

function fail(e: unknown) {
  errorMessage.value = errorDetail(e) ?? String(e)
  toast.add({ title: t('prescriptions.title'), description: errorMessage.value, color: 'error' })
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium' }).format(new Date(iso))
}

async function refresh() {
  if (!patientId.value) return
  isLoading.value = true
  try {
    items.value = await listForPatient(patientId.value)
    const w = await warnings(patientId.value)
    allergyWarnings.value = w.allergies
    flagWarnings.value = w.interaction_flags
    templates.value = await listTemplates()
    patientName.value = await getPatientName(patientId.value)
  } finally {
    isLoading.value = false
  }
}

async function refreshProfile() {
  try {
    prescriberLicense.value = (await getPrescriberProfile())?.license_number || null
  } catch {
    prescriberLicense.value = null
  }
}

function startNew() {
  editing.value = null
  editItems.value = []
  editNotes.value = ''
  showEditor.value = true
  if (route.query.new === '1') void router.replace({ query: { ...route.query, new: undefined } })
}

/** Editor row: blankLine() normalizes the nullable API `route` to a plain string. */
type DraftItem = Omit<PrescriptionItem, 'route'> & { route?: string }

function blankLine(item: PrescriptionItem): DraftItem {
  return { ...item, dosage: item.dosage ?? '', unit: item.unit ?? '', route: item.route ?? '', frequency: item.frequency ?? '', duration: item.duration ?? '', instructions: item.instructions ?? '' }
}

function editDraft(rx: Prescription) {
  editing.value = rx
  editItems.value = rx.items.map(blankLine)
  editNotes.value = rx.notes || ''
  showEditor.value = true
}

function addLine() {
  editItems.value.push({ medication_name: '' })
}

function removeLine(idx: number) {
  editItems.value.splice(idx, 1)
}

function applyTemplate(tpl: PrescriptionTemplate) {
  editItems.value = tpl.items.map((i, idx) => ({ ...blankLine(i), sort_order: idx }))
}

async function save() {
  const clean = editItems.value.filter(i => i.medication_name.trim() !== '')
  errorMessage.value = ''
  if (clean.length === 0) {
    fail({ data: { message: t('prescriptions.emptyDraft') } })
    return
  }
  try {
    if (editing.value) {
      await updateDraft(editing.value.id, { notes: editNotes.value || null, items: clean })
    } else {
      await createDraft(patientId.value, clean, editNotes.value || undefined, locale.value)
    }
    showEditor.value = false
    await refresh()
  } catch (e: unknown) { fail(e) }
}

function askConfirm(kind: 'issue' | 'cancel', rx: Prescription) {
  lastKind.value = kind
  pendingConfirm.value = { kind, rx }
}

async function doConfirmed() {
  const pending = pendingConfirm.value
  if (!pending) return
  pendingConfirm.value = null
  errorMessage.value = ''
  try {
    if (pending.kind === 'issue') await issue(pending.rx.id)
    else await cancel(pending.rx.id)
    await refresh()
  } catch (e: unknown) { fail(e) }
}

async function downloadPdfFile(rx: Prescription) {
  errorMessage.value = ''
  try {
    const blob = await downloadPdf(rx.id)
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (e: unknown) { fail(e) }
}

async function saveAsTemplate() {
  const clean = editItems.value.filter(i => i.medication_name.trim() !== '')
  if (!newTemplateName.value.trim() || clean.length === 0) return
  await createTemplate(newTemplateName.value.trim(), clean)
  newTemplateName.value = ''
  templates.value = await listTemplates()
}

onMounted(() => {
  void refreshProfile()
  if (patientId.value) void refresh()
  if (route.query.new === '1' && patientId.value) startNew()
})
watch(patientId, () => void refresh())
</script>

<template>
  <div class="space-y-4 p-4">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-h2">
          {{ t('prescriptions.title') }}
        </h1>
        <p
          v-if="patientName"
          class="text-sm text-muted"
        >
          <NuxtLink
            :to="`/patients/${patientId}`"
            class="hover:text-default"
          >
            {{ patientName }}
          </NuxtLink>
        </p>
      </div>
      <UButton
        v-if="canWrite && patientId"
        icon="i-lucide-plus"
        @click="startNew"
      >
        {{ t('prescriptions.newPrescription') }}
      </UButton>
    </div>

    <UAlert
      v-if="allergyWarnings.length > 0 || flagWarnings.length > 0"
      color="warning"
      :title="t('prescriptions.safetyTitle')"
      :description="[...allergyWarnings, ...flagWarnings].join(' · ')"
    />

    <USkeleton
      v-if="isLoading"
      class="h-32"
    />
    <p
      v-else-if="!patientId"
      class="text-sm text-muted"
    >
      {{ t('prescriptions.pickPatient') }}
    </p>
    <p
      v-else-if="items.length === 0"
      class="text-sm text-muted"
    >
      {{ t('prescriptions.emptyHint') }}
    </p>
    <div
      v-else
      class="space-y-2"
    >
      <UCard
        v-for="rx in items"
        :key="rx.id"
      >
        <div class="flex items-center justify-between gap-2">
          <div>
            <span class="font-medium">{{ formatDate(rx.issued_at) }}</span>
            <span class="text-sm text-muted"> — {{ rx.items.length }} {{ t('prescriptions.items') }}</span>
          </div>
          <UBadge :color="rx.status === 'issued' ? 'success' : rx.status === 'cancelled' ? 'neutral' : 'warning'">
            {{ t(`prescriptions.status.${rx.status}`) }}
          </UBadge>
        </div>
        <ul class="mt-2 text-sm space-y-0.5">
          <li
            v-for="item in rx.items"
            :key="item.id"
          >
            {{ item.medication_name }}<span v-if="item.dosage"> — {{ item.dosage }} {{ item.unit || '' }}</span><span v-if="item.frequency">, {{ item.frequency }}</span><span v-if="item.duration"> × {{ item.duration }}</span>
          </li>
        </ul>
        <div
          v-if="rx.status === 'draft'"
          class="mt-2 flex flex-wrap gap-2"
        >
          <UButton
            v-if="canWrite"
            size="xs"
            color="neutral"
            variant="outline"
            @click="editDraft(rx)"
          >
            {{ t('prescriptions.edit') }}
          </UButton>
          <UButton
            v-if="canIssue"
            size="xs"
            @click="askConfirm('issue', rx)"
          >
            {{ t('prescriptions.issue') }}
          </UButton>
          <UButton
            v-if="canIssue"
            size="xs"
            color="neutral"
            variant="ghost"
            @click="askConfirm('cancel', rx)"
          >
            {{ t('prescriptions.cancel') }}
          </UButton>
        </div>
        <div
          v-else-if="rx.status === 'issued'"
          class="mt-2 flex flex-wrap gap-2"
        >
          <UButton
            size="xs"
            color="neutral"
            variant="outline"
            icon="i-lucide-download"
            @click="downloadPdfFile(rx)"
          >
            {{ t('prescriptions.downloadPdf') }}
          </UButton>
          <UButton
            v-if="canIssue"
            size="xs"
            color="neutral"
            variant="ghost"
            @click="askConfirm('cancel', rx)"
          >
            {{ t('prescriptions.cancel') }}
          </UButton>
        </div>
      </UCard>
    </div>

    <UModal
      v-model:open="showEditor"
      :title="t('prescriptions.editorTitle')"
    >
      <template #body>
        <div class="space-y-3 p-4">
          <div
            v-if="templates.length > 0"
            class="flex flex-wrap gap-1.5"
          >
            <UButton
              v-for="tpl in templates"
              :key="tpl.id"
              size="xs"
              color="neutral"
              variant="outline"
              @click="applyTemplate(tpl)"
            >
              {{ tpl.name }}
            </UButton>
          </div>
          <div
            v-for="(item, idx) in editItems"
            :key="idx"
            class="grid grid-cols-[1fr_auto] gap-2 items-start border border-subtle rounded p-2"
          >
            <div class="space-y-2">
              <UInput
                v-model="item.medication_name"
                :placeholder="t('prescriptions.medicationName')"
              />
              <div class="grid grid-cols-3 gap-2">
                <UInput
                  v-model="item.dosage"
                  :placeholder="t('prescriptions.dosage')"
                />
                <UInput
                  v-model="item.unit"
                  :placeholder="t('prescriptions.unit')"
                />
                <UInput
                  v-model="item.frequency"
                  :placeholder="t('prescriptions.frequency')"
                />
              </div>
              <div class="grid grid-cols-3 gap-2">
                <UInput
                  v-model="item.route"
                  :placeholder="t('prescriptions.route')"
                />
                <UInput
                  v-model="item.duration"
                  :placeholder="t('prescriptions.duration')"
                />
                <UInput
                  v-model="item.instructions"
                  :placeholder="t('prescriptions.instructions')"
                />
              </div>
            </div>
            <UButton
              icon="i-lucide-x"
              size="xs"
              color="neutral"
              variant="ghost"
              :aria-label="t('prescriptions.removeLine')"
              @click="removeLine(idx)"
            />
          </div>
          <UButton
            color="neutral"
            variant="outline"
            icon="i-lucide-plus"
            @click="addLine"
          >
            {{ t('prescriptions.addLine') }}
          </UButton>
          <UFormField :label="t('prescriptions.notes')">
            <UTextarea
              v-model="editNotes"
              :rows="2"
            />
          </UFormField>
          <div class="flex gap-2 items-end">
            <UInput
              v-model="newTemplateName"
              :placeholder="t('prescriptions.templateName')"
              class="flex-1"
            />
            <UButton
              color="neutral"
              variant="outline"
              @click="saveAsTemplate"
            >
              {{ t('prescriptions.saveTemplate') }}
            </UButton>
          </div>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2 p-2">
          <UButton
            color="neutral"
            variant="ghost"
            @click="showEditor = false"
          >
            {{ t('common.close') }}
          </UButton>
          <UButton @click="save">
            {{ t('prescriptions.save') }}
          </UButton>
        </div>
      </template>
    </UModal>

    <UModal
      :open="pendingConfirm !== null"
      :title="t(lastKind === 'issue' ? 'prescriptions.issue' : 'prescriptions.cancel')"
      @update:open="(v: boolean) => { if (!v) pendingConfirm = null }"
    >
      <template #body>
        <div class="space-y-2 p-4 text-sm">
          <p>
            {{ t(lastKind === 'issue' ? 'prescriptions.issueConfirm' : 'prescriptions.cancelConfirm') }}
          </p>
          <p
            v-if="lastKind === 'issue' && !prescriberLicense"
            class="text-warning"
          >
            {{ t('prescriptions.noLicenseWarning') }}
          </p>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2 p-2">
          <UButton
            color="neutral"
            variant="ghost"
            @click="pendingConfirm = null"
          >
            {{ t('common.close') }}
          </UButton>
          <UButton @click="doConfirmed">
            {{ t('common.confirm') }}
          </UButton>
        </div>
      </template>
    </UModal>
  </div>
</template>
