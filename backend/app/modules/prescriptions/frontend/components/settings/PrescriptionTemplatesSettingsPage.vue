<script setup lang="ts">
/**
 * Prescription templates manager (Settings → Clinical).
 * Rename + delete; creation happens inline on the prescriptions page.
 */
import type { PrescriptionTemplate } from '../../composables/usePrescriptions'

const { t } = useI18n()
const { can } = usePermissions()
const { listTemplates, updateTemplate, deleteTemplate } = usePrescriptions()

const canWrite = computed(() => can('prescriptions.write'))
const templates = ref<PrescriptionTemplate[]>([])
const isLoading = ref(false)
const editingId = ref<string | null>(null)
const editName = ref('')

async function refresh() {
  isLoading.value = true
  try {
    templates.value = await listTemplates()
  } finally {
    isLoading.value = false
  }
}

function startRename(tpl: PrescriptionTemplate) {
  editingId.value = tpl.id
  editName.value = tpl.name
}

async function saveRename(tpl: PrescriptionTemplate) {
  if (!editName.value.trim() || editName.value === tpl.name) {
    editingId.value = null
    return
  }
  await updateTemplate(tpl.id, editName.value.trim())
  editingId.value = null
  await refresh()
}

async function remove(id: string) {
  await deleteTemplate(id)
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <div class="space-y-2">
    <USkeleton
      v-if="isLoading"
      class="h-16"
    />
    <p
      v-else-if="templates.length === 0"
      class="text-sm text-muted"
    >
      {{ t('prescriptions.noTemplates') }}
    </p>
    <div
      v-for="tpl in templates"
      :key="tpl.id"
      class="flex items-center gap-2 border border-subtle rounded p-2"
    >
      <UInput
        v-if="editingId === tpl.id && canWrite"
        v-model="editName"
        class="flex-1"
        @keyup.enter="saveRename(tpl)"
      />
      <span
        v-else
        class="flex-1 text-sm"
      >{{ tpl.name }} ({{ tpl.items.length }})</span>
      <template v-if="canWrite">
        <UButton
          v-if="editingId !== tpl.id"
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-pencil"
          :aria-label="t('prescriptions.rename')"
          @click="startRename(tpl)"
        />
        <UButton
          v-else
          size="xs"
          @click="saveRename(tpl)"
        >
          {{ t('prescriptions.save') }}
        </UButton>
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-trash-2"
          :aria-label="t('prescriptions.deleteTemplate')"
          @click="remove(tpl.id)"
        />
      </template>
    </div>
  </div>
</template>
