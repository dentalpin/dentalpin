<script setup lang="ts">
import type { ReferenceItem, ReferenceKind } from '../../composables/useMedicalReference'

const { t } = useI18n()
const { search, create, deactivate } = useMedicalReference()

const tabs = [
  { value: 'allergies' as ReferenceKind, label: t('medicalReference.tabs.allergies') },
  { value: 'medications' as ReferenceKind, label: t('medicalReference.tabs.medications') },
  { value: 'diseases' as ReferenceKind, label: t('medicalReference.tabs.diseases') }
]
const activeTab = ref<ReferenceKind>('allergies')

const items = ref<ReferenceItem[]>([])
const loading = ref(false)
const includeInactive = ref(false)

async function load() {
  loading.value = true
  try {
    items.value = await search(activeTab.value, '', includeInactive.value, 1000)
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch([activeTab, includeInactive], load)

const newName = ref('')
const newIsApci = ref(false)
const saving = ref(false)

async function handleAdd() {
  if (!newName.value.trim()) return
  saving.value = true
  try {
    const data: { name: string, is_apci?: boolean } = { name: newName.value.trim() }
    if (activeTab.value === 'diseases') data.is_apci = newIsApci.value
    const created = await create(activeTab.value, data)
    if (created) {
      items.value.push(created)
      newName.value = ''
      newIsApci.value = false
    }
  } finally {
    saving.value = false
  }
}

async function handleDeactivate(id: string) {
  const ok = await deactivate(activeTab.value, id)
  if (ok) await load()
}
</script>

<template>
  <UCard>
    <div class="space-y-4">
      <UTabs
        v-model="activeTab"
        :items="tabs"
      />

      <div class="flex items-center justify-between">
        <UCheckbox
          v-model="includeInactive"
          :label="t('medicalReference.showInactive')"
        />
        <span class="text-caption text-subtle">
          {{ t('medicalReference.itemCount', { count: items.length }) }}
        </span>
      </div>

      <UTable
        :data="items"
        :loading="loading"
        :columns="[
          { accessorKey: 'name', header: t('medicalReference.name') },
          ...(activeTab === 'diseases' ? [{ accessorKey: 'is_apci', header: 'APCI' }] : []),
          { accessorKey: 'is_active', header: t('medicalReference.status') },
          { accessorKey: 'actions', header: '' }
        ]"
      >
        <template #is_apci-cell="{ row }">
          <UBadge
            v-if="row.original.is_apci"
            color="info"
            size="xs"
          >
            APCI
          </UBadge>
        </template>
      <template #is_active-cell="{ row }">
        <UBadge
          :color="row.original.is_active ? 'success' : 'neutral'"
          variant="subtle"
          size="xs"
        >
          {{ row.original.is_active ? t('medicalReference.active') : t('medicalReference.inactive') }}
        </UBadge>
      </template>
      <template #actions-cell="{ row }">
        <UButton
          v-if="row.original.is_active"
          icon="i-lucide-eye-off"
          variant="ghost"
          color="neutral"
          size="xs"
          @click="handleDeactivate(row.original.id)"
        />
      </template>
      </UTable>

      <div class="flex gap-2 items-center pt-2 border-t border-subtle">
        <UInput
          v-model="newName"
          :placeholder="t('medicalReference.newItemPlaceholder')"
          class="flex-1"
        />
        <UCheckbox
          v-if="activeTab === 'diseases'"
          v-model="newIsApci"
          label="APCI"
        />
        <UButton
          icon="i-lucide-plus"
          :loading="saving"
          :disabled="!newName.trim()"
          @click="handleAdd"
        >
          {{ t('common.add') }}
        </UButton>
      </div>
    </div>
  </UCard>
</template>
