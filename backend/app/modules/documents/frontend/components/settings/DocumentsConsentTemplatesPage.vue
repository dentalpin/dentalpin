<script setup lang="ts">
import type { ApiResponse } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'

interface ConsentTemplate { id: string, title: string, body: string, is_active?: boolean }

const { t } = useI18n()
const api = useApi()
const toast = useToast()

const templates = ref<ConsentTemplate[]>([])
const loading = ref(true)
const saving = ref(false)
const archivingId = ref('')
const editing = ref('')
const title = ref('')
const body = ref('')

const canSave = computed(() => !!title.value.trim() && !!body.value.trim() && !saving.value)

async function fetchTemplates(): Promise<void> {
  loading.value = true
  try {
    const res = await api.get<ApiResponse<ConsentTemplate[]>>('/api/v1/documents/consent-templates?include_archived=true')
    templates.value = res.data
  } catch (error: unknown) {
    toast.add({ title: errorMessage(error, t('common.error')), color: 'error' })
  } finally {
    loading.value = false
  }
}

function reset(): void {
  editing.value = ''
  title.value = ''
  body.value = ''
}

function edit(template: ConsentTemplate): void {
  editing.value = template.id
  title.value = template.title
  body.value = template.body
}

async function save(): Promise<void> {
  saving.value = true
  try {
    const payload = { title: title.value.trim(), body: body.value.trim() }
    if (editing.value) await api.put(`/api/v1/documents/consent-templates/${editing.value}`, payload)
    else await api.post('/api/v1/documents/consent-templates', payload)
    toast.add({ title: t('documents.settings.consentTemplates.saved'), color: 'success' })
    reset()
    await fetchTemplates()
  } catch (error: unknown) {
    toast.add({ title: errorMessage(error, t('common.error')), color: 'error' })
  } finally {
    saving.value = false
  }
}

async function setArchived(template: ConsentTemplate, archived: boolean): Promise<void> {
  archivingId.value = template.id
  try {
    await api.post(`/api/v1/documents/consent-templates/${template.id}/${archived ? 'archive' : 'unarchive'}`, {})
    toast.add({
      title: t(archived ? 'documents.settings.consentTemplateArchive.archivedToast' : 'documents.settings.consentTemplateArchive.restoredToast'),
      color: 'success'
    })
    await fetchTemplates()
  } catch (error: unknown) {
    toast.add({ title: errorMessage(error, t('common.error')), color: 'error' })
  } finally {
    archivingId.value = ''
  }
}

onMounted(fetchTemplates)
</script>

<template>
  <div class="space-y-4">
    <UCard :loading="loading">
      <p class="text-sm text-muted-foreground">
        {{ t('documents.settings.consentTemplates.help') }}
        {{ t('documents.settings.consentTemplateArchive.help') }}
      </p>
      <p
        v-if="!loading && !templates.length"
        class="pt-3 text-sm"
      >
        {{ t('documents.settings.consentTemplates.empty') }}
      </p>
      <ul
        v-else
        class="divide-y"
      >
        <li
          v-for="template in templates"
          :key="template.id"
          class="flex items-start justify-between gap-3 py-3"
        >
          <div
            class="min-w-0"
            :class="template.is_active === false && 'opacity-60'"
          >
            <p class="flex items-center gap-2 font-medium">
              {{ template.title }}
              <UBadge
                v-if="template.is_active === false"
                color="neutral"
                variant="subtle"
                size="sm"
              >
                {{ t('documents.settings.consentTemplateArchive.archived') }}
              </UBadge>
            </p>
            <p class="line-clamp-2 text-sm text-muted-foreground">
              {{ template.body }}
            </p>
          </div>
          <div class="flex shrink-0 gap-2">
            <UButton
              size="xs"
              variant="outline"
              icon="i-lucide-pencil"
              :disabled="saving"
              @click="edit(template)"
            >
              {{ t('documents.consent.editTemplate') }}
            </UButton>
            <UButton
              size="xs"
              variant="outline"
              color="neutral"
              :icon="template.is_active === false ? 'i-lucide-archive-restore' : 'i-lucide-archive'"
              :loading="archivingId === template.id"
              :disabled="saving || !!archivingId"
              @click="setArchived(template, template.is_active !== false)"
            >
              {{ t(template.is_active === false ? 'documents.settings.consentTemplateArchive.restore' : 'documents.settings.consentTemplateArchive.archive') }}
            </UButton>
          </div>
        </li>
      </ul>
    </UCard>

    <UCard>
      <template #header>
        <h3 class="font-semibold">
          {{ t('documents.consent.manageTemplate') }}
        </h3>
      </template>
      <div class="space-y-4">
        <UFormField :label="t('documents.consent.templateTitle')">
          <UInput
            v-model="title"
            class="w-full"
            :maxlength="200"
          />
        </UFormField>
        <UFormField :label="t('documents.consent.templateText')">
          <UTextarea
            v-model="body"
            class="w-full"
            :rows="10"
          />
        </UFormField>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <UButton
            v-if="editing"
            variant="ghost"
            @click="reset"
          >
            {{ t('common.cancel') }}
          </UButton>
          <UButton
            color="primary"
            :disabled="!canSave"
            :loading="saving"
            @click="save"
          >
            {{ t('documents.consent.saveTemplate') }}
          </UButton>
        </div>
      </template>
    </UCard>
  </div>
</template>
