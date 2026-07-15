<script setup lang="ts">
import type { Document, DocumentType } from '~~/app/types'

interface Props {
  patientId: string
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), { disabled: false })
const emit = defineEmits<{ uploaded: [document: Document] }>()

const { t } = useI18n()
const { uploadDocument, uploading, uploadProgress } = useDocuments()

// ---------- file state ----------
const file = ref<File | null>(null)
const previewUrl = ref<string | null>(null)
const dragging = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

const ALLOWED_MIME = ['application/pdf', 'image/jpeg', 'image/png']
const MAX_SIZE = 10 * 1024 * 1024

const validationError = ref<string | null>(null)

function pickFile() {
  if (!props.disabled) fileInputRef.value?.click()
}

function setFile(f: File | null) {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  validationError.value = null
  if (!f) {
    file.value = null
    previewUrl.value = null
    return
  }
  if (!ALLOWED_MIME.includes(f.type)) {
    validationError.value = t('documents.errors.mime', 'Tipo no permitido. Solo PDF, JPG o PNG.')
    return
  }
  if (f.size > MAX_SIZE) {
    validationError.value = t('documents.errors.size', 'El archivo supera 10 MB.')
    return
  }
  file.value = f
  previewUrl.value = f.type.startsWith('image/') ? URL.createObjectURL(f) : null
  if (!title.value) {
    title.value = f.name.replace(/\.[^.]+$/, '')
  }
}

function clearFile() {
  setFile(null)
  title.value = ''
  description.value = ''
  documentType.value = 'other'
}

function onSelect(event: Event) {
  const target = event.target as HTMLInputElement
  setFile(target.files?.[0] ?? null)
  target.value = ''
}

function onDrop(event: DragEvent) {
  dragging.value = false
  setFile(event.dataTransfer?.files?.[0] ?? null)
}

onBeforeUnmount(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})

// ---------- doc type cards ----------
type DocTypeDef = {
  key: DocumentType
  icon: string
  label: string
  description: string
}

const docTypes = computed<DocTypeDef[]>(() => [
  {
    key: 'consent',
    icon: 'i-lucide-file-signature',
    label: t('documents.types.consent', 'Consentimiento'),
    description: t('documents.typeDesc.consent', 'Documento firmado')
  },
  {
    key: 'id_scan',
    icon: 'i-lucide-id-card',
    label: t('documents.types.id_scan', 'Identificación'),
    description: t('documents.typeDesc.id_scan', 'DNI / pasaporte')
  },
  {
    key: 'insurance',
    icon: 'i-lucide-shield',
    label: t('documents.types.insurance', 'Seguro'),
    description: t('documents.typeDesc.insurance', 'Póliza o tarjeta')
  },
  {
    key: 'report',
    icon: 'i-lucide-file-text',
    label: t('documents.types.report', 'Informe'),
    description: t('documents.typeDesc.report', 'Reporte clínico')
  },
  {
    key: 'referral',
    icon: 'i-lucide-file-output',
    label: t('documents.types.referral', 'Derivación'),
    description: t('documents.typeDesc.referral', 'Carta de remisión')
  },
  {
    key: 'other',
    icon: 'i-lucide-file',
    label: t('documents.types.other', 'Otro'),
    description: t('documents.typeDesc.other', 'Sin clasificar')
  }
])

const documentType = ref<DocumentType>('other')
const title = ref('')
const description = ref('')

const canSubmit = computed(
  () => !!file.value && title.value.trim().length > 0 && !uploading.value
)

const fileSizeLabel = computed(() => {
  if (!file.value) return ''
  const bytes = file.value.size
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
})

const isPdf = computed(() => file.value?.type === 'application/pdf')

async function submit() {
  if (!file.value || !canSubmit.value) return
  const doc = await uploadDocument(
    props.patientId,
    file.value,
    documentType.value,
    title.value.trim(),
    description.value.trim() || undefined
  )
  if (doc) {
    emit('uploaded', doc)
    clearFile()
  }
}
</script>

<template>
  <div class="space-y-5">
    <!-- ===== Step 1 — picker / preview ===== -->
    <div
      v-if="!file"
      class="relative flex flex-col items-center justify-center gap-3 overflow-hidden rounded-xl border-2 border-dashed p-10 text-center transition"
      :class="[
        dragging
          ? 'border-primary bg-primary/5 scale-[1.01]'
          : 'border-default hover:border-primary/60 hover:bg-elevated',
        disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'
      ]"
      @click="pickFile"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <div class="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 text-primary">
        <UIcon
          name="i-lucide-file-up"
          class="h-8 w-8"
        />
      </div>
      <div>
        <p class="text-base font-medium text-default">
          {{ t('documents.dropzone.hint', 'Arrastra un documento o haz clic') }}
        </p>
        <p class="mt-1 text-xs text-muted">
          PDF · JPG · PNG — {{ t('common.maxFileSize', 'hasta 10 MB') }}
        </p>
      </div>
      <input
        ref="fileInputRef"
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        class="absolute inset-0 cursor-pointer opacity-0"
        :disabled="disabled"
        @change="onSelect"
      >
    </div>

    <div
      v-else
      class="overflow-hidden rounded-xl border border-default bg-elevated"
    >
      <!-- Image preview when applicable -->
      <img
        v-if="previewUrl"
        :src="previewUrl"
        :alt="file.name"
        class="bg-checker block max-h-[240px] w-full object-contain"
      >
      <!-- PDF placeholder -->
      <div
        v-else-if="isPdf"
        class="flex items-center justify-center gap-3 bg-default px-6 py-8 text-error-accent"
      >
        <UIcon
          name="i-lucide-file-text"
          class="h-12 w-12"
        />
        <div class="text-left">
          <p class="text-sm font-semibold">
            PDF
          </p>
          <p class="text-xs text-muted">
            {{ t('documents.pdfPreviewHint', 'Vista previa tras subir') }}
          </p>
        </div>
      </div>
      <!-- Footer -->
      <div class="bg-default flex items-center justify-between gap-3 px-3 py-2">
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium">
            {{ file.name }}
          </p>
          <p class="text-xs text-muted">
            {{ fileSizeLabel }}
          </p>
        </div>
        <UButton
          variant="ghost"
          color="neutral"
          icon="i-lucide-rotate-ccw"
          size="sm"
          @click="pickFile"
        >
          {{ t('actions.change', 'Cambiar') }}
        </UButton>
        <UButton
          variant="ghost"
          color="error"
          icon="i-lucide-x"
          size="sm"
          @click="clearFile"
        />
      </div>
      <input
        ref="fileInputRef"
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        class="hidden"
        @change="onSelect"
      >
    </div>

    <!-- Validation error -->
    <p
      v-if="validationError"
      class="flex items-center gap-1.5 text-sm text-error-accent"
    >
      <UIcon
        name="i-lucide-alert-circle"
        class="h-4 w-4"
      />
      {{ validationError }}
    </p>

    <!-- ===== Step 2 — type cards ===== -->
    <div>
      <p class="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
        {{ t('documents.fields.type', 'Tipo') }}
      </p>
      <div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <button
          v-for="def in docTypes"
          :key="def.key"
          type="button"
          class="group flex items-start gap-3 rounded-lg border p-3 text-left transition focus:outline-none focus:ring-2 focus:ring-primary"
          :class="documentType === def.key
            ? 'border-primary bg-primary/5 text-primary shadow-sm'
            : 'border-default bg-elevated hover:border-primary/40 hover:bg-default'"
          @click="documentType = def.key"
        >
          <UIcon
            :name="def.icon"
            class="mt-0.5 h-5 w-5 shrink-0"
          />
          <div class="min-w-0">
            <p class="text-sm font-semibold leading-tight">
              {{ def.label }}
            </p>
            <p
              class="mt-0.5 text-xs leading-tight"
              :class="documentType === def.key ? 'text-primary/80' : 'text-muted'"
            >
              {{ def.description }}
            </p>
          </div>
        </button>
      </div>
    </div>

    <!-- ===== Step 3 — title + description ===== -->
    <UFormField
      :label="t('documents.fields.title', 'Título')"
      required
      size="sm"
    >
      <UInput
        v-model="title"
        :placeholder="t('documents.fields.titlePlaceholder', 'Consentimiento implantes — 02/05')"
        icon="i-lucide-tag"
      />
    </UFormField>

    <UFormField
      :label="t('documents.fields.description', 'Notas')"
      size="sm"
      :hint="t('common.optional', 'Opcional')"
    >
      <UTextarea
        v-model="description"
        :placeholder="t('documents.fields.descriptionPlaceholder', 'Contexto interno para el equipo')"
        :rows="2"
        autoresize
      />
    </UFormField>

    <!-- ===== Progress ===== -->
    <div
      v-if="uploading && uploadProgress"
      class="space-y-1"
    >
      <div class="flex justify-between text-caption text-subtle">
        <span>{{ t('documents.uploading', 'Subiendo…') }}</span>
        <span>{{ uploadProgress.percentage }}%</span>
      </div>
      <UProgress :value="uploadProgress.percentage" />
    </div>

    <!-- ===== Submit ===== -->
    <div class="flex justify-end">
      <UButton
        :disabled="!canSubmit"
        :loading="uploading"
        size="md"
        icon="i-lucide-upload"
        trailing
        @click="submit"
      >
        {{ uploading ? t('common.uploading', 'Subiendo…') : t('documents.upload', 'Subir documento') }}
      </UButton>
    </div>
  </div>
</template>

<style scoped>
.bg-checker {
  background-image:
    linear-gradient(45deg, #e5e7eb 25%, transparent 25%),
    linear-gradient(-45deg, #e5e7eb 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #e5e7eb 75%),
    linear-gradient(-45deg, transparent 75%, #e5e7eb 75%);
  background-size: 16px 16px;
  background-position: 0 0, 0 8px, 8px -8px, -8px 0;
}
:root.dark .bg-checker {
  background-image:
    linear-gradient(45deg, #1f2937 25%, transparent 25%),
    linear-gradient(-45deg, #1f2937 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #1f2937 75%),
    linear-gradient(-45deg, transparent 75%, #1f2937 75%);
}
</style>
