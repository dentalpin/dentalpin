<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">
          {{ t('procurement.suppliers.title') }}
        </h1>
        <p class="text-sm text-muted-foreground">
          {{ t('procurement.suppliers.subtitle') }}
        </p>
      </div>
      <UButton
        v-if="can(PERMISSIONS.suppliers.write)"
        icon="i-lucide-plus"
        @click="openCreate"
      >
        {{ t('procurement.suppliers.new') }}
      </UButton>
    </div>

    <div class="flex items-center gap-4">
      <UInput
        v-model="search"
        :placeholder="t('procurement.suppliers.searchPlaceholder')"
        icon="i-lucide-search"
        class="w-64"
        @change="reload"
      />
      <UCheckbox
        v-model="preferredOnly"
        :label="t('procurement.suppliers.preferredOnly')"
        @change="reload"
      />
      <UCheckbox
        v-model="includeInactive"
        :label="t('procurement.suppliers.includeInactive')"
        @change="reload"
      />
    </div>

    <div
      v-if="loading"
      class="space-y-4"
    >
      <USkeleton
        v-for="i in 5"
        :key="i"
        class="h-16"
      />
    </div>

    <UAlert
      v-else-if="error"
      color="error"
      :title="t('procurement.common.loadError')"
      :actions="[{ label: t('procurement.common.retry'), onClick: reload }]"
    />

    <UCard v-else-if="suppliers.length === 0">
      <p class="text-sm text-muted-foreground">
        {{ t('procurement.common.empty') }}
      </p>
    </UCard>

    <div
      v-else
      class="space-y-2"
    >
      <UCard
        v-for="supplier in suppliers"
        :key="supplier.id"
      >
        <div class="flex items-center justify-between gap-4">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <p class="font-medium truncate">
                {{ supplier.name }}
              </p>
              <UBadge
                v-if="supplier.is_preferred"
                color="primary"
                variant="soft"
              >
                {{ t('procurement.suppliers.preferred') }}
              </UBadge>
              <UBadge
                v-if="!supplier.is_active"
                color="neutral"
                variant="soft"
              >
                {{ t('procurement.suppliers.includeInactive') }}
              </UBadge>
            </div>
            <p class="text-sm text-muted-foreground truncate">
              {{ supplierDetails(supplier) }}
            </p>
          </div>
          <div
            v-if="can(PERMISSIONS.suppliers.write)"
            class="flex shrink-0 gap-2"
          >
            <UButton
              variant="ghost"
              icon="i-lucide-pencil"
              @click="openEdit(supplier)"
            >
              {{ t('procurement.common.edit') }}
            </UButton>
            <UButton
              variant="ghost"
              color="error"
              icon="i-lucide-trash-2"
              @click="askDelete(supplier)"
            >
              {{ t('procurement.common.delete') }}
            </UButton>
          </div>
        </div>
      </UCard>

      <div class="flex justify-center pt-2">
        <UPagination
          v-model:page="currentPage"
          :items-per-page="pageSize"
          :total="total"
        />
      </div>
    </div>

    <UModal v-model:open="showForm">
      <template #content>
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ editing ? t('procurement.suppliers.edit') : t('procurement.suppliers.new') }}
            </h2>
          </template>
          <div class="grid grid-cols-2 gap-4">
            <UFormField
              :label="t('procurement.suppliers.name')"
              class="col-span-2"
            >
              <UInput
                v-model="form.name"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('procurement.suppliers.phone')">
              <UInput
                v-model="form.phone"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('procurement.suppliers.email')">
              <UInput
                v-model="form.email"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('procurement.suppliers.address')"
              class="col-span-2"
            >
              <UInput
                v-model="form.address"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('procurement.suppliers.website')">
              <UInput
                v-model="form.website"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('procurement.suppliers.paymentTerms')">
              <UInput
                v-model="form.payment_terms"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('procurement.suppliers.leadTime')">
              <UInput
                v-model.number="form.lead_time_days"
                type="number"
                min="0"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('procurement.suppliers.preferred')">
              <UCheckbox v-model="form.is_preferred" />
            </UFormField>
            <UFormField
              :label="t('procurement.suppliers.notes')"
              class="col-span-2"
            >
              <UTextarea
                v-model="form.notes"
                class="w-full"
              />
            </UFormField>
          </div>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                @click="showForm = false"
              >
                {{ t('procurement.common.cancel') }}
              </UButton>
              <UButton
                :loading="saving"
                @click="save"
              >
                {{ t('procurement.common.save') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>

    <UModal v-model:open="showDelete">
      <template #content>
        <UCard>
          <p class="text-sm">
            {{ t('procurement.suppliers.deleteConfirm') }}
          </p>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                @click="showDelete = false"
              >
                {{ t('procurement.common.cancel') }}
              </UButton>
              <UButton
                color="error"
                :loading="saving"
                @click="remove"
              >
                {{ t('procurement.common.delete') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>
  </div>
</template>

<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'
import type { ProcurementSupplier } from '../../../composables/useProcurement'

const { t } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const { listSuppliers, createSupplier, updateSupplier, deleteSupplier } = useProcurement()

const suppliers = ref<ProcurementSupplier[]>([])
const loading = ref(true)
const error = ref(false)
const saving = ref(false)
const search = ref('')
const preferredOnly = ref(false)
const includeInactive = ref(false)
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)
const showForm = ref(false)
const showDelete = ref(false)
const editing = ref<ProcurementSupplier | null>(null)
const deleting = ref<ProcurementSupplier | null>(null)
const form = ref({
  name: '',
  phone: '',
  email: '',
  address: '',
  notes: '',
  website: '',
  payment_terms: '',
  lead_time_days: null as number | null,
  is_preferred: false
})

function supplierDetails(supplier: ProcurementSupplier): string {
  return [supplier.phone, supplier.email, supplier.payment_terms].filter(Boolean).join(' · ')
}

async function reload() {
  currentPage.value = 1
  await fetchSuppliers()
}

async function fetchSuppliers() {
  loading.value = true
  error.value = false
  try {
    const response = await listSuppliers({
      search: search.value || undefined,
      is_preferred: preferredOnly.value || undefined,
      include_inactive: includeInactive.value || undefined,
      page: currentPage.value,
      page_size: pageSize
    })
    suppliers.value = response.data
    total.value = response.total
  } catch (e) {
    error.value = true
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = {
    name: '',
    phone: '',
    email: '',
    address: '',
    notes: '',
    website: '',
    payment_terms: '',
    lead_time_days: null,
    is_preferred: false
  }
  showForm.value = true
}

function openEdit(supplier: ProcurementSupplier) {
  editing.value = supplier
  form.value = {
    name: supplier.name,
    phone: supplier.phone ?? '',
    email: supplier.email ?? '',
    address: supplier.address ?? '',
    notes: supplier.notes ?? '',
    website: supplier.website ?? '',
    payment_terms: supplier.payment_terms ?? '',
    lead_time_days: supplier.lead_time_days,
    is_preferred: supplier.is_preferred
  }
  showForm.value = true
}

function nullable(value: string): string | null {
  return value === '' ? null : value
}

async function save() {
  saving.value = true
  try {
    if (editing.value) {
      await updateSupplier(editing.value.id, {
        phone: nullable(form.value.phone),
        email: nullable(form.value.email),
        address: nullable(form.value.address),
        notes: nullable(form.value.notes),
        website: nullable(form.value.website),
        payment_terms: nullable(form.value.payment_terms),
        lead_time_days: form.value.lead_time_days,
        is_preferred: form.value.is_preferred
      })
      toast.add({ title: t('procurement.suppliers.updated'), color: 'success' })
    } else {
      await createSupplier({
        name: form.value.name,
        phone: nullable(form.value.phone),
        email: nullable(form.value.email),
        address: nullable(form.value.address),
        notes: nullable(form.value.notes),
        website: nullable(form.value.website),
        payment_terms: nullable(form.value.payment_terms),
        lead_time_days: form.value.lead_time_days,
        is_preferred: form.value.is_preferred
      })
      toast.add({ title: t('procurement.suppliers.created'), color: 'success' })
    }
    showForm.value = false
    await fetchSuppliers()
  } catch (e) {
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

function askDelete(supplier: ProcurementSupplier) {
  deleting.value = supplier
  showDelete.value = true
}

async function remove() {
  if (!deleting.value) return
  saving.value = true
  try {
    await deleteSupplier(deleting.value.id)
    toast.add({ title: t('procurement.suppliers.deleted'), color: 'success' })
    showDelete.value = false
    await fetchSuppliers()
  } catch (e) {
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

watch(currentPage, fetchSuppliers)
onMounted(fetchSuppliers)
</script>
