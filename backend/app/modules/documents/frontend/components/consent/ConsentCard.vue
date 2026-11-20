<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'

interface ConsentTemplate { id: string, title: string, body: string }
interface ConsentDocument {
  id: string
  title: string
  status: string
  content: { text?: string }
  signed: boolean
  revoked: boolean
  evidenceAvailable: boolean
}
interface ConsentSignatureStatus { id: string, signed: boolean, revoked: boolean }

const props = defineProps<{ ctx: { patient: { id: string } } }>()
const { t } = useI18n()
const api = useApi()
const { can } = usePermissions()
const templates = ref<ConsentTemplate[]>([])
const documents = ref<ConsentDocument[]>([])
const templateId = ref('')
const title = ref('')
const body = ref('')
const editing = ref('')
const editingConsent = ref('')
const consentTitle = ref('')
const consentText = ref('')
const signingUrl = ref('')
const qrImage = ref('')
const qrOpen = ref(false)
const templateOptions = computed(() => templates.value.map(item => ({ label: item.title, value: item.id })))
const message = ref('')
const busy = ref(false)

async function refresh() {
  const [a, b, signatureStatus] = await Promise.all([
    api.get<{ data: ConsentTemplate[] }>('/api/v1/documents/consent-templates'),
    api.get<{ data: ConsentDocument[] }>('/api/v1/documents', { query: {
      patient_id: props.ctx.patient.id, document_type: 'informed_consent', page_size: 100
    } }),
    api.get<{ data: ConsentSignatureStatus[] }>('/api/v1/documents/consents/signature-status', {
      query: { patient_id: props.ctx.patient.id }, errorToast: false
    }).catch(() => null)
  ])
  templates.value = a.data
  const statusById = new Map(signatureStatus?.data.map(item => [item.id, item]))
  documents.value = b.data.map((doc) => {
    const state = statusById.get(doc.id)
    // Do not offer edits if signature state could not be verified.
    return { ...doc, signed: state?.signed ?? true, revoked: state?.revoked ?? false, evidenceAvailable: state !== undefined }
  })
}

async function saveTemplate() {
  busy.value = true
  try {
    const payload = { title: title.value, body: body.value }
    if (editing.value) await api.put(`/api/v1/documents/consent-templates/${editing.value}`, payload)
    else await api.post('/api/v1/documents/consent-templates', payload)
    title.value = ''
    body.value = ''
    editing.value = ''
    await refresh()
  } finally { busy.value = false }
}
function editTemplate() {
  const selected = templates.value.find(x => x.id === templateId.value)
  if (selected) {
    editing.value = selected.id
    title.value = selected.title
    body.value = selected.body
  }
}
async function create() {
  busy.value = true
  try {
    const result = await api.post<{ data: { id: string } }>('/api/v1/documents/consents', {
      patient_id: props.ctx.patient.id, template_id: templateId.value
    })
    await link(result.data.id, 'sign')
    await refresh()
  } finally { busy.value = false }
}
async function link(id: string, purpose: 'sign' | 'revoke') {
  const result = await api.post<{ data: { url: string, qr_data_url: string } }>(`/api/v1/documents/consents/${id}/links?purpose=${purpose}`, {})
  signingUrl.value = result.data.url
  qrImage.value = result.data.qr_data_url
  qrOpen.value = true
  message.value = t('documents.consent.linkHelp')
}
function startEditConsent(doc: ConsentDocument) {
  editingConsent.value = doc.id
  consentTitle.value = doc.title
  consentText.value = doc.content?.text || ''
}
async function saveConsent() {
  busy.value = true
  try {
    await api.patch(`/api/v1/documents/${editingConsent.value}`, {
      title: consentTitle.value, content: { text: consentText.value }
    })
    editingConsent.value = ''
    signingUrl.value = ''
    message.value = t('documents.consent.linksInvalidated')
    await refresh()
  } finally { busy.value = false }
}
async function archiveConsent(id: string) {
  busy.value = true
  try {
    await api.del(`/api/v1/documents/${id}`)
    signingUrl.value = ''
    editingConsent.value = ''
    message.value = t('documents.consent.linksInvalidated')
    await refresh()
  } finally { busy.value = false }
}
async function generatePreview(id: string) {
  busy.value = true
  try {
    await api.post('/api/v1/documents/generate', { document_id: id })
    await refresh()
  } finally { busy.value = false }
}
async function downloadPreview(id: string) {
  const response = await api.raw(`/api/v1/documents/${id}/download`)
  if (!response.ok) {
    message.value = t('documents.consent.noEvidence')
    return
  }
  const url = URL.createObjectURL(await response.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = 'consent-preview.pdf'
  a.click()
  URL.revokeObjectURL(url)
}
function copyLink() {
  return navigator.clipboard.writeText(signingUrl.value)
}
async function download(id: string, purpose: 'sign' | 'revoke') {
  const response = await api.raw(`/api/v1/documents/consents/${id}/evidence/${purpose}/download`)
  if (!response.ok) {
    message.value = t('documents.consent.noEvidence')
    return
  }
  const url = URL.createObjectURL(await response.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = `consent-${purpose}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}
onMounted(() => refresh())
</script>

<template>
  <div class="space-y-3">
    <h3 class="font-semibold">
      {{ t('documents.consent.title') }}
    </h3>
    <label class="block text-sm">{{ t('documents.consent.template') }}</label>
    <USelect
      v-model="templateId"
      :items="templateOptions"
      :placeholder="t('documents.consent.selectTemplate')"
      class="w-full"
    />
    <div
      v-if="can(PERMISSIONS.generatedDocuments.write)"
      class="flex flex-wrap gap-2"
    >
      <UButton
        :disabled="!templateId || busy"
        @click="create"
      >
        {{ t('documents.consent.create') }}
      </UButton>
      <UButton
        :disabled="!templateId"
        variant="outline"
        @click="editTemplate"
      >
        {{ t('documents.consent.editTemplate') }}
      </UButton>
    </div>
    <details
      v-if="can(PERMISSIONS.generatedDocuments.write)"
      :open="!!editing"
    >
      <summary>{{ t('documents.consent.manageTemplate') }}</summary>
      <div class="space-y-2 pt-2">
        <UInput
          v-model="title"
          class="w-full rounded border p-2"
          :placeholder="t('documents.consent.templateTitle')"
        />
        <UTextarea
          v-model="body"
          class="w-full rounded border p-2"
          :rows="6"
          :placeholder="t('documents.consent.templateText')"
        />
        <UButton
          :disabled="!title.trim() || !body.trim() || busy"
          @click="saveTemplate"
        >
          {{ t('documents.consent.saveTemplate') }}
        </UButton>
        <UButton
          v-if="editing"
          variant="ghost"
          @click="editing = ''; title = ''; body = ''"
        >
          {{ t('common.cancel') }}
        </UButton>
      </div>
    </details>
    <UModal
      v-model:open="qrOpen"
      :title="t('documents.consent.qrTitle')"
      :description="t('documents.consent.linkHelp')"
    >
      <template #body>
        <div class="flex flex-col items-center gap-3 p-4">
          <img
            v-if="qrImage"
            :src="qrImage"
            :alt="t('documents.consent.qrTitle')"
            class="h-48 w-48"
          >
          <UButton
            color="neutral"
            variant="ghost"
            icon="i-lucide-copy"
            @click="copyLink"
          >
            {{ t('documents.consent.copy') }}
          </UButton>
        </div>
      </template>
    </UModal>
    <p v-if="message && !qrOpen">
      {{ message }}
    </p>
    <ul class="space-y-3">
      <li
        v-for="doc in documents"
        :key="doc.id"
        class="border-t pt-2"
      >
        <p>
          {{ doc.title }} · {{ t(`documents.consent.status.${doc.status}`) }}
          <UBadge
            v-if="doc.revoked"
            color="warning"
          >
            {{ t('documents.consent.revoked') }}
          </UBadge>
        </p>
        <div
          v-if="editingConsent === doc.id"
          class="space-y-2 pt-2"
        >
          <label class="block">
            {{ t('documents.consent.consentTitle') }}
            <UInput
              v-model="consentTitle"
              class="w-full rounded border p-2"
            />
          </label>
          <label class="block">
            {{ t('documents.consent.consentText') }}
            <UTextarea
              v-model="consentText"
              class="w-full rounded border p-2"
              :rows="6"
            />
          </label>
          <p class="text-sm">
            {{ t('documents.consent.editInvalidates') }}
          </p>
          <UButton
            :disabled="busy || !consentTitle.trim() || !consentText.trim()"
            @click="saveConsent"
          >
            {{ t('common.save') }}
          </UButton>
          <UButton
            variant="ghost"
            @click="editingConsent = ''"
          >
            {{ t('common.cancel') }}
          </UButton>
        </div>
        <div class="flex flex-wrap gap-2">
          <template v-if="doc.status !== 'archived' && !doc.signed">
            <template v-if="can(PERMISSIONS.generatedDocuments.write)">
              <UButton
                size="xs"
                :disabled="busy"
                @click="link(doc.id, 'sign')"
              >
                {{ t('documents.consent.signLink') }}
              </UButton>
              <UButton
                size="xs"
                variant="outline"
                :disabled="busy"
                @click="startEditConsent(doc)"
              >
                {{ t('documents.consent.editConsent') }}
              </UButton>
              <UButton
                size="xs"
                variant="outline"
                :disabled="busy"
                @click="archiveConsent(doc.id)"
              >
                {{ t('documents.consent.archiveConsent') }}
              </UButton>
              <UButton
                size="xs"
                variant="outline"
                :disabled="busy"
                @click="generatePreview(doc.id)"
              >
                {{ t('documents.consent.generatePreview') }}
              </UButton>
            </template>
            <UButton
              v-if="doc.status === 'generated'"
              size="xs"
              @click="downloadPreview(doc.id)"
            >
              {{ t('documents.consent.downloadPreview') }}
            </UButton>
          </template>
          <template v-else-if="doc.status !== 'archived' && doc.signed && doc.evidenceAvailable">
            <UButton
              size="xs"
              @click="download(doc.id, 'sign')"
            >
              {{ t('documents.consent.download') }}
            </UButton>
            <UButton
              v-if="can(PERMISSIONS.generatedDocuments.write) && !doc.revoked"
              size="xs"
              variant="outline"
              @click="link(doc.id, 'revoke')"
            >
              {{ t('documents.consent.revoke') }}
            </UButton>
            <UButton
              v-if="doc.revoked"
              size="xs"
              variant="outline"
              @click="download(doc.id, 'revoke')"
            >
              {{ t('documents.consent.downloadRevocation') }}
            </UButton>
          </template>
          <p v-else-if="!doc.evidenceAvailable">
            {{ t('documents.consent.evidenceUnavailable') }}
          </p>
        </div>
      </li>
    </ul>
  </div>
</template>
