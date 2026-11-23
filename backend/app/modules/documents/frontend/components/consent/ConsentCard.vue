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
const { t, locale } = useI18n()
const api = useApi()
const { can } = usePermissions()
const templates = ref<ConsentTemplate[]>([])
const documents = ref<ConsentDocument[]>([])
const templateId = ref('')
const editingConsent = ref('')
const consentTitle = ref('')
const consentText = ref('')
const signingUrl = ref('')
const qrImage = ref('')
const qrOpen = ref(false)
const templateOptions = computed(() => templates.value.map(item => ({ label: item.title, value: item.id })))
const message = ref('')
const busy = ref(false)
const toast = useToast()
// The tablet signs on another device: poll while the QR is open so the card
// flips to signed/revoked and the dialog closes without a manual reload.
const pendingLink = ref<{ id: string, purpose: 'sign' | 'revoke' } | null>(null)
let pollTimer: ReturnType<typeof setInterval> | undefined
watch(qrOpen, (open) => {
  clearInterval(pollTimer)
  if (!open) {
    pendingLink.value = null
    return
  }
  pollTimer = setInterval(async () => {
    await refresh()
    const pending = pendingLink.value
    const doc = pending && documents.value.find(d => d.id === pending.id)
    if (!doc || !pending) return
    if (pending.purpose === 'sign' ? doc.signed && doc.evidenceAvailable : doc.revoked) {
      qrOpen.value = false
      message.value = ''
      toast.add({ title: t(pending.purpose === 'sign' ? 'documents.consent.signedToast' : 'documents.consent.revoked'), color: 'success' })
    }
  }, 3000)
})
onUnmounted(() => clearInterval(pollTimer))

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
  pendingLink.value = { id, purpose }
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
    // Render the captions and draft watermark in the UI language, as the
    // documents page does (#524); without it the route falls back to es (#1041).
    await api.post(`/api/v1/documents/generate?locale=${encodeURIComponent(locale.value)}`, { document_id: id })
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
async function copyLink() {
  await navigator.clipboard.writeText(signingUrl.value)
  toast.add({ title: t('common.copied'), color: 'success' })
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
  <UCard :ui="{ body: 'space-y-3' }">
    <template #header>
      <h3 class="font-semibold">
        {{ t('documents.consent.title') }}
      </h3>
    </template>
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
    </div>
    <NuxtLink
      v-if="can(PERMISSIONS.generatedDocuments.write)"
      to="/settings/clinical/consent-templates"
      class="inline-block text-sm text-primary hover:underline"
    >
      {{ t('documents.settings.consentTemplates.manageLink') }}
    </NuxtLink>
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
              class="w-full"
            />
          </label>
          <label class="block">
            {{ t('documents.consent.consentText') }}
            <UTextarea
              v-model="consentText"
              class="w-full"
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
  </UCard>
</template>
