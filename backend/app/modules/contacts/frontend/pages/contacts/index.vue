<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { useContacts, type Contact, type ContactType } from '../../composables/useContacts'
import { useSuppliers } from '../../../../suppliers/frontend/composables/useSuppliers'
import SupplierPerformanceModal from '../../../../supplier_ratings/frontend/components/SupplierPerformanceModal.vue'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const contactsApi = useContacts()
const suppliersApi = useSuppliers()

if (!can(PERMISSIONS.contacts.read)) {
  await navigateTo('/')
}

const canWrite = computed(() => can(PERMISSIONS.contacts.write))

const TYPES: ContactType[] = ['lab', 'supplier', 'delegate', 'other']
const typeOptions = computed(() =>
  TYPES.map(ty => ({ value: ty, label: t(`contacts.types.${ty}`) }))
)

const items = ref<Contact[]>([])
const performanceContact = ref<Contact | null>(null)
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

// Supplier-only procurement fields (Phase 13 §5 — folded into this
// same modal instead of a separate suppliers page/nav entry).
interface SupplierFormFields {
  website: string
  payment_terms: string
  lead_time_days: number | null
  is_preferred: boolean
}
const supplierForm = ref<SupplierFormFields>({
  website: '',
  payment_terms: '',
  lead_time_days: null,
  is_preferred: false
})
const isSupplier = computed(() => form.value.contact_type === 'supplier')

function resetSupplierForm() {
  supplierForm.value = { website: '', payment_terms: '', lead_time_days: null, is_preferred: false }
}

function openCreate() {
  editingId.value = null
  form.value = { name: '', contact_type: 'lab', phone: '', email: '', address: '', notes: '' }
  resetSupplierForm()
  showModal.value = true
}

async function openEdit(contact: Contact) {
  editingId.value = contact.id
  form.value = {
    name: contact.name,
    contact_type: contact.contact_type,
    phone: contact.phone ?? '',
    email: contact.email ?? '',
    address: contact.address ?? '',
    notes: contact.notes ?? ''
  }
  resetSupplierForm()

  if (contact.contact_type === 'supplier') {
    try {
      const res = await suppliersApi.getSupplier(contact.id)
      supplierForm.value = {
        website: res.data.website ?? '',
        payment_terms: res.data.payment_terms ?? '',
        lead_time_days: res.data.lead_time_days ?? null,
        is_preferred: res.data.is_preferred
      }
    } catch {
      // No profile row yet for this supplier — keep the reset defaults.
    }
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

    let contactId = editingId.value
    if (contactId) {
      await contactsApi.update(contactId, payload)
    } else {
      const created = await contactsApi.create(payload)
      contactId = created.data.id
    }

    if (form.value.contact_type === 'supplier' && contactId) {
      await suppliersApi.upsertProfile(contactId, {
        website: supplierForm.value.website || null,
        payment_terms: supplierForm.value.payment_terms || null,
        lead_time_days: supplierForm.value.lead_time_days ?? null,
        is_preferred: supplierForm.value.is_preferred
      })
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
  { accessorKey: 'notes', header: t('contacts.notes') },
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
      <template #notes-cell="{ row }">
        <span
          v-if="row.original.notes"
          class="text-caption text-subtle line-clamp-1"
          :title="row.original.notes"
        >
          {{ row.original.notes }}
        </span>
      </template>
      <template #actions-cell="{ row }">
        <div class="flex gap-1">
          <UButton
            v-if="row.original.contact_type === 'supplier'"
            icon="i-lucide-bar-chart-3"
            variant="ghost"
            size="xs"
            @click="performanceContact = row.original"
          />
          <template v-if="canWrite">
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
          </template>
        </div>
      </template>
    </UTable>

    <SupplierPerformanceModal
      v-if="performanceContact"
      :contact-id="performanceContact.id"
      :supplier-name="performanceContact.name"
      @close="performanceContact = null"
    />

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

          <template v-if="isSupplier">
            <div class="pt-2 border-t border-default space-y-2">
              <div class="text-caption font-medium text-subtle">
                {{ t('contacts.supplier.sectionTitle') }}
              </div>
              <UInput v-model="supplierForm.website" :placeholder="t('contacts.supplier.website')" />
              <UInput v-model="supplierForm.payment_terms" :placeholder="t('contacts.supplier.paymentTerms')" />
              <UInput
                v-model.number="supplierForm.lead_time_days"
                type="number"
                step="1"
                :placeholder="t('contacts.supplier.leadTimeDays')"
              />
              <UCheckbox v-model="supplierForm.is_preferred" :label="t('contacts.supplier.preferred')" />
            </div>
          </template>

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
