<script setup lang="ts">
// Verifactu admin home.
//
// One status hero drives every state transition (setup → ready →
// active-test → active-prod). Configuration cards below are read-only
// summaries that link to their dedicated pages. The environment switch
// lives only in the hero so there is no conflicting control elsewhere.
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage as resolveErrorMessage } from '~~/app/utils/error'

const { t } = useI18n()
const { health, getSettings, updateSettings } = useVerifactu()
const { can } = usePermissions()

const summary = ref<Awaited<ReturnType<typeof health>> | null>(null)
const settings = ref<Awaited<ReturnType<typeof getSettings>> | null>(null)
const loading = ref(true)
const saving = ref(false)
const switchingEnv = ref(false)
const showProdConfirm = ref(false)
const errorMessage = ref<string | null>(null)

const canManage = computed(() => can(PERMISSIONS.verifactu.settingsConfigure))
const canPromoteToProd = computed(() => can(PERMISSIONS.verifactu.environmentPromote))

async function refresh() {
  loading.value = true
  try {
    summary.value = await health()
    settings.value = await getSettings()
  } finally {
    loading.value = false
  }
}

// Setup checklist — every prerequisite that must be true before the
// clinic can flip Verifactu on. Order matches the typical setup flow:
// clinic identity (NIF) first, then producer identity, then signing,
// then certificate.
interface SetupItem {
  key: string
  done: boolean
  to: string
  ctaKey: string
}

const setupItems = computed<SetupItem[]>(() => {
  const s = settings.value
  const sm = summary.value
  if (!s || !sm) return []
  return [
    {
      key: 'clinicNif',
      done: !!s.nif_emisor,
      to: '/settings',
      ctaKey: 'verifactu.setup.clinicNifCta'
    },
    {
      key: 'producer',
      done: !!s.producer_nif && !!s.producer_name,
      to: '/settings/verifactu/producer',
      ctaKey: 'verifactu.setup.producerCta'
    },
    {
      key: 'declaration',
      done: !!s.declaracion_responsable_signed_at,
      to: '/settings/verifactu/producer',
      ctaKey: 'verifactu.setup.declarationCta'
    },
    {
      key: 'certificate',
      done: sm.has_certificate,
      to: '/settings/verifactu/certificate',
      ctaKey: 'verifactu.setup.certificateCta'
    }
  ]
})

const setupComplete = computed(() => setupItems.value.every(i => i.done))

type HeroState = 'loading' | 'setup' | 'inactive' | 'active-test' | 'active-prod'

const heroState = computed<HeroState>(() => {
  if (loading.value || !settings.value) return 'loading'
  if (!setupComplete.value) return 'setup'
  if (!settings.value.enabled) return 'inactive'
  return settings.value.environment === 'prod' ? 'active-prod' : 'active-test'
})

const heroPalette = computed(() => {
  switch (heroState.value) {
    case 'setup':
      return { wrap: 'border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30', icon: 'text-amber-600', dot: 'bg-amber-500' }
    case 'inactive':
      return { wrap: 'border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900', icon: 'text-gray-500', dot: 'bg-gray-400' }
    case 'active-test':
      return { wrap: 'border-blue-300 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/30', icon: 'text-blue-600', dot: 'bg-blue-500' }
    case 'active-prod':
      return { wrap: 'border-emerald-400 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-950/30', icon: 'text-emerald-600', dot: 'bg-emerald-500' }
    default:
      return { wrap: 'border-gray-200 bg-gray-50', icon: 'text-gray-400', dot: 'bg-gray-300' }
  }
})

const heroIcon = computed(() => {
  switch (heroState.value) {
    case 'setup':
      return 'i-lucide-list-checks'
    case 'inactive':
      return 'i-lucide-power-off'
    case 'active-test':
      return 'i-lucide-flask-conical'
    case 'active-prod':
      return 'i-lucide-shield-check'
    default:
      return 'i-lucide-loader'
  }
})

async function toggleEnabled() {
  if (!settings.value || !canManage.value) return
  saving.value = true
  errorMessage.value = null
  try {
    settings.value = await updateSettings({ enabled: !settings.value.enabled })
    summary.value = await health()
  } catch (e: unknown) {
    errorMessage.value = resolveErrorMessage(e, 'Error')
  } finally {
    saving.value = false
  }
}

async function switchEnvironment(target: 'test' | 'prod') {
  if (!settings.value || !canManage.value) return
  if (target === 'prod') {
    if (!canPromoteToProd.value) {
      errorMessage.value = t('verifactu.errors.cannotPromoteToProd')
      return
    }
    showProdConfirm.value = true
    return
  }
  switchingEnv.value = true
  try {
    settings.value = await updateSettings({ environment: target })
  } finally {
    switchingEnv.value = false
  }
}

async function confirmProd() {
  switchingEnv.value = true
  try {
    settings.value = await updateSettings({ environment: 'prod' })
    showProdConfirm.value = false
  } finally {
    switchingEnv.value = false
  }
}

const certWarning = computed(() => {
  if (!summary.value || !summary.value.has_certificate || !summary.value.certificate_valid_until) return null
  const until = new Date(summary.value.certificate_valid_until)
  const days = Math.floor((until.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
  if (days < 0) return { color: 'red', message: t('verifactu.status.certificateExpired') }
  if (days < 60) return { color: days < 15 ? 'red' : 'amber', message: t('verifactu.status.certificateExpiringSoon', { days }) }
  return null
})

const certValidUntilFormatted = computed(() => {
  const v = summary.value?.certificate_valid_until
  return v ? new Date(v).toLocaleDateString() : null
})

onMounted(refresh)
</script>

<template>
  <div class="p-4 sm:p-6 max-w-5xl mx-auto space-y-6">
    <header>
      <h1 class="text-2xl font-semibold">
        {{ t('verifactu.title') }}
      </h1>
      <p class="text-sm text-gray-500">
        {{ t('verifactu.subtitle') }}
      </p>
    </header>

    <UAlert
      v-if="certWarning"
      :color="certWarning.color"
      variant="soft"
      :title="certWarning.message"
    />

    <USkeleton
      v-if="loading"
      class="h-44 w-full"
    />

    <!-- ─── HERO STATUS ─────────────────────────────────────────── -->
    <section
      v-else
      class="rounded-lg border p-5 sm:p-6 transition-colors"
      :class="heroPalette.wrap"
    >
      <div class="flex items-start gap-4">
        <UIcon
          :name="heroIcon"
          class="text-3xl shrink-0 mt-0.5"
          :class="heroPalette.icon"
        />

        <div class="flex-1 min-w-0">
          <h2 class="text-lg font-semibold">
            {{ t(`verifactu.hero.${heroState}.title`) }}
          </h2>
          <p class="text-sm text-gray-600 dark:text-gray-300 mt-0.5">
            {{ t(`verifactu.hero.${heroState}.description`) }}
          </p>

          <!-- ─── SETUP CHECKLIST ─────────────────────────────── -->
          <ul
            v-if="heroState === 'setup'"
            class="mt-4 space-y-2"
          >
            <li
              v-for="item in setupItems"
              :key="item.key"
              class="flex items-center gap-3 text-sm"
            >
              <UIcon
                :name="item.done ? 'i-lucide-check-circle-2' : 'i-lucide-circle'"
                :class="item.done ? 'text-emerald-600' : 'text-gray-400'"
              />
              <span :class="item.done ? 'line-through text-gray-500' : ''">
                {{ t(`verifactu.setup.${item.key}`) }}
              </span>
              <UButton
                v-if="!item.done && canManage"
                :to="item.to"
                size="xs"
                variant="soft"
                trailing-icon="i-lucide-arrow-right"
                class="ml-auto"
              >
                {{ t(item.ctaKey) }}
              </UButton>
            </li>
          </ul>

          <!-- ─── ENVIRONMENT + ACTIVATION CONTROLS ──────────── -->
          <div
            v-if="heroState !== 'setup' && heroState !== 'loading' && canManage"
            class="mt-5 flex flex-wrap items-center gap-3"
          >
            <UButton
              :loading="saving"
              :color="settings?.enabled ? 'gray' : 'primary'"
              :icon="settings?.enabled ? 'i-lucide-power-off' : 'i-lucide-power'"
              @click="toggleEnabled"
            >
              {{ t(settings?.enabled ? 'verifactu.hero.deactivate' : 'verifactu.hero.activate') }}
            </UButton>

            <span class="hidden sm:inline-block w-px h-5 bg-gray-300 dark:bg-gray-700" />

            <div class="flex items-center gap-2 text-sm">
              <span class="text-gray-500">{{ t('verifactu.environment.label') }}:</span>
              <UBadge
                :color="settings?.environment === 'prod' ? 'red' : 'gray'"
                variant="subtle"
              >
                {{ t(`verifactu.environment.${settings?.environment}`) }}
              </UBadge>
              <UButton
                v-if="settings?.environment === 'test' && canPromoteToProd"
                :loading="switchingEnv"
                variant="ghost"
                color="red"
                size="xs"
                trailing-icon="i-lucide-arrow-right"
                @click="switchEnvironment('prod')"
              >
                {{ t('verifactu.environment.switchToProd') }}
              </UButton>
              <UButton
                v-if="settings?.environment === 'prod'"
                :loading="switchingEnv"
                variant="ghost"
                size="xs"
                @click="switchEnvironment('test')"
              >
                {{ t('verifactu.environment.switchToTest') }}
              </UButton>
            </div>
          </div>

          <UAlert
            v-if="errorMessage"
            color="red"
            variant="soft"
            :title="errorMessage"
            class="mt-4"
            :close="true"
            @close="errorMessage = null"
          />
        </div>
      </div>
    </section>

    <!-- ─── CONFIGURATION CARDS ─────────────────────────────────── -->
    <div
      v-if="!loading"
      class="grid gap-4 grid-cols-1 sm:grid-cols-2"
    >
      <!-- Datos del emisor (read-only, edited from clinic settings) -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-building-2"
              class="text-primary-500"
            />
            <h2 class="font-semibold">
              {{ t('verifactu.cards.emisor.title') }}
            </h2>
          </div>
        </template>
        <div class="space-y-3 text-sm">
          <div>
            <span class="text-gray-500 block">{{ t('verifactu.settings.nifEmisor') }}</span>
            <span class="font-mono">{{ settings?.nif_emisor ?? '—' }}</span>
          </div>
          <div>
            <span class="text-gray-500 block">{{ t('verifactu.settings.nombreRazon') }}</span>
            <span>{{ settings?.nombre_razon_emisor ?? '—' }}</span>
          </div>
          <p class="text-xs text-gray-500 pt-1">
            {{ t('verifactu.cards.emisor.editHint') }}
          </p>
          <UButton
            to="/settings"
            size="xs"
            variant="soft"
            trailing-icon="i-lucide-arrow-right"
          >
            {{ t('verifactu.cards.emisor.editLink') }}
          </UButton>
        </div>
      </UCard>

      <!-- Certificado digital -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-key-round"
              class="text-primary-500"
            />
            <h2 class="font-semibold">
              {{ t('verifactu.certificate.title') }}
            </h2>
          </div>
        </template>
        <div class="space-y-3 text-sm">
          <div
            v-if="summary?.has_certificate"
            class="space-y-1"
          >
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-check-circle-2"
                class="text-emerald-600"
              />
              <span>{{ t('verifactu.certificate.active') }}</span>
            </div>
            <p
              v-if="certValidUntilFormatted"
              class="text-gray-500 text-xs"
            >
              {{ t('verifactu.certificate.validUntil') }}: {{ certValidUntilFormatted }}
            </p>
          </div>
          <div
            v-else
            class="flex items-center gap-2 text-amber-700"
          >
            <UIcon name="i-lucide-alert-triangle" />
            <span>{{ t('verifactu.certificate.noActive') }}</span>
          </div>
          <UButton
            to="/settings/verifactu/certificate"
            size="xs"
            variant="soft"
            trailing-icon="i-lucide-arrow-right"
          >
            {{ summary?.has_certificate ? t('verifactu.cards.manage') : t('verifactu.certificate.uploadButton') }}
          </UButton>
        </div>
      </UCard>

      <!-- Productor del SIF -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-file-signature"
              class="text-primary-500"
            />
            <h2 class="font-semibold">
              {{ t('verifactu.producer.title') }}
            </h2>
          </div>
        </template>
        <div class="space-y-3 text-sm">
          <div
            v-if="settings?.producer_name"
            class="space-y-1"
          >
            <p class="font-medium">
              {{ settings.producer_name }}
            </p>
            <p class="text-gray-500 font-mono text-xs">
              {{ settings.producer_nif }}
            </p>
            <div
              v-if="settings.declaracion_responsable_signed_at"
              class="flex items-center gap-2 text-emerald-700 text-xs pt-1"
            >
              <UIcon name="i-lucide-check-circle-2" />
              <span>{{ t('verifactu.producer.alreadySigned') }}</span>
            </div>
            <div
              v-else
              class="flex items-center gap-2 text-amber-700 text-xs pt-1"
            >
              <UIcon name="i-lucide-alert-triangle" />
              <span>{{ t('verifactu.producer.statusUnsigned') }}</span>
            </div>
          </div>
          <p
            v-else
            class="text-amber-700 text-xs"
          >
            {{ t('verifactu.cards.producer.empty') }}
          </p>
          <UButton
            to="/settings/verifactu/producer"
            size="xs"
            variant="soft"
            trailing-icon="i-lucide-arrow-right"
          >
            {{ t('verifactu.cards.manage') }}
          </UButton>
        </div>
      </UCard>

      <!-- AEAT VAT classification mapping -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-percent"
              class="text-primary-500"
            />
            <h2 class="font-semibold">
              {{ t('verifactu.cards.vatMapping.title') }}
            </h2>
          </div>
        </template>
        <div class="space-y-3 text-sm">
          <p class="text-gray-500 text-xs">
            {{ t('verifactu.cards.vatMapping.description') }}
          </p>
          <UButton
            to="/settings/verifactu/vat-mapping"
            size="xs"
            variant="soft"
            trailing-icon="i-lucide-arrow-right"
          >
            {{ t('verifactu.cards.manage') }}
          </UButton>
        </div>
      </UCard>

      <!-- Actividad (queue + records combined) -->
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-activity"
              class="text-primary-500"
            />
            <h2 class="font-semibold">
              {{ t('verifactu.cards.activity.title') }}
            </h2>
          </div>
        </template>
        <div class="space-y-3 text-sm">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <p class="text-gray-500 text-xs">
                {{ t('verifactu.queue.tabs.pending') }}
              </p>
              <p class="text-xl font-semibold">
                {{ summary?.pending_count ?? 0 }}
              </p>
            </div>
            <div>
              <p class="text-gray-500 text-xs">
                {{ t('verifactu.queue.tabs.rejected') }}
              </p>
              <p
                class="text-xl font-semibold"
                :class="(summary?.rejected_count ?? 0) > 0 ? 'text-red-600' : ''"
              >
                {{ summary?.rejected_count ?? 0 }}
              </p>
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <UButton
              to="/settings/verifactu/queue"
              size="xs"
              variant="soft"
              trailing-icon="i-lucide-arrow-right"
            >
              {{ t('verifactu.queue.title') }}
            </UButton>
            <UButton
              to="/settings/verifactu/records"
              size="xs"
              variant="soft"
              trailing-icon="i-lucide-arrow-right"
            >
              {{ t('verifactu.records.title') }}
            </UButton>
          </div>
        </div>
      </UCard>
    </div>

    <!-- ─── PROD CONFIRMATION MODAL ─────────────────────────────── -->
    <UModal v-model:open="showProdConfirm">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-alert-triangle"
                class="text-red-600 text-xl"
              />
              <h3 class="font-semibold">
                {{ t('verifactu.modal.confirmProdTitle') }}
              </h3>
            </div>
          </template>
          <p class="text-sm">
            {{ t('verifactu.environment.warningProd') }}
          </p>
          <template #footer>
            <div class="flex gap-2 justify-end">
              <UButton
                variant="ghost"
                @click="showProdConfirm = false"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                color="red"
                :loading="switchingEnv"
                @click="confirmProd"
              >
                {{ t('verifactu.modal.confirmProdAction') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>
  </div>
</template>
