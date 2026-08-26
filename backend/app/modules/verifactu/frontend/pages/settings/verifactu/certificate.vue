<script setup lang="ts">
// Certificate management page.
//
// Three sections, top-down by priority:
//   1. Active certificate status — expiry countdown, validity range.
//   2. Upload form — prominent dropzone (drag & drop or click) + password.
//   3. History — every uploaded certificate, active one badge-marked.
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

const { t } = useI18n()
const toast = useToast?.()
const {
  getActiveCertificate,
  getCertificateHistory,
  uploadCertificate
} = useVerifactu()
const { can } = usePermissions()

const canManage = computed(() => can(PERMISSIONS.verifactu.settingsConfigure))

const active = ref<Awaited<ReturnType<typeof getActiveCertificate>> | null>(null)
const history = ref<Awaited<ReturnType<typeof getCertificateHistory>>>([])
const file = ref<File | null>(null)
const password = ref('')
const showPassword = ref(false)
const uploading = ref(false)
const dragOver = ref(false)
const error = ref<string | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

async function refresh() {
  active.value = await getActiveCertificate()
  history.value = await getCertificateHistory()
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  setFile(target.files?.[0] ?? null)
  // Reset input so picking the same file twice still triggers @change.
  if (target) target.value = ''
}

function onDrop(e: DragEvent) {
  dragOver.value = false
  const dropped = e.dataTransfer?.files?.[0]
  if (dropped) setFile(dropped)
}

function setFile(f: File | null) {
  if (!f) {
    file.value = null
    return
  }
  // Allow .pfx / .p12 by extension since browsers don't always set
  // a meaningful MIME type for these files.
  const lower = f.name.toLowerCase()
  if (!lower.endsWith('.pfx') && !lower.endsWith('.p12')) {
    error.value = t('verifactu.certificate.invalidFormat')
    return
  }
  error.value = null
  file.value = f
}

function clearFile() {
  file.value = null
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

async function submit() {
  if (!file.value || !password.value) return
  uploading.value = true
  error.value = null
  try {
    await uploadCertificate(file.value, password.value)
    file.value = null
    password.value = ''
    toast?.add({ title: t('verifactu.certificate.uploaded'), color: 'success' })
    await refresh()
  } catch (e: unknown) {
    error.value = errorMessage(e, t('verifactu.certificate.uploadFailed'))
  } finally {
    uploading.value = false
  }
}

const expiryInfo = computed(() => {
  const v = active.value?.valid_until
  if (!v) return null
  const until = new Date(v)
  const days = Math.floor((until.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
  if (days < 0) return { tone: 'red', icon: 'i-lucide-octagon-x', label: t('verifactu.status.certificateExpired'), days }
  if (days < 15) return { tone: 'red', icon: 'i-lucide-alert-triangle', label: t('verifactu.status.certificateExpiringSoon', { days }), days }
  if (days < 60) return { tone: 'amber', icon: 'i-lucide-alert-triangle', label: t('verifactu.status.certificateExpiringSoon', { days }), days }
  return { tone: 'emerald', icon: 'i-lucide-shield-check', label: t('verifactu.certificate.healthy'), days }
})

const expiryToneClass = computed(() => {
  switch (expiryInfo.value?.tone) {
    case 'red': return { wrap: 'border-red-300 bg-red-50', icon: 'text-red-600', text: 'text-red-800' }
    case 'amber': return { wrap: 'border-amber-300 bg-amber-50', icon: 'text-amber-600', text: 'text-amber-800' }
    case 'emerald': return { wrap: 'border-emerald-300 bg-emerald-50', icon: 'text-emerald-700', text: 'text-emerald-800' }
    default: return { wrap: 'border-gray-200 bg-gray-50', icon: 'text-gray-500', text: 'text-gray-700' }
  }
})

const canSubmit = computed(() =>
  !!file.value && password.value.length > 0 && !uploading.value
)

onMounted(refresh)
</script>

<template>
  <div class="p-4 sm:p-6 max-w-3xl mx-auto space-y-6">
    <header>
      <NuxtLink
        to="/settings/verifactu"
        class="text-sm text-gray-500"
      >← Verifactu</NuxtLink>
      <h1 class="text-2xl font-semibold mt-2">
        {{ t('verifactu.certificate.title') }}
      </h1>
      <p class="text-sm text-gray-500">
        {{ t('verifactu.certificate.description') }}
      </p>
    </header>

    <!-- ─── ACTIVE CERTIFICATE STATUS ───────────────────────────── -->
    <section
      v-if="active"
      class="rounded-lg border p-5 transition-colors"
      :class="expiryToneClass.wrap"
    >
      <div class="flex items-start gap-4">
        <UIcon
          v-if="expiryInfo"
          :name="expiryInfo.icon"
          class="text-3xl shrink-0 mt-0.5"
          :class="expiryToneClass.icon"
        />
        <div class="flex-1 min-w-0">
          <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 class="font-semibold">
              {{ active.subject_cn }}
            </h2>
            <span
              v-if="expiryInfo"
              class="text-sm font-medium"
              :class="expiryToneClass.text"
            >
              {{ expiryInfo.label }}
            </span>
          </div>
          <dl class="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <div>
              <dt class="text-gray-500 text-xs">
                {{ t('verifactu.certificate.issuer') }}
              </dt>
              <dd>{{ active.issuer_cn }}</dd>
            </div>
            <div>
              <dt class="text-gray-500 text-xs">
                {{ t('verifactu.certificate.nif') }}
              </dt>
              <dd class="font-mono">
                {{ active.nif_titular }}
              </dd>
            </div>
            <div>
              <dt class="text-gray-500 text-xs">
                {{ t('verifactu.certificate.validFrom') }}
              </dt>
              <dd>{{ active.valid_from ? new Date(active.valid_from).toLocaleDateString() : '—' }}</dd>
            </div>
            <div>
              <dt class="text-gray-500 text-xs">
                {{ t('verifactu.certificate.validUntil') }}
              </dt>
              <dd>{{ active.valid_until ? new Date(active.valid_until).toLocaleDateString() : '—' }}</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>

    <section
      v-else
      class="rounded-lg border border-amber-300 bg-amber-50 p-5"
    >
      <div class="flex items-start gap-4">
        <UIcon
          name="i-lucide-alert-triangle"
          class="text-3xl text-amber-600 shrink-0 mt-0.5"
        />
        <div>
          <h2 class="font-semibold text-amber-900">
            {{ t('verifactu.certificate.noActive') }}
          </h2>
          <p class="text-sm text-amber-800 mt-1">
            {{ t('verifactu.certificate.noActiveHint') }}
          </p>
        </div>
      </div>
    </section>

    <!-- ─── UPLOAD FORM ─────────────────────────────────────────── -->
    <UCard v-if="canManage">
      <template #header>
        <h2 class="font-semibold">
          {{ active ? t('verifactu.certificate.replaceTitle') : t('verifactu.certificate.uploadTitle') }}
        </h2>
      </template>

      <form
        class="space-y-5"
        @submit.prevent="submit"
      >
        <!-- Drag & drop / browse zone -->
        <div>
          <p class="text-sm font-medium mb-2">
            {{ t('verifactu.certificate.uploadFile') }}
          </p>
          <div
            class="relative rounded-lg border-2 border-dashed transition-colors cursor-pointer p-6 sm:p-8 text-center"
            :class="[
              dragOver
                ? 'border-primary-500 bg-primary-50'
                : file
                  ? 'border-emerald-500 bg-emerald-50'
                  : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
            ]"
            @click="triggerFileInput"
            @dragover.prevent="dragOver = true"
            @dragenter.prevent="dragOver = true"
            @dragleave.prevent="dragOver = false"
            @drop.prevent="onDrop"
          >
            <input
              ref="fileInputRef"
              type="file"
              accept=".pfx,.p12"
              class="hidden"
              @change="onFileChange"
            >

            <div
              v-if="!file"
              class="space-y-1"
            >
              <UIcon
                name="i-lucide-upload-cloud"
                class="text-4xl text-gray-400 mx-auto block"
              />
              <p class="font-medium text-sm">
                {{ t('verifactu.certificate.dropzoneTitle') }}
              </p>
              <p class="text-xs text-gray-500">
                {{ t('verifactu.certificate.dropzoneSubtitle') }}
              </p>
              <p class="text-xs text-gray-400 pt-1">
                {{ t('verifactu.certificate.dropzoneFormats') }}
              </p>
            </div>

            <div
              v-else
              class="flex items-center justify-center gap-3 text-left"
            >
              <UIcon
                name="i-lucide-file-check-2"
                class="text-3xl text-emerald-600 shrink-0"
              />
              <div class="min-w-0">
                <p class="font-medium text-sm truncate">
                  {{ file.name }}
                </p>
                <p class="text-xs text-gray-500">
                  {{ formatSize(file.size) }}
                </p>
              </div>
              <UButton
                icon="i-lucide-x"
                :aria-label="t('common.clear')"
                size="xs"
                color="neutral"
                variant="ghost"
                :title="t('verifactu.certificate.removeFile')"
                @click.stop="clearFile"
              />
            </div>
          </div>
        </div>

        <!-- Password with show/hide toggle -->
        <UFormField
          :label="t('verifactu.certificate.password')"
          :hint="t('verifactu.certificate.passwordHint')"
        >
          <UInput
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="off"
            :placeholder="t('verifactu.certificate.passwordPlaceholder')"
            :ui="{ trailing: 'pe-1' }"
          >
            <template #trailing>
              <UButton
                :icon="showPassword ? 'i-lucide-eye-off' : 'i-lucide-eye'"
                size="xs"
                color="neutral"
                variant="ghost"
                :aria-label="t('verifactu.certificate.togglePassword')"
                @click="showPassword = !showPassword"
              />
            </template>
          </UInput>
        </UFormField>

        <UAlert
          v-if="error"
          color="error"
          variant="soft"
          icon="i-lucide-alert-triangle"
          :title="error"
        />

        <UButton
          type="submit"
          :loading="uploading"
          :disabled="!canSubmit"
          icon="i-lucide-shield-check"
          size="md"
          block
        >
          {{ active ? t('verifactu.certificate.replaceSubmit') : t('verifactu.certificate.uploadSubmit') }}
        </UButton>

        <p class="text-xs text-gray-500 leading-relaxed">
          <UIcon
            name="i-lucide-lock"
            class="inline-block align-text-bottom mr-1"
          />
          {{ t('verifactu.certificate.encryptionNote') }}
        </p>
      </form>
    </UCard>

    <!-- ─── HELP / WHERE TO GET THE CERT ────────────────────────── -->
    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-help-circle"
            class="text-primary-500"
          />
          <h2 class="font-semibold">
            {{ t('verifactu.certificate.helpTitle') }}
          </h2>
        </div>
      </template>
      <div class="text-sm space-y-2 text-gray-700 dark:text-gray-300">
        <p>{{ t('verifactu.certificate.helpBody') }}</p>
        <ul class="list-disc pl-5 space-y-1">
          <li>{{ t('verifactu.certificate.helpItem1') }}</li>
          <li>{{ t('verifactu.certificate.helpItem2') }}</li>
          <li>{{ t('verifactu.certificate.helpItem3') }}</li>
        </ul>
        <p class="pt-1">
          <a
            href="https://www.sede.fnmt.gob.es/certificados/certificado-de-representante"
            target="_blank"
            rel="noopener noreferrer"
            class="text-primary-600 hover:underline inline-flex items-center gap-1"
          >
            {{ t('verifactu.certificate.fnmtLink') }}
            <UIcon name="i-lucide-external-link" />
          </a>
        </p>
      </div>
    </UCard>

    <!-- ─── HISTORY ─────────────────────────────────────────────── -->
    <UCard v-if="history.length > 0">
      <template #header>
        <h2 class="font-semibold">
          {{ t('verifactu.certificate.history') }}
        </h2>
      </template>
      <ul class="divide-y divide-gray-200 dark:divide-gray-700">
        <li
          v-for="c in history"
          :key="c.id"
          class="py-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm"
        >
          <UBadge
            :color="c.is_active ? 'success' : 'neutral'"
            variant="subtle"
            size="sm"
          >
            {{ c.is_active ? t('verifactu.certificate.active') : t('verifactu.status.disabled') }}
          </UBadge>
          <span class="font-medium">{{ c.subject_cn }}</span>
          <span
            v-if="c.valid_until"
            class="text-gray-500 ml-auto text-xs"
          >
            {{ t('verifactu.certificate.validUntil') }}: {{ new Date(c.valid_until).toLocaleDateString() }}
          </span>
        </li>
      </ul>
    </UCard>
  </div>
</template>
