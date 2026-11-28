<script setup lang="ts">
/**
 * Public online booking page (online_booking layer). Mounted at
 * `/p/booking/<clinicId>`; bypasses the global auth middleware like the other
 * `/p/*` screens and talks only to the cookie-free public endpoints under
 * `/api/v1/online_booking/public/<clinicId>` (same origin as the page).
 *
 * The same page serves three moments:
 *   - the booking form (no fragment),
 *   - the "check your email" notice once a request is queued,
 *   - the confirmation landing opened from the email: `#token=...`. The token
 *     lives in the URL fragment so servers, proxies and Referer headers never
 *     see it; it is stripped from the address bar on load and only sent by an
 *     explicit POST when the visitor presses the button.
 *
 * The clinic may embed this page in an iframe from its own website; the
 * allowed origins are the `embed_origins` setting, applied as `frame-ancestors`
 * by `server/utils/bookingEmbed.ts`.
 */
import {
  usePublicBooking,
  type PublicBookingConfig,
  type PublicReason
} from '../../../composables/usePublicBooking'
import { PublicBookingError } from '../../../utils/publicBookingError'
import {
  allowedParentOrigin,
  apiLanguage,
  dayDistance,
  offsetDay,
  postBookingHeight,
  safeUrl,
  splitDayParts,
  takeFragmentToken,
  todayIn,
  validClinicId
} from '../../../utils/publicBooking'

definePageMeta({ layout: 'public', publicChrome: false })
useHead({ meta: [{ name: 'referrer', content: 'no-referrer' }] })

const route = useRoute()
const { t, locale, locales, loadLocaleMessages } = useI18n()

const SUPPORTED = ['en', 'es', 'fr', 'pt', 'ta', 'te', 'hi', 'de', 'pl', 'it', 'hu', 'ar']
const ALTCHA_LANGUAGE: Record<string, string> = { pt: 'pt-pt' }

const clinicId = computed(() => String(route.params.clinicId || ''))
const validClinic = validClinicId(clinicId.value)
const api = usePublicBooking(clinicId.value)

type Stage = 'loading' | 'booking' | 'queued' | 'confirm' | 'confirmed' | 'unavailable'
const stage = ref<Stage>(validClinic ? 'loading' : 'unavailable')
const config = ref<PublicBookingConfig | null>(null)
const timezone = ref('UTC')
const errorKey = ref('')
const showRestart = ref(false)
const submitting = ref(false)
const confirmToken = ref<string | null>(null)
const resultStart = ref('')
const bookingRoot = ref<HTMLElement | null>(null)
let heightObserver: ResizeObserver | null = null
let parentOrigin = ''

function notifyParentHeight() {
  if (!parentOrigin || !bookingRoot.value || window.parent === window) return
  const rect = bookingRoot.value.getBoundingClientRect()
  const height = Math.ceil(rect.height + Math.max(0, rect.top + window.scrollY))
  postBookingHeight(window.parent, document.referrer, config.value?.embed_origins || [], height)
}

watch([config, stage], async () => {
  parentOrigin = ''
  if (window.parent === window || !document.referrer) return
  parentOrigin = allowedParentOrigin(document.referrer, config.value?.embed_origins || []) || ''
  await nextTick()
  notifyParentHeight()
})
onMounted(() => {
  if (bookingRoot.value && typeof ResizeObserver !== 'undefined') {
    heightObserver = new ResizeObserver(notifyParentHeight)
    heightObserver.observe(bookingRoot.value)
  }
  window.addEventListener('resize', notifyParentHeight)
})
onUnmounted(() => {
  heightObserver?.disconnect()
  window.removeEventListener('resize', notifyParentHeight)
})

// ----- language ---------------------------------------------------------------

const languageItems = computed(() => (locales.value as { code: string, name?: string }[])
  .filter(item => SUPPORTED.includes(item.code))
  .map(item => ({ label: item.name || item.code, value: item.code })))

const lang = computed(() => apiLanguage(locale.value))

async function setLanguage(code: string) {
  if (!SUPPORTED.includes(code) || code === locale.value) return
  // In memory only: persisting the cookie would overwrite the visitor's own
  // language choice for the staff application on the same origin.
  await loadLocaleMessages(code as never)
  locale.value = code as never
}

function localised(es: string | null | undefined, en: string | null | undefined, fallback: string) {
  if (locale.value === 'es') return es || fallback
  if (locale.value === 'en') return en || fallback
  return fallback
}

const heading = computed(() => localised(
  config.value?.branding.title_es, config.value?.branding.title_en, t('onlineBooking.public.title')
))
const intro = computed(() => localised(
  config.value?.branding.intro_es, config.value?.branding.intro_en, t('onlineBooking.public.intro')
))

function reasonName(reason: PublicReason) {
  return locale.value === 'es' ? reason.name_es : reason.name_en
}

// ----- branding ---------------------------------------------------------------

const accent = computed(() => {
  const value = config.value?.branding.accent_color || ''
  return /^#[0-9a-f]{6}$/i.test(value) ? value : '#127f83'
})
const logoSrc = computed(() =>
  config.value?.branding.logo_url === `/api/v1/online_booking/public/${clinicId.value}/logo`
    ? api.logoUrl
    : '')

// ----- availability -----------------------------------------------------------

const reasonId = ref('')
const firstDay = ref('')
const maxDays = ref(0)
const weekOffset = ref(0)
const chosenDay = ref('')
const selected = ref('')
const loadingSlots = ref(false)
const days = ref<Record<string, string[]>>({})

async function ensureDays(offset: number, count: number) {
  if (offset >= maxDays.value) return
  const response = await api.availability(
    offsetDay(firstDay.value, offset), Math.min(count, maxDays.value - offset), reasonId.value
  )
  const next = { ...days.value }
  for (const entry of response.days) next[entry.date] = entry.starts
  days.value = next
}

async function refreshAvailability() {
  loadingSlots.value = true
  selected.value = ''
  chosenDay.value = ''
  days.value = {}
  weekOffset.value = 0
  try {
    for (let offset = 0; offset < maxDays.value; offset += 31) {
      await ensureDays(offset, Math.min(31, maxDays.value - offset))
      const first = Object.entries(days.value).sort(([a], [b]) => a.localeCompare(b)).find(([, starts]) => starts.length)
      if (first) {
        chosenDay.value = first[0]
        weekOffset.value = Math.floor(dayDistance(firstDay.value, first[0]) / 7) * 7
        break
      }
    }
  } catch {
    errorKey.value = 'error'
  } finally {
    loadingSlots.value = false
  }
}

const weekDays = computed(() => {
  const list = []
  for (let i = 0; i < 7 && weekOffset.value + i < maxDays.value; i++) {
    const day = offsetDay(firstDay.value, weekOffset.value + i)
    list.push({
      day,
      enabled: (days.value[day] || []).length > 0,
      label: new Intl.DateTimeFormat(locale.value, { weekday: 'short', day: 'numeric', timeZone: 'UTC' })
        .format(new Date(`${day}T12:00:00Z`))
    })
  }
  return list
})

const weekLabel = computed(() => {
  if (!firstDay.value) return ''
  const format = new Intl.DateTimeFormat(locale.value, { day: 'numeric', month: 'short', timeZone: 'UTC' })
  const begin = offsetDay(firstDay.value, weekOffset.value)
  const end = offsetDay(firstDay.value, Math.min(weekOffset.value + 6, maxDays.value - 1))
  return `${format.format(new Date(`${begin}T12:00:00Z`))} – ${format.format(new Date(`${end}T12:00:00Z`))}`
})

const dayInView = computed(() => {
  if (!chosenDay.value) return false
  const distance = dayDistance(firstDay.value, chosenDay.value)
  return distance >= weekOffset.value && distance < weekOffset.value + 7
})
const slotsOfDay = computed(() => (dayInView.value ? days.value[chosenDay.value] || [] : []))
const slotGroups = computed(() => {
  const parts = splitDayParts(slotsOfDay.value, timezone.value)
  return [
    { key: 'morning', starts: parts.morning },
    { key: 'afternoon', starts: parts.afternoon }
  ].filter(group => group.starts.length)
})
const weekHasSlots = computed(() => weekDays.value.some(item => item.enabled))
const slotMessage = computed(() => {
  if (loadingSlots.value) return t('onlineBooking.public.loading')
  if (slotsOfDay.value.length) return ''
  if (!weekHasSlots.value && Object.values(days.value).every(starts => !starts.length)) {
    return t('onlineBooking.public.noAvailable')
  }
  return t(weekHasSlots.value ? 'onlineBooking.public.selectDay' : 'onlineBooking.public.weekEmpty')
})

function formatTime(iso: string) {
  return new Intl.DateTimeFormat(locale.value, { timeZone: timezone.value, hour: '2-digit', minute: '2-digit' })
    .format(new Date(iso))
}
function formatDayOf(iso: string) {
  return new Intl.DateTimeFormat(locale.value, {
    timeZone: timezone.value, weekday: 'long', day: 'numeric', month: 'long'
  }).format(new Date(iso))
}

function chooseDay(day: string) {
  chosenDay.value = day
  selected.value = ''
}
function previousWeek() {
  weekOffset.value = Math.max(0, weekOffset.value - 7)
}
const nextDisabled = computed(() => weekOffset.value + 7 >= maxDays.value || loadingSlots.value)
async function nextWeek() {
  const next = weekOffset.value + 7
  loadingSlots.value = true
  try {
    await ensureDays(next, 7)
    weekOffset.value = next
  } catch {
    errorKey.value = 'error'
  } finally {
    loadingSlots.value = false
  }
}

async function onReasonChange() {
  errorKey.value = ''
  await refreshAvailability()
}

// ----- form ---------------------------------------------------------------------

const form = reactive({
  firstName: '', lastName: '', email: '', phone: '', existing: '' as '' | 'yes' | 'no',
  comment: '', website: '', consent: false
})
const formEl = ref<HTMLFormElement | null>(null)
const altchaHost = ref<HTMLElement | null>(null)

const privacyHref = computed(() => safeUrl(config.value?.privacy_url))
const canSubmit = computed(() => !!privacyHref.value && !submitting.value)

async function phoneIsValid(value: string) {
  const { isValidPhoneNumber } = await import('libphonenumber-js/max')
  return isValidPhoneNumber(value.trim(), 'ES')
}

async function mountAltcha() {
  await nextTick()
  if (!altchaHost.value || altchaHost.value.querySelector('altcha-widget')) return
  await import('altcha/i18n')
  if (!altchaHost.value) return
  const widget = document.createElement('altcha-widget')
  widget.setAttribute('challenge', api.challengeUrl)
  widget.setAttribute('name', 'altcha')
  widget.setAttribute('language', ALTCHA_LANGUAGE[locale.value] || locale.value)
  altchaHost.value.append(widget)
}

watch(locale, (code) => {
  altchaHost.value?.querySelector('altcha-widget')
    ?.setAttribute('language', ALTCHA_LANGUAGE[code] || code)
})

function resetAltcha() {
  const widget = altchaHost.value?.querySelector('altcha-widget') as (HTMLElement & { reset?: () => void }) | null
  widget?.reset?.()
}

async function submit() {
  errorKey.value = ''
  showRestart.value = false
  if (!selected.value) {
    errorKey.value = 'selectSlot'
    return
  }
  if (!(await phoneIsValid(form.phone))) {
    errorKey.value = 'phoneHint'
    return
  }
  const proof = formEl.value ? new FormData(formEl.value).get('altcha') : null
  if (!proof || typeof proof !== 'string') {
    errorKey.value = 'verify'
    return
  }
  submitting.value = true
  try {
    await api.createRequest({
      start_time: selected.value,
      contact_name: `${form.firstName.trim()} ${form.lastName.trim()}`,
      contact_first_name: form.firstName.trim(),
      contact_last_name: form.lastName.trim(),
      existing_patient: form.existing ? form.existing === 'yes' : null,
      comment: form.comment.trim() || null,
      contact_email: form.email.trim(),
      contact_phone: form.phone.trim(),
      language: lang.value,
      reason: reasonId.value,
      website: form.website,
      altcha: proof
    })
    stage.value = 'queued'
    const target = safeUrl(config.value?.redirect_url)
    if (target) window.location.assign(target)
  } catch (error) {
    resetAltcha()
    const status = error instanceof PublicBookingError ? error.status : 0
    if (status === 409) {
      try {
        await ensureDays(weekOffset.value, 7)
        selected.value = ''
      } catch {
        // Keep the current calendar and report the conflict.
      }
    }
    errorKey.value = status === 409 ? 'conflict' : 'error'
  } finally {
    submitting.value = false
  }
}

async function confirm() {
  if (!confirmToken.value) return
  errorKey.value = ''
  showRestart.value = false
  submitting.value = true
  try {
    const result = await api.confirm(confirmToken.value)
    resultStart.value = result.start_time
    timezone.value = result.timezone || timezone.value
    confirmToken.value = null
    stage.value = 'confirmed'
  } catch (error) {
    const status = error instanceof PublicBookingError ? error.status : 0
    errorKey.value = status === 410 ? 'expired' : status === 409 ? 'conflict' : 'error'
    showRestart.value = true
  } finally {
    submitting.value = false
  }
}

function restart() {
  window.location.assign(window.location.pathname)
}

// ----- load -----------------------------------------------------------------------

async function loadBooking() {
  const received = await api.config()
  config.value = received
  timezone.value = received.timezone
  firstDay.value = todayIn(received.timezone)
  maxDays.value = received.window_days + 1
  if (!received.reasons.length) throw new Error('No active visit reasons')
  reasonId.value = received.reasons[0]!.id
  stage.value = 'booking'
  void mountAltcha().catch(() => {})
  await refreshAvailability()
}

onMounted(async () => {
  if (locale.value === 'pt-BR') await setLanguage('pt')
  if (!validClinic) return
  confirmToken.value = takeFragmentToken()
  if (confirmToken.value) {
    stage.value = 'confirm'
    // Branding is optional on the confirmation landing.
    api.config().then((received) => {
      config.value = received
      timezone.value = received.timezone
    }).catch(() => {})
    return
  }
  try {
    await loadBooking()
  } catch {
    stage.value = 'unavailable'
  }
})

const resultBodyValues = computed(() => {
  const start = stage.value === 'confirmed' ? resultStart.value : selected.value
  return start ? { day: formatDayOf(start), hour: formatTime(start) } : { day: '', hour: '' }
})
</script>

<template>
  <div
    ref="bookingRoot"
    class="mx-auto w-full max-w-3xl px-4 py-6 space-y-6"
    :dir="locale === 'ar' ? 'rtl' : 'ltr'"
    :style="{ '--booking-accent': accent }"
    data-testid="public-booking"
  >
    <header class="flex items-center justify-between gap-3">
      <div class="flex items-center gap-3 min-w-0">
        <img
          v-if="logoSrc"
          :src="logoSrc"
          alt=""
          class="max-h-12 max-w-40 object-contain"
          data-testid="booking-logo"
        >
      </div>
      <label class="flex items-center gap-2 text-sm">
        <span>{{ t('onlineBooking.public.language') }}</span>
        <select
          :value="locale"
          class="rounded-md border border-[var(--ui-border)] bg-[var(--ui-bg)] px-2 py-1"
          :aria-label="t('onlineBooking.public.language')"
          data-testid="booking-language"
          @change="setLanguage(($event.target as HTMLSelectElement).value)"
        >
          <option
            v-for="item in languageItems"
            :key="item.value"
            :value="item.value"
          >{{ item.label }}</option>
        </select>
      </label>
    </header>

    <div
      v-if="stage === 'loading'"
      class="space-y-3"
    >
      <USkeleton class="h-10 w-2/3" />
      <USkeleton class="h-48 w-full" />
    </div>

    <UCard v-else-if="stage === 'unavailable'">
      <p
        role="alert"
        class="text-center py-6"
        data-testid="booking-unavailable"
      >
        {{ t('onlineBooking.public.unavailable') }}
      </p>
    </UCard>

    <UCard v-else-if="stage === 'confirm'">
      <div class="space-y-4">
        <h1 class="text-xl font-semibold">
          {{ t('onlineBooking.public.confirmTitle') }}
        </h1>
        <p>{{ t('onlineBooking.public.confirmIntro') }}</p>
        <p
          v-if="errorKey"
          role="alert"
          class="text-sm text-[var(--ui-error)]"
          data-testid="booking-error"
        >
          {{ t(`onlineBooking.public.${errorKey}`) }}
        </p>
        <div class="flex flex-wrap items-center gap-3">
          <UButton
            :disabled="submitting"
            :style="{ backgroundColor: accent }"
            data-testid="booking-confirm"
            @click="confirm"
          >
            {{ t('onlineBooking.public.confirmButton') }}
          </UButton>
          <a
            v-if="showRestart"
            href="#"
            class="underline text-sm"
            @click.prevent="restart"
          >{{ t('onlineBooking.public.restart') }}</a>
        </div>
      </div>
    </UCard>

    <UCard v-else-if="stage === 'confirmed' || stage === 'queued'">
      <div
        class="space-y-3"
        data-testid="booking-result"
      >
        <h1 class="text-xl font-semibold">
          {{ t(stage === 'confirmed' ? 'onlineBooking.public.receivedTitle' : 'onlineBooking.public.queuedTitle') }}
        </h1>
        <p>
          {{ t(stage === 'confirmed' ? 'onlineBooking.public.receivedBody' : 'onlineBooking.public.queuedBody', resultBodyValues) }}
        </p>
        <a
          href="#"
          class="underline text-sm"
          @click.prevent="restart"
        >{{ t('onlineBooking.public.restart') }}</a>
      </div>
    </UCard>

    <template v-else>
      <div class="space-y-2">
        <h1
          class="text-2xl font-semibold"
          data-testid="booking-title"
        >
          {{ heading }}
        </h1>
        <p class="text-[var(--ui-text-muted)]">
          {{ intro }}
        </p>
      </div>

      <UCard>
        <div class="space-y-4">
          <h2 class="text-lg font-semibold">
            1. {{ t('onlineBooking.public.chooseTitle') }}
          </h2>
          <div class="space-y-1">
            <label
              for="booking-reason"
              class="block text-sm font-medium"
            >{{ t('onlineBooking.public.reason') }}</label>
            <select
              id="booking-reason"
              v-model="reasonId"
              :disabled="loadingSlots"
              class="w-full rounded-md border border-[var(--ui-border)] bg-[var(--ui-bg)] px-3 py-2"
              @change="onReasonChange"
            >
              <option
                v-for="reason in config?.reasons"
                :key="reason.id"
                :value="reason.id"
              >
                {{ reasonName(reason) }}
              </option>
            </select>
          </div>

          <div class="flex items-center justify-between gap-2">
            <UButton
              variant="outline"
              :disabled="weekOffset === 0"
              :aria-label="t('onlineBooking.public.previousWeek')"
              data-testid="booking-previous-week"
              @click="previousWeek"
            >
              ‹
            </UButton>
            <strong>{{ weekLabel }}</strong>
            <UButton
              variant="outline"
              :disabled="nextDisabled"
              :aria-label="t('onlineBooking.public.nextWeek')"
              data-testid="booking-next-week"
              @click="nextWeek"
            >
              ›
            </UButton>
          </div>

          <div
            class="grid grid-cols-7 gap-1"
            role="group"
            :aria-label="t('onlineBooking.public.date')"
          >
            <button
              v-for="item in weekDays"
              :key="item.day"
              type="button"
              :disabled="!item.enabled"
              :aria-pressed="item.day === chosenDay"
              class="rounded-md border px-1 py-2 text-sm disabled:opacity-40 disabled:cursor-not-allowed"
              :class="item.day === chosenDay ? 'text-white' : 'border-[var(--ui-border)]'"
              :style="item.day === chosenDay ? { backgroundColor: accent, borderColor: accent } : {}"
              data-testid="booking-day"
              @click="chooseDay(item.day)"
            >
              {{ item.label }}
            </button>
          </div>

          <h3 class="font-medium">
            {{ t('onlineBooking.public.slots') }}
          </h3>
          <p
            v-if="slotMessage"
            class="text-sm text-[var(--ui-text-muted)]"
            data-testid="booking-slot-message"
          >
            {{ slotMessage }}
          </p>
          <section
            v-for="group in slotGroups"
            :key="group.key"
            class="space-y-2"
          >
            <h4 class="text-sm font-medium">
              {{ t(`onlineBooking.public.${group.key}`) }}
            </h4>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="start in group.starts"
                :key="start"
                type="button"
                :aria-pressed="start === selected"
                class="rounded-md border px-3 py-1.5 text-sm"
                :class="start === selected ? 'text-white' : 'border-[var(--ui-border)]'"
                :style="start === selected ? { backgroundColor: accent, borderColor: accent } : {}"
                data-testid="booking-slot"
                @click="selected = start"
              >
                {{ formatTime(start) }}
              </button>
            </div>
          </section>
        </div>
      </UCard>

      <form
        ref="formEl"
        novalidate
        data-testid="booking-form"
        @submit.prevent="submit"
      >
        <UCard>
          <div class="space-y-4">
            <h2 class="text-lg font-semibold">
              2. {{ t('onlineBooking.public.contactTitle') }}
            </h2>
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="space-y-1">
                <label
                  for="booking-first-name"
                  class="block text-sm font-medium"
                >{{ t('onlineBooking.public.firstName') }}</label>
                <UInput
                  id="booking-first-name"
                  v-model="form.firstName"
                  autocomplete="given-name"
                  :maxlength="60"
                  required
                  class="w-full"
                />
              </div>
              <div class="space-y-1">
                <label
                  for="booking-last-name"
                  class="block text-sm font-medium"
                >{{ t('onlineBooking.public.lastName') }}</label>
                <UInput
                  id="booking-last-name"
                  v-model="form.lastName"
                  autocomplete="family-name"
                  :maxlength="59"
                  required
                  class="w-full"
                />
              </div>
              <div class="space-y-1">
                <label
                  for="booking-email"
                  class="block text-sm font-medium"
                >{{ t('onlineBooking.public.email') }}</label>
                <UInput
                  id="booking-email"
                  v-model="form.email"
                  type="email"
                  autocomplete="email"
                  :maxlength="254"
                  required
                  class="w-full"
                />
              </div>
              <div class="space-y-1">
                <label
                  for="booking-phone"
                  class="block text-sm font-medium"
                >{{ t('onlineBooking.public.phone') }}</label>
                <UInput
                  id="booking-phone"
                  v-model="form.phone"
                  type="tel"
                  autocomplete="tel"
                  :maxlength="30"
                  required
                  aria-describedby="booking-phone-hint"
                  class="w-full"
                />
                <small
                  id="booking-phone-hint"
                  class="text-[var(--ui-text-muted)]"
                >{{ t('onlineBooking.public.phoneHint') }}</small>
              </div>
            </div>

            <div
              v-if="config?.ask_existing_patient"
              class="space-y-1"
            >
              <label
                for="booking-existing"
                class="block text-sm font-medium"
              >{{ t('onlineBooking.public.existingPatient') }}</label>
              <select
                id="booking-existing"
                v-model="form.existing"
                class="w-full rounded-md border border-[var(--ui-border)] bg-[var(--ui-bg)] px-3 py-2"
              >
                <option value="">
                  —
                </option>
                <option value="yes">
                  {{ t('onlineBooking.public.yes') }}
                </option>
                <option value="no">
                  {{ t('onlineBooking.public.no') }}
                </option>
              </select>
            </div>

            <div
              v-if="config?.allow_comment"
              class="space-y-1"
            >
              <label
                for="booking-comment"
                class="block text-sm font-medium"
              >{{ t('onlineBooking.public.comment') }}</label>
              <UTextarea
                id="booking-comment"
                v-model="form.comment"
                :maxlength="500"
                aria-describedby="booking-comment-hint"
                class="w-full"
              />
              <small
                id="booking-comment-hint"
                class="text-[var(--ui-text-muted)]"
              >{{ t('onlineBooking.public.noMedical') }}</small>
            </div>

            <!-- Honeypot: invisible to people, tempting to bots. -->
            <input
              v-model="form.website"
              name="website"
              class="hidden"
              tabindex="-1"
              autocomplete="off"
              aria-hidden="true"
              data-testid="booking-honeypot"
            >

            <label class="flex items-start gap-2 text-sm">
              <input
                v-model="form.consent"
                type="checkbox"
                required
                class="mt-1"
                data-testid="booking-consent"
              >
              <span>
                <a
                  v-if="privacyHref"
                  :href="privacyHref"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="underline"
                >{{ t('onlineBooking.public.privacy') }}</a>
                <template v-else>{{ t('onlineBooking.public.privacy') }}</template>
              </span>
            </label>

            <div
              ref="altchaHost"
              data-testid="booking-altcha"
            />

            <p
              v-if="!privacyHref"
              role="alert"
              class="text-sm text-[var(--ui-error)]"
            >
              {{ t('onlineBooking.public.unavailable') }}
            </p>
            <p
              v-else-if="errorKey"
              role="alert"
              class="text-sm text-[var(--ui-error)]"
              data-testid="booking-error"
            >
              {{ t(`onlineBooking.public.${errorKey}`) }}
            </p>

            <div class="flex flex-wrap items-center justify-end gap-3">
              <UButton
                type="submit"
                :disabled="!canSubmit || !form.consent"
                :loading="submitting"
                :style="{ backgroundColor: accent }"
                data-testid="booking-submit"
              >
                {{ t('onlineBooking.public.submit') }}
              </UButton>
            </div>
          </div>
        </UCard>
      </form>
    </template>
  </div>
</template>
