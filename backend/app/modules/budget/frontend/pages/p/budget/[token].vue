<script setup lang="ts">
/**
 * Patient-facing budget view (ADR 0006). Mounted at
 * ``/p/budget/<token>`` and bypasses the global auth middleware
 * (see ``frontend/app/middleware/auth.global.ts``).
 *
 * Conversion-optimised UI: clinic identity hero, personalised
 * greeting, itemised treatment list, prominent total, trust signals
 * and three CTAs (accept · doubts · reject) with a sticky bar on
 * mobile so the primary action is always reachable.
 */

import type { PublicBudgetItem } from '../../../composables/usePublicBudget'
import BudgetVerifyForm from '../../../components/public/BudgetVerifyForm.vue'

definePageMeta({ layout: 'public' })

const route = useRoute()
const i18n = useI18n()
const { t, locale } = i18n
const setLocale = (i18n as unknown as { setLocale?: (l: string) => Promise<void> }).setLocale

const token = computed(() => route.params.token as string)

const {
  meta,
  budget,
  verifying,
  submitting,
  lastError,
  fetchMeta,
  fetchBudget,
  verify,
  accept,
  reject,
  downloadSignedPdf
} = usePublicBudget(token.value)

const downloadingPdf = ref(false)
const reauthForDownload = ref(false)
const downloadError = ref<string | null>(null)

async function onDownloadSigned() {
  downloadingPdf.value = true
  downloadError.value = null
  try {
    const result = await downloadSignedPdf()
    if (result === 'ok') return
    if (result === 'verification_required') {
      reauthForDownload.value = true
      return
    }
    if (result === 'not_signed') {
      downloadError.value = t('budget.public.download.notSigned')
      return
    }
    downloadError.value = t('budget.public.download.error')
  } finally {
    downloadingPdf.value = false
  }
}

async function onReauthVerify(payload: { method: string, value: string }) {
  const ok = await verify(payload.method as never, payload.value)
  if (ok) {
    reauthForDownload.value = false
    await onDownloadSigned()
  }
}

async function applyClinicLanguage() {
  const lang = meta.value?.clinic_language
  if (!lang || lang === locale.value) return
  if (typeof setLocale === 'function') {
    try {
      await setLocale(lang)
    } catch {
      // ignore: keep current locale
    }
  } else {
    locale.value = lang as never
  }
}

onMounted(async () => {
  await fetchMeta()
  await applyClinicLanguage()
  if (
    meta.value
    && !meta.value.requires_verification
    && !meta.value.locked
    && !meta.value.expired
  ) {
    await fetchBudget()
  }
})

// ----- accept / reject modal state ---------------------------

const showAccept = ref(false)
const showReject = ref(false)

const signerName = ref('')
const signaturePng = ref<string | null>(null)
const consentChecked = ref(false)

const rejectReason = ref<'price' | 'time' | 'second_opinion' | 'other'>('price')
const rejectNote = ref('')

async function onVerifySubmit(payload: { method: string, value: string }) {
  const ok = await verify(payload.method as never, payload.value)
  if (ok) {
    await fetchMeta()
    await fetchBudget()
  }
}

// ----- accept (signature pad) ----------------------------------------

const canvasRef = ref<HTMLCanvasElement | null>(null)
let drawing = false
let lastX = 0
let lastY = 0

function getCtx(): CanvasRenderingContext2D | null {
  return canvasRef.value?.getContext('2d') ?? null
}

function startDraw(ev: PointerEvent) {
  if (!canvasRef.value) return
  drawing = true
  const rect = canvasRef.value.getBoundingClientRect()
  lastX = ev.clientX - rect.left
  lastY = ev.clientY - rect.top
}

function moveDraw(ev: PointerEvent) {
  if (!drawing || !canvasRef.value) return
  const ctx = getCtx()
  if (!ctx) return
  const rect = canvasRef.value.getBoundingClientRect()
  const x = ev.clientX - rect.left
  const y = ev.clientY - rect.top
  ctx.strokeStyle = '#0f172a'
  ctx.lineWidth = 2
  ctx.lineCap = 'round'
  ctx.beginPath()
  ctx.moveTo(lastX, lastY)
  ctx.lineTo(x, y)
  ctx.stroke()
  lastX = x
  lastY = y
}

function endDraw() {
  if (!drawing || !canvasRef.value) return
  drawing = false
  signaturePng.value = canvasRef.value.toDataURL('image/png')
}

function clearSignature() {
  if (!canvasRef.value) return
  const ctx = getCtx()
  if (ctx) ctx.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height)
  signaturePng.value = null
}

const canSubmitAccept = computed(
  () => signerName.value.trim().length > 0 && consentChecked.value
)

async function onAcceptSubmit() {
  if (!canSubmitAccept.value) return
  await accept({
    signer_name: signerName.value.trim(),
    signature_data: signaturePng.value ? { png: signaturePng.value } : undefined
  })
  showAccept.value = false
}

async function onRejectSubmit() {
  await reject({
    reason: rejectReason.value,
    note: rejectNote.value.trim() || undefined
  })
  showReject.value = false
}

// ----- formatting helpers ---------------------------------------------

function formatMoney(amount: number | string | null | undefined, currency: string | null | undefined): string {
  const n = typeof amount === 'string' ? Number(amount) : (amount ?? 0)
  const cur = currency || 'EUR'
  try {
    return new Intl.NumberFormat(locale.value, { style: 'currency', currency: cur }).format(n)
  } catch {
    return `${n.toFixed(2)} ${cur}`
  }
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString(locale.value, {
      day: '2-digit',
      month: 'long',
      year: 'numeric'
    })
  } catch {
    return iso
  }
}

function itemName(item: PublicBudgetItem): string {
  const names = item.catalog_item?.names
  if (names) {
    return (
      names[locale.value]
      || names['es']
      || names['en']
      || Object.values(names)[0]
      || item.catalog_item?.internal_code
      || '—'
    )
  }
  return item.catalog_item?.internal_code || '—'
}

const reasonOptions = computed(() => [
  { value: 'price', label: t('budget.public.reject.reasons.price') },
  { value: 'time', label: t('budget.public.reject.reasons.time') },
  { value: 'second_opinion', label: t('budget.public.reject.reasons.second_opinion') },
  { value: 'other', label: t('budget.public.reject.reasons.other') }
])

const greeting = computed(() => {
  const name = meta.value?.patient_first_name
  return name ? t('budget.public.greeting', { name }) : t('budget.public.title')
})
</script>

<template>
  <div class="public-budget">
    <!-- Loading -->
    <div
      v-if="!meta"
      class="container space-y-3 py-6"
    >
      <USkeleton class="h-12 w-2/3" />
      <USkeleton class="h-4 w-1/2" />
      <USkeleton class="h-64 w-full" />
    </div>

    <!-- Cold states -->
    <div
      v-else-if="meta.locked || meta.expired"
      class="container py-8 space-y-4"
    >
      <UCard>
        <div class="flex flex-col items-center text-center gap-3 py-8 px-4">
          <div
            class="w-14 h-14 rounded-full flex items-center justify-center"
            :class="meta.locked ? 'bg-red-100' : 'bg-amber-100'"
          >
            <UIcon
              :name="meta.locked ? 'i-lucide-shield-alert' : 'i-lucide-clock-alert'"
              class="w-7 h-7"
              :class="meta.locked ? 'text-red-600' : 'text-amber-600'"
            />
          </div>
          <h1 class="text-xl font-semibold">
            {{ meta.locked ? t('budget.public.locked') : t('budget.public.expired') }}
          </h1>
          <div
            v-if="meta.clinic_phone"
            class="pt-2"
          >
            <UButton
              :is="'a'"
              color="primary"
              size="lg"
              icon="i-lucide-phone"
              :href="`tel:${meta.clinic_phone}`"
            >
              {{ t('budget.public.callClinic') }}
            </UButton>
          </div>
        </div>
      </UCard>
    </div>

    <!-- Already decided -->
    <div
      v-else-if="meta.already_decided"
      class="container py-8 space-y-4"
    >
      <UCard>
        <div class="flex flex-col items-center text-center gap-3 py-8 px-4">
          <div
            class="w-14 h-14 rounded-full flex items-center justify-center"
            :class="meta.decided_status === 'accepted' ? 'bg-green-100' : 'bg-slate-100'"
          >
            <UIcon
              :name="meta.decided_status === 'accepted' ? 'i-lucide-check-circle-2' : 'i-lucide-info'"
              class="w-7 h-7"
              :class="meta.decided_status === 'accepted' ? 'text-green-600' : 'text-slate-600'"
            />
          </div>
          <h1 class="text-xl font-semibold">
            {{ meta.decided_status === 'accepted'
              ? t('budget.public.already_accepted')
              : t('budget.public.already_rejected')
            }}
          </h1>

          <div
            v-if="meta.decided_status === 'accepted' && !reauthForDownload"
            class="w-full max-w-xs pt-2"
          >
            <UButton
              color="primary"
              size="lg"
              block
              icon="i-lucide-download"
              :loading="downloadingPdf"
              @click="onDownloadSigned"
            >
              {{ t('budget.public.download.signedPdf') }}
            </UButton>
            <p
              v-if="downloadError"
              class="text-xs text-red-600 mt-2"
            >
              {{ downloadError }}
            </p>
          </div>

          <div
            v-if="reauthForDownload"
            class="w-full pt-4"
          >
            <p class="text-sm text-[var(--ui-text-muted)] mb-3">
              {{ t('budget.public.download.reauthIntro') }}
            </p>
            <BudgetVerifyForm
              :method="meta.method"
              :verifying="verifying"
              :error="lastError"
              @submit="onReauthVerify"
            />
          </div>

          <div
            v-if="meta.clinic_phone"
            class="pt-2"
          >
            <UButton
              :is="'a'"
              color="primary"
              variant="soft"
              size="lg"
              icon="i-lucide-phone"
              :href="`tel:${meta.clinic_phone}`"
            >
              {{ t('budget.public.callClinic') }}
            </UButton>
          </div>
        </div>
      </UCard>
    </div>

    <!-- Verify gate -->
    <div
      v-else-if="!budget && meta.requires_verification"
      class="container py-8 space-y-4"
    >
      <BudgetVerifyForm
        :method="meta.method"
        :verifying="verifying"
        :error="lastError"
        @submit="onVerifySubmit"
      />
    </div>

    <!-- Budget detail (post-verify) -->
    <template v-else-if="budget">
      <!-- Hero -->
      <section class="hero">
        <div class="container hero-inner">
          <div class="hero-clinic">
            <span class="hero-clinic-badge">{{ (meta.clinic_name || 'C').slice(0, 2).toUpperCase() }}</span>
            <div class="min-w-0">
              <p class="hero-clinic-name">
                {{ meta.clinic_name }}
              </p>
              <p
                v-if="meta.clinic_address_line"
                class="hero-clinic-meta"
              >
                {{ meta.clinic_address_line }}
              </p>
            </div>
          </div>
          <div class="hero-pill">
            <span class="hero-pill-label">{{ t('budget.public.budgetNumber') }}</span>
            <span class="hero-pill-value">{{ budget.budget_number }}</span>
          </div>
        </div>
      </section>

      <main class="container content space-y-5 pb-32 md:pb-10">
        <!-- Greeting -->
        <header class="space-y-1">
          <h1 class="page-title">
            {{ greeting }}
          </h1>
          <p class="page-sub">
            {{ t('budget.public.subtitle') }}
            <span v-if="meta.clinic_name">·&nbsp;{{ meta.clinic_name }}</span>
          </p>
          <p
            v-if="budget.valid_until"
            class="page-validity"
          >
            <UIcon
              name="i-lucide-calendar-clock"
              class="w-4 h-4 inline-block mr-1"
            />
            {{ t('budget.public.validUntil', { date: formatDate(budget.valid_until) }) }}
          </p>
        </header>

        <!-- Patient note from clinic -->
        <UAlert
          v-if="budget.patient_notes"
          color="info"
          variant="subtle"
          icon="i-lucide-message-square-quote"
          :title="t('budget.public.noteFromClinic')"
          :description="budget.patient_notes"
        />

        <!-- Treatments card -->
        <UCard class="treatments-card">
          <template #header>
            <div class="flex items-center justify-between">
              <h2 class="card-title">
                {{ t('budget.public.items') }}
              </h2>
              <span class="text-xs text-[var(--ui-text-muted)]">
                {{ budget.items.length }}
              </span>
            </div>
          </template>

          <ul class="treatments-list">
            <li
              v-for="(item, idx) in budget.items"
              :key="item.id"
              class="treatments-row"
            >
              <span class="treatments-index">{{ idx + 1 }}</span>
              <div class="min-w-0 flex-1">
                <p class="treatments-name">
                  {{ itemName(item) }}
                </p>
                <p
                  v-if="item.tooth_number"
                  class="treatments-meta"
                >
                  {{ t('budget.public.tooth', { number: item.tooth_number }) }}
                </p>
              </div>
              <div class="treatments-money">
                <p class="treatments-qty">
                  {{ item.quantity }} × {{ formatMoney(item.unit_price, meta?.clinic_currency) }}
                </p>
                <p class="treatments-total">
                  {{ formatMoney(item.line_total, meta?.clinic_currency) }}
                </p>
              </div>
            </li>
          </ul>
        </UCard>

        <!-- Total card (visually loud) -->
        <UCard class="total-card">
          <dl class="totals">
            <div class="totals-row">
              <dt>{{ t('budget.public.subtotal') }}</dt>
              <dd>{{ formatMoney(budget.subtotal, meta?.clinic_currency) }}</dd>
            </div>
            <div
              v-if="Number(budget.total_discount) > 0"
              class="totals-row totals-row-discount"
            >
              <dt>{{ t('budget.public.discount') }}</dt>
              <dd>−{{ formatMoney(budget.total_discount, meta?.clinic_currency) }}</dd>
            </div>
            <div class="totals-row">
              <dt>{{ t('budget.public.tax') }}</dt>
              <dd>{{ formatMoney(budget.total_tax, meta?.clinic_currency) }}</dd>
            </div>
            <div class="totals-row totals-grand">
              <dt>{{ t('budget.public.total') }}</dt>
              <dd>{{ formatMoney(budget.total, meta?.clinic_currency) }}</dd>
            </div>
          </dl>
        </UCard>

        <!-- Trust strip -->
        <ul class="trust-strip">
          <li>
            <UIcon
              name="i-lucide-lock"
              class="w-4 h-4"
            />
            <span>{{ t('budget.public.trustSecure') }}</span>
          </li>
          <li>
            <UIcon
              name="i-lucide-shield-check"
              class="w-4 h-4"
            />
            <span>{{ t('budget.public.trustEncrypted') }}</span>
          </li>
          <li>
            <UIcon
              name="i-lucide-pen-line"
              class="w-4 h-4"
            />
            <span>{{ t('budget.public.trustSignature') }}</span>
          </li>
        </ul>

        <!-- Desktop CTAs -->
        <div class="desktop-cta hidden md:flex flex-col gap-3 pt-2">
          <UButton
            color="primary"
            size="xl"
            block
            @click="showAccept = true"
          >
            {{ t('budget.public.cta_accept') }}
          </UButton>
          <button
            type="button"
            class="reject-link"
            @click="showReject = true"
          >
            {{ t('budget.public.cta_reject') }}
          </button>
        </div>

        <!-- Clinic contact footer -->
        <div
          v-if="meta.clinic_phone || meta.clinic_email"
          class="contact-card"
        >
          <UIcon
            name="i-lucide-headphones"
            class="w-5 h-5 text-[var(--ui-primary)]"
          />
          <div class="flex-1 min-w-0">
            <p class="contact-title">
              {{ t('budget.public.needHelp') }}
            </p>
            <p class="contact-name">
              {{ meta.clinic_name }}
            </p>
          </div>
          <div class="flex gap-2 shrink-0">
            <a
              v-if="meta.clinic_phone"
              :href="`tel:${meta.clinic_phone}`"
              class="contact-action"
            >
              <UIcon
                name="i-lucide-phone"
                class="w-4 h-4"
              />
            </a>
            <a
              v-if="meta.clinic_email"
              :href="`mailto:${meta.clinic_email}`"
              class="contact-action"
            >
              <UIcon
                name="i-lucide-mail"
                class="w-4 h-4"
              />
            </a>
          </div>
        </div>
      </main>

      <!-- Mobile sticky CTA -->
      <div class="mobile-cta md:hidden">
        <UButton
          color="primary"
          size="xl"
          block
          @click="showAccept = true"
        >
          {{ t('budget.public.cta_accept') }}
        </UButton>
        <div class="mobile-cta-secondary">
          <button
            type="button"
            @click="showReject = true"
          >
            {{ t('budget.public.cta_reject') }}
          </button>
        </div>
      </div>
    </template>

    <!-- Accept modal -->
    <UModal v-model:open="showAccept">
      <template #content>
        <UCard>
          <template #header>
            <h3 class="text-lg font-semibold">
              {{ t('budget.public.accept.title') }}
            </h3>
          </template>

          <div class="space-y-4">
            <UFormField
              :label="t('budget.public.accept.signerLabel')"
              required
            >
              <UInput
                v-model="signerName"
                autofocus
                size="lg"
              />
            </UFormField>

            <div>
              <p class="text-sm text-[var(--ui-text-muted)] mb-2">
                {{ t('budget.public.accept.signatureLabel') }}
              </p>
              <div class="rounded-md border border-[var(--ui-border)] bg-white touch-none">
                <canvas
                  ref="canvasRef"
                  width="600"
                  height="180"
                  class="block w-full h-44 cursor-crosshair"
                  @pointerdown="startDraw"
                  @pointermove="moveDraw"
                  @pointerup="endDraw"
                  @pointerleave="endDraw"
                />
              </div>
              <UButton
                color="neutral"
                variant="ghost"
                size="xs"
                class="mt-2"
                @click="clearSignature"
              >
                {{ t('budget.public.accept.signatureClear') }}
              </UButton>
            </div>

            <UCheckbox
              v-model="consentChecked"
              :label="t('budget.public.accept.consent')"
            />
          </div>

          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                color="neutral"
                variant="ghost"
                @click="showAccept = false"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                color="primary"
                :loading="submitting"
                :disabled="!canSubmitAccept"
                @click="onAcceptSubmit"
              >
                {{ t('budget.public.accept.submit') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>

    <!-- Reject modal -->
    <UModal v-model:open="showReject">
      <template #content>
        <UCard>
          <template #header>
            <h3 class="text-lg font-semibold">
              {{ t('budget.public.reject.title') }}
            </h3>
          </template>

          <div class="space-y-4">
            <p class="text-sm text-[var(--ui-text-muted)]">
              {{ t('budget.public.reject.intro') }}
            </p>
            <UFormField :label="t('budget.public.reject.reasonLabel')">
              <USelect
                v-model="rejectReason"
                :items="reasonOptions"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('budget.public.reject.noteLabel')">
              <UTextarea
                v-model="rejectNote"
                :rows="3"
                :maxlength="2000"
              />
            </UFormField>
          </div>

          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                color="neutral"
                variant="ghost"
                @click="showReject = false"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                color="error"
                :loading="submitting"
                @click="onRejectSubmit"
              >
                {{ t('budget.public.reject.submit') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>
  </div>
</template>

<style scoped>
.public-budget {
  min-height: 100vh;
}

.container {
  max-width: 720px;
  margin-left: auto;
  margin-right: auto;
  padding-left: 16px;
  padding-right: 16px;
}

/* ----- Hero --------------------------------------------------------- */

.hero {
  background: linear-gradient(135deg, var(--ui-primary) 0%, color-mix(in srgb, var(--ui-primary) 70%, #0f172a 30%) 100%);
  color: white;
}

.hero-inner {
  padding-top: 18px;
  padding-bottom: 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.hero-clinic {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.hero-clinic-badge {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.18);
  color: white;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}

.hero-clinic-name {
  font-weight: 600;
  font-size: 15px;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hero-clinic-meta {
  font-size: 12px;
  opacity: 0.8;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hero-pill {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  background: rgba(255, 255, 255, 0.15);
  padding: 6px 12px;
  border-radius: 999px;
  flex-shrink: 0;
}

.hero-pill-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  opacity: 0.85;
}

.hero-pill-value {
  font-size: 13px;
  font-weight: 700;
  font-feature-settings: 'tnum';
}

/* ----- Content ------------------------------------------------------ */

.content {
  padding-top: 24px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.01em;
  line-height: 1.2;
  color: var(--ui-text);
  margin: 0;
}

.page-sub {
  font-size: 14px;
  color: var(--ui-text-muted);
  margin: 0;
}

.page-validity {
  font-size: 12px;
  color: var(--ui-text-muted);
  margin-top: 6px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

/* ----- Treatments list --------------------------------------------- */

.treatments-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.treatments-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--ui-border);
}

.treatments-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.treatments-row:first-child {
  padding-top: 0;
}

.treatments-index {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--ui-primary) 12%, transparent);
  color: var(--ui-primary);
  font-weight: 600;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.treatments-name {
  font-size: 15px;
  font-weight: 500;
  color: var(--ui-text);
  margin: 0;
}

.treatments-meta {
  font-size: 12px;
  color: var(--ui-text-muted);
  margin: 2px 0 0 0;
}

.treatments-money {
  text-align: right;
  flex-shrink: 0;
}

.treatments-qty {
  font-size: 12px;
  color: var(--ui-text-muted);
  margin: 0;
}

.treatments-total {
  font-size: 15px;
  font-weight: 600;
  color: var(--ui-text);
  margin: 2px 0 0 0;
  font-feature-settings: 'tnum';
}

/* ----- Total card -------------------------------------------------- */

.total-card {
  border: 2px solid color-mix(in srgb, var(--ui-primary) 35%, transparent);
}

.totals {
  margin: 0;
}

.totals-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 14px;
  padding: 4px 0;
}

.totals-row dt {
  color: var(--ui-text-muted);
}

.totals-row dd {
  margin: 0;
  font-feature-settings: 'tnum';
  color: var(--ui-text);
}

.totals-row-discount dd {
  color: #16a34a;
}

.totals-grand {
  margin-top: 10px;
  padding-top: 12px;
  border-top: 1px solid var(--ui-border);
  font-size: 18px;
}

.totals-grand dt {
  color: var(--ui-text);
  font-weight: 600;
}

.totals-grand dd {
  font-weight: 800;
  font-size: 24px;
  color: var(--ui-primary);
}

/* ----- Trust strip ------------------------------------------------- */

.trust-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  list-style: none;
  margin: 0;
  padding: 12px 0;
  justify-content: center;
}

.trust-strip li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ui-text-muted);
}

/* ----- Reject link ------------------------------------------------- */

.reject-link {
  background: none;
  border: 0;
  color: var(--ui-text-muted);
  font-size: 13px;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
  padding: 6px 0;
  margin: 0 auto;
}

.reject-link:hover {
  color: var(--ui-text);
}

/* ----- Contact card ------------------------------------------------ */

.contact-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--ui-bg-elevated);
  border: 1px solid var(--ui-border);
}

.contact-title {
  margin: 0;
  font-size: 12px;
  color: var(--ui-text-muted);
}

.contact-name {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ui-text);
}

.contact-action {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  background: var(--ui-primary);
  color: white;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  transition: opacity 0.15s ease;
}

.contact-action:hover {
  opacity: 0.9;
}

/* ----- Mobile sticky CTA ------------------------------------------ */

.mobile-cta {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px env(safe-area-inset-bottom, 12px) 16px;
  background: var(--ui-bg);
  border-top: 1px solid var(--ui-border);
  box-shadow: 0 -8px 20px -10px rgba(0, 0, 0, 0.12);
  z-index: 40;
}

.mobile-cta-secondary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--ui-text-muted);
}

.mobile-cta-secondary button {
  background: none;
  border: 0;
  color: var(--ui-text-muted);
  cursor: pointer;
  padding: 4px 8px;
}

.mobile-cta-secondary button:hover {
  color: var(--ui-text);
}
</style>
