<script setup lang="ts">
// SIF producer page — 3-step flow.
//
// 1. Identifica al productor del SIF (datos).
// 2. Lee la declaración responsable y fírmala electrónicamente.
//    El servidor sella timestamp + user_id como evidencia para una
//    inspección AEAT (RD 1007/2023 art. 13).
// 3. Descarga el PDF firmado para archivo / distribución a clínicas.
import type { ProducerInfoUpdate, VerifactuSettings, ProducerDefaults } from '~/composables/useVerifactu'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

const { t } = useI18n()
const { getSettings, getProducerDefaults, updateProducer, revokeDeclaration } = useVerifactu()
const { can } = usePermissions()
const toast = useToast?.()
const showRevokeConfirm = ref(false)
const revoking = ref(false)

const canManage = computed(() => can(PERMISSIONS.verifactu.settingsConfigure))

const settings = ref<VerifactuSettings | null>(null)
const defaults = ref<ProducerDefaults | null>(null)
const loading = ref(true)
const saving = ref(false)
const error = ref<string | null>(null)
const acceptedDeclaration = ref(false)

const form = ref<ProducerInfoUpdate>({
  producer_nif: '',
  producer_name: '',
  producer_id_sistema: 'DP',
  producer_version: '0.1.0',
  sign_declaracion: false
})

async function refresh() {
  loading.value = true
  try {
    const [s, d] = await Promise.all([getSettings(), getProducerDefaults()])
    settings.value = s
    defaults.value = d
    form.value = {
      producer_nif: s.producer_nif ?? d.nif,
      producer_name: s.producer_name ?? d.name,
      producer_id_sistema: s.producer_id_sistema ?? d.id_sistema,
      producer_version: s.producer_version ?? d.version,
      sign_declaracion: false
    }
  } finally {
    loading.value = false
  }
}

const alreadySigned = computed(() => !!settings.value?.declaracion_responsable_signed_at)
const signedAtFormatted = computed(() => {
  const at = settings.value?.declaracion_responsable_signed_at
  if (!at) return null
  return new Date(at).toLocaleString('es-ES', { dateStyle: 'long', timeStyle: 'short' })
})

const formFilled = computed(() =>
  form.value.producer_nif.trim().length >= 8
  && form.value.producer_name.trim().length >= 2
  && form.value.producer_id_sistema.trim().length >= 1
  && form.value.producer_version.trim().length >= 1
)

const canSaveDraft = computed(() =>
  canManage.value && formFilled.value && !alreadySigned.value && !saving.value
)

const canSign = computed(() =>
  canManage.value && formFilled.value && acceptedDeclaration.value && !alreadySigned.value && !saving.value
)

async function saveDraft() {
  if (!canSaveDraft.value) return
  saving.value = true
  error.value = null
  try {
    settings.value = await updateProducer({ ...form.value, sign_declaracion: false })
    toast?.add({ title: t('verifactu.producer.draftSaved'), color: 'green' })
  } catch (e: unknown) {
    error.value = errorMessage(e, t('verifactu.producer.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function revokeNow() {
  if (!canManage.value || !alreadySigned.value || revoking.value) return
  revoking.value = true
  error.value = null
  try {
    settings.value = await revokeDeclaration()
    showRevokeConfirm.value = false
    acceptedDeclaration.value = false
    toast?.add({ title: t('verifactu.producer.revokedToast'), color: 'amber' })
  } catch (e: unknown) {
    error.value = errorMessage(e, t('verifactu.producer.saveFailed'))
  } finally {
    revoking.value = false
  }
}

async function signNow() {
  if (!canSign.value) return
  saving.value = true
  error.value = null
  try {
    settings.value = await updateProducer({ ...form.value, sign_declaracion: true })
    acceptedDeclaration.value = false
    toast?.add({ title: t('verifactu.producer.signedToast'), color: 'green' })
  } catch (e: unknown) {
    error.value = errorMessage(e, t('verifactu.producer.saveFailed'))
  } finally {
    saving.value = false
  }
}

function downloadPdf() {
  if (!alreadySigned.value) return
  const html = renderDeclarationHtml(form.value, settings.value)
  const win = window.open('', '_blank')
  if (win) {
    win.document.write(html)
    win.document.close()
  }
}

function renderDeclarationHtml(f: ProducerInfoUpdate, s: VerifactuSettings | null): string {
  const today = new Date().toLocaleDateString('es-ES')
  const signed = s?.declaracion_responsable_signed_at
    ? new Date(s.declaracion_responsable_signed_at).toLocaleString('es-ES', { dateStyle: 'long', timeStyle: 'short' })
    : null
  const signerLine = signed
    ? `<p><strong>Firmado electrónicamente</strong> el ${signed}.</p>`
    : '<p style="color:#b91c1c"><strong>Documento sin firma electrónica registrada.</strong></p>'

  return `<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Declaración responsable Veri*Factu</title>
<style>
  body{font-family:Georgia,serif;max-width:720px;margin:40px auto;padding:0 24px;line-height:1.55;color:#111}
  h1{font-size:18pt;margin-bottom:4px}
  h2{font-size:11pt;color:#555;margin:0 0 24px;font-weight:normal}
  ol li{margin-bottom:8px}
  .meta{margin-top:32px;padding:16px;background:#f6f6f6;border-radius:6px;font-size:10.5pt}
  .sig{margin-top:48px;padding-top:16px;border-top:1px solid #ccc}
</style>
</head><body>
<h1>Declaración responsable</h1>
<h2>Sistema Informático de Facturación — Veri*Factu (RD 1007/2023, art. 13)</h2>

<p>De conformidad con el artículo 13 del Real Decreto 1007/2023, de 5 de diciembre, por el que se aprueba el Reglamento de los Sistemas Informáticos de Facturación (RRSIF), y la Orden HAC/1177/2024:</p>

<p><strong>${escapeHtml(f.producer_name)}</strong>, con NIF <strong>${escapeHtml(f.producer_nif)}</strong>, en su condición de <strong>productor del Sistema Informático de Facturación</strong> denominado <strong>DentalPin</strong> (identificador del sistema <strong>${escapeHtml(f.producer_id_sistema)}</strong>, versión <strong>${escapeHtml(f.producer_version)}</strong>), declara responsablemente que:</p>

<ol>
<li>El sistema cumple los requisitos establecidos en el artículo 29.2.j) de la Ley 58/2003, General Tributaria, y en el RRSIF.</li>
<li>El sistema garantiza la integridad, conservación, accesibilidad, legibilidad, trazabilidad e inalterabilidad de los registros de facturación.</li>
<li>El sistema implementa el envío continuo de los registros a la AEAT en modalidad Veri*Factu.</li>
<li>El productor se compromete a mantener el sistema actualizado conforme a las modificaciones normativas que se publiquen.</li>
</ol>

<div class="meta">
  Lugar y fecha del documento: ${today}<br>
  Productor: ${escapeHtml(f.producer_name)} (NIF ${escapeHtml(f.producer_nif)})<br>
  Sistema: DentalPin · ID ${escapeHtml(f.producer_id_sistema)} · v${escapeHtml(f.producer_version)}
</div>

<div class="sig">
  ${signerLine}
  <p style="font-size:10pt;color:#666">La firma se almacena con sello de tiempo y usuario en el sistema. Esta página puede acompañar la declaración como evidencia ante la AEAT.</p>
</div>
</body></html>`
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

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
        {{ t('verifactu.producer.title') }}
      </h1>
      <p class="text-sm text-gray-500">
        {{ t('verifactu.producer.subtitle') }}
      </p>
    </header>

    <!-- 3-step process explainer. Always visible so the user has the
         mental model of what's required before scrolling. -->
    <UAlert
      color="blue"
      variant="soft"
      :title="t('verifactu.producer.process.title')"
    >
      <template #description>
        <ol class="list-decimal pl-5 mt-2 space-y-1 text-sm">
          <li>{{ t('verifactu.producer.process.s1') }}</li>
          <li>{{ t('verifactu.producer.process.s2') }}</li>
          <li>{{ t('verifactu.producer.process.s3') }}</li>
        </ol>
        <p class="mt-3 text-xs text-gray-500">
          {{ t('verifactu.producer.process.legalNote') }}
        </p>
      </template>
    </UAlert>

    <USkeleton
      v-if="loading"
      class="h-64 w-full"
    />

    <template v-else>
      <!-- ─── STEP 1 — Producer identity ─────────────────────────── -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-3">
            <span class="flex items-center justify-center w-7 h-7 rounded-full bg-primary-100 text-primary-700 font-semibold text-sm">1</span>
            <h2 class="font-semibold">
              {{ t('verifactu.producer.step1.title') }}
            </h2>
          </div>
        </template>

        <p class="text-sm text-gray-600 mb-4">
          {{ t('verifactu.producer.step1.description') }}
        </p>

        <UAlert
          v-if="alreadySigned"
          color="amber"
          variant="soft"
          icon="i-lucide-lock"
          :title="t('verifactu.producer.step1.lockedTitle')"
          :description="t('verifactu.producer.step1.lockedDescription')"
          class="mb-4"
        >
          <template #actions>
            <UButton
              v-if="canManage"
              color="amber"
              variant="solid"
              size="xs"
              icon="i-lucide-unlock"
              @click="showRevokeConfirm = true"
            >
              {{ t('verifactu.producer.revokeAction') }}
            </UButton>
          </template>
        </UAlert>

        <form
          class="space-y-4"
          @submit.prevent="saveDraft"
        >
          <UFormField
            :label="t('verifactu.producer.fields.name')"
            :hint="t('verifactu.producer.fields.nameHint')"
          >
            <UInput
              v-model="form.producer_name"
              :placeholder="defaults?.name"
              :disabled="alreadySigned"
            />
          </UFormField>
          <UFormField
            :label="t('verifactu.producer.fields.nif')"
            :hint="t('verifactu.producer.fields.nifHint')"
          >
            <UInput
              v-model="form.producer_nif"
              :placeholder="defaults?.nif"
              :disabled="alreadySigned"
            />
          </UFormField>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <UFormField
              :label="t('verifactu.producer.fields.idSistema')"
              :hint="t('verifactu.producer.fields.idSistemaHint')"
            >
              <UInput
                v-model="form.producer_id_sistema"
                maxlength="2"
                :disabled="alreadySigned"
              />
            </UFormField>
            <UFormField
              :label="t('verifactu.producer.fields.version')"
              :hint="t('verifactu.producer.fields.versionHint')"
            >
              <UInput
                v-model="form.producer_version"
                :disabled="alreadySigned"
              />
            </UFormField>
          </div>

          <UButton
            v-if="!alreadySigned"
            type="submit"
            variant="soft"
            :loading="saving"
            :disabled="!canSaveDraft"
          >
            {{ t('verifactu.producer.saveDraft') }}
          </UButton>
        </form>
      </UCard>

      <!-- ─── STEP 2 — Read & sign declaration ────────────────────── -->
      <UCard>
        <template #header>
          <div class="flex items-center justify-between gap-3 flex-wrap">
            <div class="flex items-center gap-3">
              <span class="flex items-center justify-center w-7 h-7 rounded-full bg-primary-100 text-primary-700 font-semibold text-sm">2</span>
              <h2 class="font-semibold">
                {{ t('verifactu.producer.step2.title') }}
              </h2>
            </div>
            <UBadge
              :color="alreadySigned ? 'green' : 'amber'"
              variant="subtle"
              :icon="alreadySigned ? 'i-lucide-check-circle' : 'i-lucide-clock'"
            >
              {{ alreadySigned ? t('verifactu.producer.statusSigned') : t('verifactu.producer.statusUnsigned') }}
            </UBadge>
          </div>
        </template>

        <p class="text-sm text-gray-600 mb-4">
          {{ t('verifactu.producer.step2.description') }}
        </p>

        <!-- Inline preview of the declaration with the form values
             interpolated. Lets the user verify exactly what they're
             about to sign. Same content as the downloadable PDF. -->
        <div class="border border-gray-200 dark:border-gray-700 rounded-md p-4 bg-gray-50 dark:bg-gray-900 text-sm leading-relaxed max-h-80 overflow-y-auto">
          <p class="font-semibold mb-2">
            {{ t('verifactu.producer.declaration.heading') }}
          </p>
          <p class="text-xs text-gray-500 mb-3">
            {{ t('verifactu.producer.declaration.legalRef') }}
          </p>

          <p class="mb-3">
            {{ t('verifactu.producer.declaration.preamble') }}
          </p>

          <p class="mb-3">
            {{ t('verifactu.producer.declaration.identity', {
              name: form.producer_name || '—',
              nif: form.producer_nif || '—',
              idSistema: form.producer_id_sistema || '—',
              version: form.producer_version || '—'
            }) }}
          </p>

          <ol class="list-decimal pl-5 space-y-2">
            <li>{{ t('verifactu.producer.declaration.item1') }}</li>
            <li>{{ t('verifactu.producer.declaration.item2') }}</li>
            <li>{{ t('verifactu.producer.declaration.item3') }}</li>
            <li>{{ t('verifactu.producer.declaration.item4') }}</li>
          </ol>
        </div>

        <!-- Pre-sign: checkbox + sign button. -->
        <div
          v-if="!alreadySigned"
          class="mt-5 space-y-4"
        >
          <UCheckbox
            v-model="acceptedDeclaration"
            :label="t('verifactu.producer.readAndAccept')"
          />

          <UAlert
            v-if="error"
            color="red"
            variant="soft"
            :title="error"
          />

          <div class="flex flex-wrap gap-2">
            <UButton
              icon="i-lucide-pen-tool"
              :loading="saving"
              :disabled="!canSign"
              @click="signNow"
            >
              {{ t('verifactu.producer.signButton') }}
            </UButton>
          </div>
          <p class="text-xs text-gray-500">
            {{ t('verifactu.producer.signNote') }}
          </p>
        </div>

        <!-- Post-sign: confirmation + sealed notice. -->
        <div
          v-else
          class="mt-5"
        >
          <div class="flex items-start gap-3 p-4 rounded-md bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-900">
            <UIcon
              name="i-lucide-shield-check"
              class="text-green-700 text-xl mt-0.5"
            />
            <div class="text-sm">
              <p class="font-medium text-green-900 dark:text-green-200">
                {{ t('verifactu.producer.signedAt', { at: signedAtFormatted }) }}
              </p>
              <p class="text-green-800 dark:text-green-300 mt-1">
                {{ t('verifactu.producer.sealedNote') }}
              </p>
            </div>
          </div>
        </div>
      </UCard>

      <!-- ─── STEP 3 — Download signed PDF ────────────────────────── -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-3">
            <span class="flex items-center justify-center w-7 h-7 rounded-full bg-primary-100 text-primary-700 font-semibold text-sm">3</span>
            <h2 class="font-semibold">
              {{ t('verifactu.producer.step3.title') }}
            </h2>
          </div>
        </template>

        <p class="text-sm text-gray-600 mb-4">
          {{ t('verifactu.producer.step3.description') }}
        </p>

        <UButton
          icon="i-lucide-download"
          :variant="alreadySigned ? 'solid' : 'soft'"
          :disabled="!alreadySigned"
          @click="downloadPdf"
        >
          {{ t('verifactu.producer.downloadPdf') }}
        </UButton>

        <p
          v-if="!alreadySigned"
          class="text-xs text-gray-500 mt-2"
        >
          {{ t('verifactu.producer.step3.lockedHint') }}
        </p>
      </UCard>
    </template>

    <!-- Revoke signature confirmation modal -->
    <UModal v-model:open="showRevokeConfirm">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-alert-triangle"
                class="text-amber-600 text-xl"
              />
              <h3 class="font-semibold">
                {{ t('verifactu.producer.revokeTitle') }}
              </h3>
            </div>
          </template>
          <p class="text-sm">
            {{ t('verifactu.producer.revokeBody') }}
          </p>
          <ul class="text-sm list-disc pl-5 mt-3 space-y-1 text-gray-600 dark:text-gray-300">
            <li>{{ t('verifactu.producer.revokeBullet1') }}</li>
            <li>{{ t('verifactu.producer.revokeBullet2') }}</li>
            <li>{{ t('verifactu.producer.revokeBullet3') }}</li>
          </ul>
          <template #footer>
            <div class="flex gap-2 justify-end">
              <UButton
                variant="ghost"
                @click="showRevokeConfirm = false"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                color="amber"
                :loading="revoking"
                icon="i-lucide-unlock"
                @click="revokeNow"
              >
                {{ t('verifactu.producer.revokeConfirm') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>
  </div>
</template>
