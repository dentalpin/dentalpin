<script setup lang="ts">
import type { MediaCategory, MediaKind } from '~~/app/types'

interface Props {
  patientId: string
}

const props = defineProps<Props>()
const emit = defineEmits<{ uploaded: [] }>()

const { t } = useI18n()
const { uploadPhoto, uploading } = usePhotos()

// ---------- file state ----------
const file = ref<File | null>(null)
const previewUrl = ref<string | null>(null)
const dragging = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

function pickFile() {
  fileInputRef.value?.click()
}

function setFile(f: File | null) {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  file.value = f
  previewUrl.value = f ? URL.createObjectURL(f) : null
  if (f && !title.value) {
    title.value = f.name.replace(/\.[^.]+$/, '')
  }
}

function clearFile() {
  setFile(null)
}

function onSelect(event: Event) {
  const target = event.target as HTMLInputElement
  setFile(target.files?.[0] ?? null)
  target.value = ''
}

function onDrop(event: DragEvent) {
  dragging.value = false
  const dropped = event.dataTransfer?.files?.[0]
  if (dropped) setFile(dropped)
}

onBeforeUnmount(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})

// ---------- taxonomy state ----------
type CategoryDef = {
  key: MediaCategory
  kind: MediaKind
  icon: string
  label: string
  description: string
  subtypes: Array<{ value: string, label: string }>
}

const categoryDefs = computed<CategoryDef[]>(() => [
  {
    key: 'intraoral',
    kind: 'photo',
    icon: 'i-lucide-smile',
    label: t('photoGallery.cat.intraoral', 'Intraoral'),
    description: t('photoGallery.catDesc.intraoral', 'Dentro de la boca'),
    subtypes: [
      { value: 'frontal', label: t('photoGallery.sub.frontal', 'Frontal') },
      { value: 'lateral_left', label: t('photoGallery.sub.lateral_left', 'Lateral izda') },
      { value: 'lateral_right', label: t('photoGallery.sub.lateral_right', 'Lateral dcha') },
      { value: 'occlusal_upper', label: t('photoGallery.sub.occlusal_upper', 'Oclusal sup') },
      { value: 'occlusal_lower', label: t('photoGallery.sub.occlusal_lower', 'Oclusal inf') },
      { value: 'palatal', label: t('photoGallery.sub.palatal', 'Palatal') },
      { value: 'lingual', label: t('photoGallery.sub.lingual', 'Lingual') }
    ]
  },
  {
    key: 'extraoral',
    kind: 'photo',
    icon: 'i-lucide-user',
    label: t('photoGallery.cat.extraoral', 'Extraoral'),
    description: t('photoGallery.catDesc.extraoral', 'Cara y perfil'),
    subtypes: [
      { value: 'smile', label: t('photoGallery.sub.smile', 'Sonrisa') },
      { value: 'rest', label: t('photoGallery.sub.rest', 'Reposo') },
      { value: 'frontal_face', label: t('photoGallery.sub.frontal_face', 'Frontal') },
      { value: 'profile_left', label: t('photoGallery.sub.profile_left', 'Perfil izdo') },
      { value: 'profile_right', label: t('photoGallery.sub.profile_right', 'Perfil dcho') },
      { value: 'three_quarter_left', label: t('photoGallery.sub.three_quarter_left', '3/4 izdo') },
      { value: 'three_quarter_right', label: t('photoGallery.sub.three_quarter_right', '3/4 dcho') }
    ]
  },
  {
    key: 'xray',
    kind: 'xray',
    icon: 'i-lucide-scan-line',
    label: t('photoGallery.cat.xray', 'Radiografía'),
    description: t('photoGallery.catDesc.xray', 'Imagen radiológica'),
    subtypes: [
      { value: 'panoramic', label: t('photoGallery.sub.panoramic', 'Panorámica') },
      { value: 'periapical', label: t('photoGallery.sub.periapical', 'Periapical') },
      { value: 'bitewing', label: t('photoGallery.sub.bitewing', 'Aleta') },
      { value: 'cephalometric_lateral', label: t('photoGallery.sub.ceph_lat', 'Cefalo lateral') },
      { value: 'cephalometric_pa', label: t('photoGallery.sub.ceph_pa', 'Cefalo PA') },
      { value: 'cbct', label: t('photoGallery.sub.cbct', 'CBCT') },
      { value: 'occlusal_xray', label: t('photoGallery.sub.occlusal_xray', 'Oclusal Rx') }
    ]
  },
  {
    key: 'clinical',
    kind: 'photo',
    icon: 'i-lucide-arrow-right-left',
    label: t('photoGallery.cat.clinical', 'Antes/Después'),
    description: t('photoGallery.catDesc.clinical', 'Comparativa de tratamiento'),
    subtypes: [
      { value: 'before', label: t('photoGallery.sub.before', 'Antes') },
      { value: 'after', label: t('photoGallery.sub.after', 'Después') },
      { value: 'progress', label: t('photoGallery.sub.progress', 'Progreso') },
      { value: 'reference', label: t('photoGallery.sub.reference', 'Referencia') }
    ]
  },
  {
    key: 'other',
    kind: 'photo',
    icon: 'i-lucide-image',
    label: t('photoGallery.cat.other', 'Otra'),
    description: t('photoGallery.catDesc.other', 'Sin clasificar'),
    subtypes: [
      { value: 'portrait', label: t('photoGallery.sub.portrait', 'Retrato') },
      { value: 'document_scan', label: t('photoGallery.sub.document_scan', 'Documento') },
      { value: 'model_photo', label: t('photoGallery.sub.model_photo', 'Modelo') }
    ]
  }
])

const activeCategoryKey = ref<MediaCategory>('intraoral')
const activeSubtype = ref<string>('frontal')
const title = ref('')
const capturedAt = ref<string>('')

const activeCategory = computed(
  () => categoryDefs.value.find(c => c.key === activeCategoryKey.value)!
)

watch(activeCategoryKey, () => {
  activeSubtype.value = activeCategory.value.subtypes[0]?.value ?? ''
})

const canSubmit = computed(() => !!file.value && !!title.value.trim() && !!activeSubtype.value)

const fileSizeLabel = computed(() => {
  if (!file.value) return ''
  const bytes = file.value.size
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
})

async function submit() {
  if (!file.value || !canSubmit.value) return
  const result = await uploadPhoto(props.patientId, {
    file: file.value,
    title: title.value.trim(),
    media_kind: activeCategory.value.kind,
    media_category: activeCategoryKey.value,
    media_subtype: activeSubtype.value,
    captured_at: capturedAt.value || undefined
  })
  if (result) {
    clearFile()
    title.value = ''
    capturedAt.value = ''
    emit('uploaded')
  }
}
</script>

<template>
  <div class="space-y-5">
    <!-- ===== Step 1 — picker / preview ===== -->
    <div
      v-if="!file"
      class="relative flex flex-col items-center justify-center gap-3 overflow-hidden rounded-xl border-2 border-dashed border-default p-10 text-center transition"
      :class="dragging
        ? 'border-primary bg-primary/5 scale-[1.01]'
        : 'hover:border-primary/60 hover:bg-elevated'"
      @click="pickFile"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <div class="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 text-primary">
        <UIcon
          name="i-lucide-image-up"
          class="h-8 w-8"
        />
      </div>
      <div>
        <p class="text-base font-medium text-default">
          {{ t('photoGallery.dropHere', 'Arrastra una foto o haz clic') }}
        </p>
        <p class="text-xs text-muted mt-1">
          JPG · PNG · HEIC · WebP — {{ t('common.maxFileSize', 'hasta 10 MB') }}
        </p>
      </div>
      <input
        ref="fileInputRef"
        type="file"
        accept="image/*"
        capture="environment"
        class="absolute inset-0 cursor-pointer opacity-0"
        @change="onSelect"
      >
    </div>

    <div
      v-else
      class="relative overflow-hidden rounded-xl border border-default bg-elevated"
    >
      <img
        :src="previewUrl ?? undefined"
        :alt="file.name"
        class="block max-h-[280px] w-full object-contain bg-checker"
      >
      <div class="flex items-center justify-between gap-3 px-3 py-2 bg-default">
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
        accept="image/*"
        class="hidden"
        @change="onSelect"
      >
    </div>

    <!-- ===== Step 2 — category cards ===== -->
    <div>
      <p class="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
        {{ t('photoGallery.category', 'Tipo') }}
      </p>
      <div class="grid grid-cols-2 gap-2 sm:grid-cols-5">
        <button
          v-for="cat in categoryDefs"
          :key="cat.key"
          type="button"
          class="group flex flex-col items-center gap-1 rounded-lg border p-3 text-center transition focus:outline-none focus:ring-2 focus:ring-primary"
          :class="activeCategoryKey === cat.key
            ? 'border-primary bg-primary/5 text-primary shadow-sm'
            : 'border-default bg-elevated hover:border-primary/40 hover:bg-default'"
          @click="activeCategoryKey = cat.key"
        >
          <UIcon
            :name="cat.icon"
            class="h-5 w-5"
          />
          <span class="text-xs font-medium leading-tight">
            {{ cat.label }}
          </span>
        </button>
      </div>
    </div>

    <!-- ===== Step 3 — subtype chips ===== -->
    <div v-if="activeCategory.subtypes.length">
      <p class="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
        {{ t('photoGallery.subtype', 'Vista') }}
      </p>
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="sub in activeCategory.subtypes"
          :key="sub.value"
          type="button"
          class="rounded-full px-3 py-1 text-xs font-medium transition focus:outline-none focus:ring-2 focus:ring-primary/40"
          :class="activeSubtype === sub.value
            ? 'bg-primary text-inverted'
            : 'bg-elevated text-muted hover:bg-default hover:text-default'"
          @click="activeSubtype = sub.value"
        >
          {{ sub.label }}
        </button>
      </div>
    </div>

    <!-- ===== Step 4 — title + optional date ===== -->
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto]">
      <UFormField
        :label="t('photoGallery.title', 'Título')"
        required
        size="sm"
      >
        <UInput
          v-model="title"
          :placeholder="t('photoGallery.titlePlaceholder', 'Frontal intraoral — 02/05')"
          icon="i-lucide-tag"
        />
      </UFormField>
      <UFormField
        :label="t('photoGallery.capturedAt', 'Fecha')"
        size="sm"
        :hint="t('photoGallery.exifHint', 'Auto desde EXIF')"
      >
        <UInput
          v-model="capturedAt"
          type="date"
        />
      </UFormField>
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
        {{ uploading ? t('common.uploading', 'Subiendo…') : t('common.upload', 'Subir foto') }}
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
