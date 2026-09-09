<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">
          {{ t('procurement.items.title') }}
        </h1>
        <p class="text-sm text-muted-foreground">
          {{ t('procurement.items.subtitle') }}
        </p>
      </div>
      <UButton
        v-if="can(PERMISSIONS.supplierItems.write)"
        icon="i-lucide-plus"
        @click="showForm = true"
      >
        {{ t('procurement.items.new') }}
      </UButton>
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
      :actions="[{ label: t('procurement.common.retry'), onClick: fetchLinks }]"
    />

    <UCard v-else-if="links.length === 0">
      <p class="text-sm text-muted-foreground">
        {{ t('procurement.items.emptyHint') }}
      </p>
    </UCard>

    <div
      v-else
      class="space-y-2"
    >
      <UCard
        v-for="link in links"
        :key="link.id"
      >
        <div class="flex items-center justify-between gap-4">
          <div class="min-w-0">
            <p class="font-medium truncate">
              {{ link.item_name ?? link.inventory_item_id }}
            </p>
            <p class="text-sm text-muted-foreground truncate">
              {{ link.supplier_name ?? link.supplier_id }}
              <span v-if="link.supplier_sku"> · {{ link.supplier_sku }}</span>
              <span v-if="link.price"> · {{ link.price }}</span>
            </p>
          </div>
          <UButton
            v-if="can(PERMISSIONS.supplierItems.write)"
            variant="ghost"
            color="error"
            icon="i-lucide-unlink"
            @click="askDelist(link)"
          >
            {{ t('procurement.items.delist') }}
          </UButton>
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
              {{ t('procurement.items.new') }}
            </h2>
          </template>
          <div class="grid grid-cols-2 gap-4">
            <UFormField :label="t('procurement.items.supplier')">
              <USelect
                v-model="form.supplier_id"
                :items="supplierOptions"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('procurement.items.item')">
              <USelect
                v-model="form.inventory_item_id"
                :items="itemOptions"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('procurement.items.sku')">
              <UInput
                v-model="form.supplier_sku"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('procurement.items.price')">
              <UInput
                v-model="form.price"
                type="number"
                min="0"
                step="0.01"
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

    <UModal v-model:open="showDelist">
      <template #content>
        <UCard>
          <p class="text-sm">
            {{ t('procurement.items.delistConfirm') }}
          </p>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                @click="showDelist = false"
              >
                {{ t('procurement.common.cancel') }}
              </UButton>
              <UButton
                color="error"
                :loading="saving"
                @click="delist"
              >
                {{ t('procurement.items.delist') }}
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
import type { SupplierItemLink } from '../../../composables/useProcurement'

const { t } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const {
  listSupplierItems,
  createSupplierItemLink,
  deleteSupplierItemLink,
  listSuppliers,
  listInventoryItems
} = useProcurement()

const links = ref<SupplierItemLink[]>([])
const loading = ref(true)
const error = ref(false)
const saving = ref(false)
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)
const showForm = ref(false)
const showDelist = ref(false)
const delisting = ref<SupplierItemLink | null>(null)
const supplierOptions = ref<{ label: string, value: string }[]>([])
const itemOptions = ref<{ label: string, value: string }[]>([])
const form = ref({ supplier_id: '', inventory_item_id: '', supplier_sku: '', price: '' })

async function fetchLinks() {
  loading.value = true
  error.value = false
  try {
    const response = await listSupplierItems({ page: currentPage.value, page_size: pageSize })
    links.value = response.data
    total.value = response.total
  } catch (e) {
    error.value = true
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [suppliers, items] = await Promise.all([
    listSuppliers({ page: 1, page_size: 100 }),
    listInventoryItems({ page: 1, page_size: 100 })
  ])
  supplierOptions.value = suppliers.data.map(s => ({ label: s.name, value: s.id }))
  itemOptions.value = items.data.map(i => ({ label: i.name, value: i.id }))
}

async function save() {
  saving.value = true
  try {
    await createSupplierItemLink({
      supplier_id: form.value.supplier_id,
      inventory_item_id: form.value.inventory_item_id,
      supplier_sku: form.value.supplier_sku || null,
      price: form.value.price || null
    })
    toast.add({ title: t('procurement.items.created'), color: 'success' })
    showForm.value = false
    form.value = { supplier_id: '', inventory_item_id: '', supplier_sku: '', price: '' }
    await fetchLinks()
  } catch (e) {
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

function askDelist(link: SupplierItemLink) {
  delisting.value = link
  showDelist.value = true
}

async function delist() {
  if (!delisting.value) return
  saving.value = true
  try {
    await deleteSupplierItemLink(delisting.value.id)
    toast.add({ title: t('procurement.items.deleted'), color: 'success' })
    showDelist.value = false
    await fetchLinks()
  } catch (e) {
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

watch(currentPage, fetchLinks)
onMounted(async () => {
  await Promise.all([fetchLinks(), loadOptions().catch(() => undefined)])
})
</script>
