<script setup lang="ts">
interface ConsentTemplate { id: string, title: string, body: string }
interface ConsentDocument { id: string, title: string, status: string }
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
const signingUrl = ref('')
const message = ref('')
const busy = ref(false)

async function refresh() {
  const [a, b] = await Promise.all([
    api.get<{ data: ConsentTemplate[] }>('/api/v1/documents/consent-templates'),
    api.get<{ data: ConsentDocument[] }>('/api/v1/documents', { query: {
      patient_id: props.ctx.patient.id, document_type: 'informed_consent', page_size: 100
    } })
  ])
  templates.value = a.data
  documents.value = b.data
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
  const result = await api.post<{ data: { token: string } }>(`/api/v1/documents/consents/${id}/links?purpose=${purpose}`, {})
  signingUrl.value = `${window.location.origin}/p/consent#${result.data.token}`
  message.value = t('documents.consent.linkHelp')
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
    <select
      v-model="templateId"
      class="w-full rounded border p-2"
    >
      <option value="">
        {{ t('documents.consent.selectTemplate') }}
      </option>
      <option
        v-for="item in templates"
        :key="item.id"
        :value="item.id"
      >
        {{ item.title }}
      </option>
    </select>
    <div
      v-if="can('documents.write')"
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
      v-if="can('documents.write')"
      :open="!!editing"
    >
      <summary>{{ t('documents.consent.manageTemplate') }}</summary>
      <div class="space-y-2 pt-2">
        <input
          v-model="title"
          class="w-full rounded border p-2"
          :placeholder="t('documents.consent.templateTitle')"
        >
        <textarea
          v-model="body"
          class="w-full rounded border p-2"
          rows="6"
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
    <div
      v-if="signingUrl"
      class="space-y-1"
    >
      <p>{{ message }}</p>
      <input
        :value="signingUrl"
        readonly
        class="w-full rounded border p-2"
        @focus="($event.target as HTMLInputElement).select()"
      >
      <UButton
        variant="outline"
        @click="copyLink"
      >
        {{ t('documents.consent.copy') }}
      </UButton>
    </div>
    <p v-else-if="message">
      {{ message }}
    </p>
    <ul class="space-y-3">
      <li
        v-for="doc in documents"
        :key="doc.id"
        class="border-t pt-2"
      >
        <p>{{ doc.title }} · {{ doc.status }}</p>
        <div class="flex flex-wrap gap-2">
          <UButton
            v-if="doc.status === 'draft' && can('documents.write')"
            size="xs"
            @click="link(doc.id, 'sign')"
          >
            {{ t('documents.consent.signLink') }}
          </UButton>
          <template v-else-if="doc.status !== 'draft'">
            <UButton
              size="xs"
              @click="download(doc.id, 'sign')"
            >
              {{ t('documents.consent.download') }}
            </UButton>
            <UButton
              v-if="can('documents.write')"
              size="xs"
              variant="outline"
              @click="link(doc.id, 'revoke')"
            >
              {{ t('documents.consent.revoke') }}
            </UButton>
            <UButton
              size="xs"
              variant="outline"
              @click="download(doc.id, 'revoke')"
            >
              {{ t('documents.consent.downloadRevocation') }}
            </UButton>
          </template>
        </div>
      </li>
    </ul>
  </div>
</template>
