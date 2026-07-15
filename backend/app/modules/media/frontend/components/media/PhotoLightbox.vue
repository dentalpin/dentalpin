<script setup lang="ts">
import type { Document } from '~~/app/types'

interface Props {
  open: boolean
  documents: Document[]
  startId?: string | null
  /** Show before/after pairing controls + comparison view. */
  enablePairing?: boolean
}

const props = withDefaults(defineProps<Props>(), { enablePairing: false })
const emit = defineEmits<{
  'update:open': [boolean]
  'pair-changed': []
}>()

const { t } = useI18n()
const { pairPhotos, unpair } = usePhotos()

const config = useRuntimeConfig()
const auth = useAuth()
const apiBaseUrl = computed(() =>
  import.meta.server ? config.apiBaseUrlServer : config.public.apiBaseUrl
)

const index = ref(0)

watch(
  () => [props.open, props.startId, props.documents.length] as const,
  () => {
    if (!props.open) return
    if (props.startId) {
      const i = props.documents.findIndex(d => d.id === props.startId)
      index.value = i >= 0 ? i : 0
    } else {
      index.value = 0
    }
  },
  { immediate: true }
)

const current = computed(() => props.documents[index.value] ?? null)
const partner = computed<Document | null>(() => {
  const id = current.value?.paired_document_id
  if (!id) return null
  return props.documents.find(d => d.id === id) ?? null
})

const blobUrl = ref<string | null>(null)
const partnerBlobUrl = ref<string | null>(null)

async function fetchBlob(path: string): Promise<string | null> {
  try {
    const response = await $fetch<Blob>(path, {
      baseURL: apiBaseUrl.value,
      headers: { Authorization: `Bearer ${auth.accessToken.value}` },
      responseType: 'blob'
    })
    return URL.createObjectURL(response)
  } catch {
    return null
  }
}

async function loadCurrent() {
  if (!current.value) return
  const path = current.value.medium_url ?? current.value.full_url
  if (!path) return
  if (blobUrl.value) URL.revokeObjectURL(blobUrl.value)
  blobUrl.value = await fetchBlob(path)
}

async function loadPartner() {
  if (partnerBlobUrl.value) {
    URL.revokeObjectURL(partnerBlobUrl.value)
    partnerBlobUrl.value = null
  }
  if (!comparing.value || !partner.value) return
  const path = partner.value.medium_url ?? partner.value.full_url
  if (!path) return
  partnerBlobUrl.value = await fetchBlob(path)
}

watch(() => current.value?.id, loadCurrent, { immediate: true })

onBeforeUnmount(() => {
  if (blobUrl.value) URL.revokeObjectURL(blobUrl.value)
  if (partnerBlobUrl.value) URL.revokeObjectURL(partnerBlobUrl.value)
})

function close() {
  emit('update:open', false)
  comparing.value = false
  pickerOpen.value = false
}
function prev() {
  if (index.value > 0) index.value -= 1
}
function next() {
  if (index.value < props.documents.length - 1) index.value += 1
}

function onKey(e: KeyboardEvent) {
  if (!props.open) return
  if (e.key === 'ArrowLeft') prev()
  else if (e.key === 'ArrowRight') next()
  else if (e.key === 'Escape') close()
}

onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

let touchStartX = 0
function onTouchStart(e: TouchEvent) {
  touchStartX = e.touches[0]?.clientX ?? 0
}
function onTouchEnd(e: TouchEvent) {
  const dx = (e.changedTouches[0]?.clientX ?? 0) - touchStartX
  if (Math.abs(dx) > 60) {
    if (dx > 0) prev()
    else next()
  }
}

const captureLabel = computed(() => {
  if (!current.value) return ''
  const ts = current.value.captured_at ?? current.value.created_at
  return ts ? new Date(ts).toLocaleString() : ''
})

// ----- Pairing -----
const comparing = ref(false)
const pickerOpen = ref(false)
const pairBusy = ref(false)

watch(comparing, loadPartner)
watch(() => partner.value?.id, () => {
  if (comparing.value) loadPartner()
})

const pairCandidates = computed<Document[]>(() => {
  if (!current.value) return []
  return props.documents.filter(d =>
    d.id !== current.value!.id
    && !d.paired_document_id
    && (d.media_kind === 'photo' || d.media_kind === 'xray')
  )
})

async function handlePair(target: Document) {
  if (!current.value || pairBusy.value) return
  pairBusy.value = true
  const updated = await pairPhotos(current.value.id, target.id)
  pairBusy.value = false
  pickerOpen.value = false
  if (updated) emit('pair-changed')
}

async function handleUnpair() {
  if (!current.value || pairBusy.value) return
  pairBusy.value = true
  const ok = await unpair(current.value.id)
  pairBusy.value = false
  if (ok) {
    comparing.value = false
    emit('pair-changed')
  }
}

function toggleCompare() {
  comparing.value = !comparing.value
}
</script>

<template>
  <UModal
    :open="props.open"
    fullscreen
    @update:open="emit('update:open', $event)"
  >
    <template #content>
      <div
        class="flex h-full w-full flex-col bg-black/95 text-white"
        @touchstart="onTouchStart"
        @touchend="onTouchEnd"
      >
        <!-- Top bar -->
        <div class="flex items-center justify-between gap-3 px-4 py-3 text-sm">
          <div class="flex flex-col">
            <span class="font-medium">{{ current?.title ?? '' }}</span>
            <span class="text-xs text-white/70">{{ captureLabel }}</span>
          </div>
          <div class="flex items-center gap-3">
            <span class="text-xs text-white/70">{{ index + 1 }} / {{ documents.length }}</span>
            <button
              type="button"
              class="flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20 focus:outline-none focus:ring-2 focus:ring-white/40"
              :aria-label="t('common.close')"
              @click="close"
            >
              <UIcon
                name="i-lucide-x"
                class="h-5 w-5"
              />
            </button>
          </div>
        </div>

        <!-- Image area -->
        <div class="relative flex flex-1 items-center justify-center overflow-hidden">
          <button
            v-if="index > 0 && !comparing"
            type="button"
            class="absolute left-2 top-1/2 hidden -translate-y-1/2 rounded-full bg-black/40 p-2 text-white hover:bg-black/60 sm:block"
            :aria-label="t('common.previous')"
            @click="prev"
          >
            <UIcon
              name="i-lucide-chevron-left"
              class="h-6 w-6"
            />
          </button>

          <!-- Single image OR side-by-side comparison -->
          <div
            v-if="comparing && partner"
            class="grid h-full w-full grid-cols-1 gap-2 p-2 sm:grid-cols-2"
          >
            <figure class="relative flex flex-col items-center">
              <span class="absolute top-2 left-2 z-10 rounded bg-primary px-2 py-0.5 text-[11px] font-semibold text-inverted shadow">
                {{ current?.media_subtype === 'after'
                  ? t('photoGallery.compare.after', 'Después')
                  : t('photoGallery.compare.before', 'Antes') }}
              </span>
              <img
                v-if="blobUrl"
                :src="blobUrl"
                :alt="current?.title"
                class="max-h-full max-w-full object-contain"
                draggable="false"
              >
            </figure>
            <figure class="relative flex flex-col items-center">
              <span class="absolute top-2 left-2 z-10 rounded bg-primary px-2 py-0.5 text-[11px] font-semibold text-inverted shadow">
                {{ partner?.media_subtype === 'before'
                  ? t('photoGallery.compare.before', 'Antes')
                  : t('photoGallery.compare.after', 'Después') }}
              </span>
              <img
                v-if="partnerBlobUrl"
                :src="partnerBlobUrl"
                :alt="partner?.title"
                class="max-h-full max-w-full object-contain"
                draggable="false"
              >
              <div
                v-else
                class="text-white/70"
              >
                <UIcon
                  name="i-lucide-loader-2"
                  class="h-8 w-8 animate-spin"
                />
              </div>
            </figure>
          </div>

          <img
            v-else-if="blobUrl"
            :src="blobUrl"
            :alt="current?.title"
            class="max-h-full max-w-full select-none object-contain"
            draggable="false"
          >
          <div
            v-else
            class="text-white/70"
          >
            <UIcon
              name="i-lucide-loader-2"
              class="h-8 w-8 animate-spin"
            />
          </div>

          <button
            v-if="index < documents.length - 1 && !comparing"
            type="button"
            class="absolute right-2 top-1/2 hidden -translate-y-1/2 rounded-full bg-black/40 p-2 text-white hover:bg-black/60 sm:block"
            :aria-label="t('common.next')"
            @click="next"
          >
            <UIcon
              name="i-lucide-chevron-right"
              class="h-6 w-6"
            />
          </button>
        </div>

        <!-- Pair candidate picker (slide-up panel) -->
        <div
          v-if="pickerOpen"
          class="border-t border-white/10 bg-black/80 px-4 py-3"
        >
          <div class="mb-2 flex items-center justify-between text-xs text-white/80">
            <span>{{ t('photoGallery.pair.pickHint', 'Elige la foto a emparejar:') }}</span>
            <button
              type="button"
              class="text-white/60 hover:text-white"
              @click="pickerOpen = false"
            >
              {{ t('actions.cancel', 'Cancelar') }}
            </button>
          </div>
          <div
            v-if="pairCandidates.length === 0"
            class="text-xs text-white/60"
          >
            {{ t('photoGallery.pair.noCandidates', 'Sin fotos disponibles. Sube otra primero.') }}
          </div>
          <div
            v-else
            class="flex gap-2 overflow-x-auto pb-1"
          >
            <button
              v-for="cand in pairCandidates"
              :key="cand.id"
              type="button"
              class="group flex shrink-0 flex-col items-center gap-1 rounded border border-white/20 bg-white/5 p-1.5 transition hover:border-primary hover:bg-primary/10"
              :disabled="pairBusy"
              @click="handlePair(cand)"
            >
              <PhotoCard
                :document="cand"
                class="!h-16 !w-16"
              />
              <span class="max-w-[80px] truncate text-[10px] text-white/80">
                {{ cand.media_subtype || cand.media_category || cand.title }}
              </span>
            </button>
          </div>
        </div>

        <!-- Metadata + pair actions footer -->
        <div class="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 px-4 py-2 text-xs">
          <div class="flex flex-wrap items-center gap-2">
            <UBadge
              v-if="current?.media_kind"
              color="neutral"
              variant="solid"
            >
              {{ current.media_kind }}
            </UBadge>
            <UBadge
              v-if="current?.media_category"
              color="primary"
              variant="soft"
            >
              {{ current.media_category }}
            </UBadge>
            <UBadge
              v-if="current?.media_subtype"
              color="primary"
              variant="outline"
            >
              {{ current.media_subtype }}
            </UBadge>
            <UBadge
              v-for="tag in current?.tags ?? []"
              :key="tag"
              color="neutral"
              variant="outline"
            >
              {{ tag }}
            </UBadge>
          </div>

          <!-- Pair actions (gallery context only) -->
          <div
            v-if="enablePairing && current"
            class="flex items-center gap-2"
          >
            <template v-if="current.paired_document_id">
              <span class="hidden items-center gap-1 text-white/70 sm:inline-flex">
                <UIcon
                  name="i-lucide-link"
                  class="h-3.5 w-3.5"
                />
                {{ partner?.title ?? t('photoGallery.pair.paired', 'Emparejada') }}
              </span>
              <button
                type="button"
                class="rounded bg-white/10 px-2 py-1 text-white hover:bg-white/20"
                :disabled="pairBusy || !partner"
                @click="toggleCompare"
              >
                {{ comparing
                  ? t('photoGallery.pair.exitCompare', 'Salir de la comparativa')
                  : t('photoGallery.pair.compare', 'Comparar') }}
              </button>
              <button
                type="button"
                class="rounded bg-error/80 px-2 py-1 text-white hover:bg-error"
                :disabled="pairBusy"
                @click="handleUnpair"
              >
                {{ t('photoGallery.pair.unpair', 'Quitar') }}
              </button>
            </template>
            <button
              v-else
              type="button"
              class="rounded bg-primary px-2 py-1 font-medium text-inverted hover:bg-primary/90"
              :disabled="pairBusy"
              @click="pickerOpen = !pickerOpen"
            >
              <UIcon
                name="i-lucide-link"
                class="mr-1 inline h-3.5 w-3.5"
              />
              {{ t('photoGallery.pair.pair', 'Emparejar antes/después') }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </UModal>
</template>
