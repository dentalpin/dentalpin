<script setup lang="ts">
import { useNotificationTemplates, type NotificationTemplate } from '../../composables/useNotificationTemplates'

const { t } = useI18n()
const toast = useToast()
const templatesApi = useNotificationTemplates()

const items = ref<NotificationTemplate[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await templatesApi.list()
    items.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(load)

const CHANNELS = ['email', 'whatsapp', 'sms'] as const

// --- Add/edit modal ---
const showModal = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = reactive({
  template_key: '',
  channel: 'email' as string,
  locale: 'fr',
  subject: '',
  body_text: '',
  description: ''
})

function openCreate() {
  editingId.value = null
  form.template_key = ''
  form.channel = 'email'
  form.locale = 'fr'
  form.subject = ''
  form.body_text = ''
  form.description = ''
  showModal.value = true
}

function openEdit(tpl: NotificationTemplate) {
  editingId.value = tpl.id
  form.template_key = tpl.template_key
  form.channel = tpl.channel
  form.locale = tpl.locale
  form.subject = tpl.subject ?? ''
  form.body_text = tpl.body_text ?? ''
  form.description = tpl.description ?? ''
  showModal.value = true
}

async function submit() {
  saving.value = true
  try {
    if (editingId.value) {
      await templatesApi.update(editingId.value, {
        subject: form.subject || null,
        body_text: form.body_text || null,
        description: form.description || null
      })
    } else {
      await templatesApi.create({
        template_key: form.template_key,
        channel: form.channel,
        locale: form.locale,
        subject: form.subject || null,
        body_text: form.body_text || null,
        description: form.description || null
      })
    }
    showModal.value = false
    toast.add({ title: t('notifications.templatesPage.saved'), color: 'success' })
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(tpl: NotificationTemplate) {
  await templatesApi.remove(tpl.id)
  await load()
}

const columns = [
  { accessorKey: 'template_key', header: t('notifications.templatesPage.key') },
  { accessorKey: 'channel', header: t('notifications.templatesPage.channel') },
  { accessorKey: 'locale', header: t('notifications.templatesPage.locale') },
  { accessorKey: 'is_active', header: t('notifications.templatesPage.active') },
  { accessorKey: 'actions', header: '' }
]
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-h3 text-default">
          {{ t('notifications.templatesPage.title') }}
        </h2>
        <p class="text-caption text-subtle">
          {{ t('notifications.templatesPage.description') }}
        </p>
      </div>
      <UButton icon="i-lucide-plus" @click="openCreate">
        {{ t('notifications.templatesPage.add') }}
      </UButton>
    </div>

    <UTable :data="items" :columns="columns" :loading="loading">
      <template #is_active-cell="{ row }">
        <UBadge :color="row.original.is_active ? 'success' : 'neutral'" variant="soft" size="sm">
          {{ row.original.is_active ? t('notifications.templatesPage.active') : t('notifications.templatesPage.inactive') }}
        </UBadge>
        <UBadge v-if="row.original.is_system" color="neutral" variant="outline" size="sm" class="ml-1">
          {{ t('notifications.templatesPage.system') }}
        </UBadge>
      </template>
      <template #actions-cell="{ row }">
        <div v-if="!row.original.is_system" class="flex gap-1">
          <UButton icon="i-lucide-pencil" variant="ghost" size="xs" @click="openEdit(row.original)" />
          <UButton icon="i-lucide-trash-2" variant="ghost" color="error" size="xs" @click="remove(row.original)" />
        </div>
        <span v-else class="text-caption text-subtle">{{ t('notifications.templatesPage.systemLocked') }}</span>
      </template>
    </UTable>

    <UModal v-model:open="showModal">
      <template #content>
        <div class="p-4 space-y-4">
          <h3 class="text-h3 text-default">
            {{ editingId ? t('notifications.templatesPage.edit') : t('notifications.templatesPage.add') }}
          </h3>
          <UInput
            v-model="form.template_key"
            :disabled="!!editingId"
            :placeholder="t('notifications.templatesPage.key')"
          />
          <USelect
            v-model="form.channel"
            :disabled="!!editingId"
            :items="CHANNELS.map(c => ({ value: c, label: c }))"
          />
          <UInput v-model="form.locale" :disabled="!!editingId" :placeholder="t('notifications.templatesPage.locale')" />
          <UInput v-model="form.subject" :placeholder="t('notifications.templatesPage.subject')" />
          <UTextarea v-model="form.body_text" :rows="6" :placeholder="t('notifications.templatesPage.body')" />
          <UInput v-model="form.description" :placeholder="t('notifications.templatesPage.notesPlaceholder')" />
          <div class="flex justify-end gap-2">
            <UButton variant="ghost" @click="showModal = false">
              {{ t('actions.cancel') }}
            </UButton>
            <UButton :loading="saving" :disabled="!form.template_key" @click="submit">
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
