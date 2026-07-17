<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { useContacts, type Contact, type ContactType } from '../../composables/useContacts'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const contactsApi = useContacts()

if (!can(PERMISSIONS.contacts.read)) {
  await navigateTo('/')
}

const canWrite = computed(() => can(PERMISSIONS.contacts.write))

const TYPES: ContactType[] = ['lab', 'supplier', 'other']
const typeOptions = computed(() =>
  TYPES.map(ty => ({ value: ty, label: t(`contacts.types.${ty}`) }))
)

const items = ref<Contact[]>([])
const loading = ref(false)
const filterType = ref<ContactType | undefined>(undefined)
const search = ref('')

async function load() {
  loading.value = true
  try {
    const res = await contactsApi.list({ contact_type: filterType.value, search: search.value, page: 1, page_size: 100 })
    items.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch([filterType, search], load)

// --- Add/edit contact modal ---
const showModal = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = ref({
  name: '',
  contact_type: 'lab' as ContactType,
  phone: '',
  email: '',
  address: '',
  notes: ''
})

function openCreate() {
  editingId.value = null
  form.value = { name: '', contact_type: 'lab', phone: '', email: '', address: '', notes: '' }
  showModal.value = true
}

function openEdit(contact: Contact) {
  editingId.value = contact.id
  form.value = {
    name: contact.name,
    contact_type: contact.contact_type,
    phone: contact.phone ?? '',
    email: contact.email ?? '',
    address: contact.address ?? '',
    notes: contact.notes ?? ''
  }
  showModal.value = true
}

async function submit() {
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      contact_type: form.value.contact_type,
      phone: form.value.phone || null,
      email: form.value.email || null,
      address: form.value.address || null,
      notes: form.value.notes || null
    }
    if (editingId.value) {
      await contactsApi.update(editingId.value, payload)
    } else {
      await contactsApi.create(payload)
    }
    showModal.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(id: string) {
  await contactsApi.remove(id)
  await load()
}

const columns = [
  { accessorKey: 'name', header: t('contacts.name') },
  { accessorKey: 'contact_type', header: t('contacts.type') },
  { accessorKey: 'phone', header: t('contacts.phone') },
  { accessorKey: 'email', header: t('contacts.email') },
  { accessorKey: 'actions', header: '' }
]
</script>

<template>
  <div class="p-4 space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-h2 text-default">
        {{ t('contacts.title') }}
      </h1>
      <UButton
        v-if="canWrite"
        icon="i-lucide-plus"
        @click="openCreate"
      >
        {{ t('contacts.add') }}
      </UButton>
    </div>

    <div class="flex flex-wrap gap-2">
      <UInput
        v-model="search"
        icon="i-lucide-search"
        :placeholder="t('contacts.search')"
        class="max-w-xs"
      />
      <USelect
        v-model="filterType"
        :items="typeOptions"
        :placeholder="t('contacts.filterByType')"
        class="max-w-xs"
      />
    </div>

    <UTable
      :data="items"
      :columns="columns"
      :loading="loading"
    >
      <template #contact_type-cell="{ row }">
        {{ t(`contacts.types.${row.original.contact_type}`) }}
      </template>
      <template #actions-cell="{ row }">
        <div v-if="canWrite" class="flex gap-1">
          <UButton
            icon="i-lucide-pencil"
            variant="ghost"
            size="xs"
            @click="openEdit(row.original)"
          />
          <UButton
            icon="i-lucide-trash-2"
            variant="ghost"
            color="error"
            size="xs"
            @click="remove(row.original.id)"
          />
        </div>
      </template>
    </UTable>

    <UModal v-model:open="showModal">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ editingId ? t('contacts.edit') : t('contacts.add') }}
          </h2>
          <UInput v-model="form.name" :placeholder="t('contacts.name')" />
          <USelect v-model="form.contact_type" :items="typeOptions" />
          <UInput v-model="form.phone" :placeholder="t('contacts.phone')" />
          <UInput v-model="form.email" type="email" :placeholder="t('contacts.email')" />
          <UInput v-model="form.address" :placeholder="t('contacts.address')" />
          <UInput v-model="form.notes" :placeholder="t('contacts.notes')" />
          <div class="flex justify-end gap-2">
            <UButton variant="ghost" @click="showModal = false">
              {{ t('actions.cancel') }}
            </UButton>
            <UButton :loading="saving" @click="submit">
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
