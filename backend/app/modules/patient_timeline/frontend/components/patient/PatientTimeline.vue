<script setup lang="ts">
import type { TimelineEntry } from '~~/app/types'
import { resolveSlot } from '~~/app/composables/useModuleSlots'
import { PERMISSIONS } from '~~/app/config/permissions'

interface Props {
  patientId: string
}

const props = defineProps<Props>()

const { t, locale } = useI18n()
const { can } = usePermissions()

const patientIdRef = computed(() => props.patientId)

const {
  entries,
  total,
  hasMore,
  selectedCategory,
  isLoading,
  isLoadingMore,
  categoryOptions,
  loadMore,
  setCategory,
  getEventIcon,
  getCategoryColor,
  isHighImpact,
  isLowImpact
} = usePatientTimeline(patientIdRef)

// Professionals lookup — populates names for created_by and professional_id chips.
// Uses an endpoint that dentists, hygienists, receptionists can all call,
// unlike useUsers() which is admin-only.
const { professionals, fetchProfessionals, getProfessionalById, getProfessionalFullName } = useProfessionals()
onMounted(() => {
  if (professionals.value.length === 0) fetchProfessionals()
})

// Module extension point — other modules (e.g. treatment_plan) register
// richer views per category via the slot registry. When the user selects the
// "treatment" filter and a module has opted in, we render the slot INSTEAD of
// the generic event list so clinicians can see full clinical-note bodies
// grouped by plan/treatment. Keeps this module free of cross-module imports.
const treatmentSlotCtx = computed(() => ({ patientId: props.patientId }))
const treatmentSlotEntries = computed(() =>
  resolveSlot('patient.timeline.treatments', treatmentSlotCtx.value, { can })
)
const showTreatmentSlot = computed(
  () => selectedCategory.value === 'treatment' && treatmentSlotEntries.value.length > 0
)

// ---- Date formatting ---------------------------------------------------

const localeCode = computed(() => (locale.value === 'es' ? 'es-ES' : 'en-US'))

function formatTime(date: Date): string {
  return date.toLocaleTimeString(localeCode.value, { hour: '2-digit', minute: '2-digit' })
}

function formatEntryDate(dateStr: string): string {
  const date = new Date(dateStr)
  const bucket = bucketForDate(date)
  if (bucket === 'today') return `${t('patients.timeline.groups.today')} · ${formatTime(date)}`
  if (bucket === 'yesterday') return `${t('patients.timeline.groups.yesterday')} · ${formatTime(date)}`
  if (bucket === 'thisWeek') {
    return date.toLocaleDateString(localeCode.value, {
      weekday: 'long', hour: '2-digit', minute: '2-digit'
    })
  }
  return date.toLocaleDateString(localeCode.value, {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
  })
}

type Bucket = 'today' | 'yesterday' | 'thisWeek' | 'thisMonth' | 'earlier'

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

function bucketForDate(date: Date): Bucket {
  const now = new Date()
  const todayStart = startOfDay(now)
  const entryStart = startOfDay(date)
  const diffDays = Math.round((todayStart.getTime() - entryStart.getTime()) / 86400000)
  if (diffDays <= 0) return 'today'
  if (diffDays === 1) return 'yesterday'
  if (diffDays < 7) return 'thisWeek'
  // same calendar month
  if (date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth()) {
    return 'thisMonth'
  }
  return 'earlier'
}

const BUCKET_ORDER: Bucket[] = ['today', 'yesterday', 'thisWeek', 'thisMonth', 'earlier']

interface Group {
  bucket: Bucket
  label: string
  entries: TimelineEntry[]
}

const groupedEntries = computed<Group[]>(() => {
  const groups = new Map<Bucket, TimelineEntry[]>()
  for (const entry of entries.value) {
    const b = bucketForDate(new Date(entry.occurred_at))
    if (!groups.has(b)) groups.set(b, [])
    groups.get(b)!.push(entry)
  }
  return BUCKET_ORDER
    .filter(b => groups.has(b))
    .map(b => ({
      bucket: b,
      label: t(`patients.timeline.groups.${b}`),
      entries: groups.get(b)!
    }))
})

// ---- Event metadata chips ---------------------------------------------

interface MetaChip {
  icon: string
  label: string
}

const { format: formatCurrencyAmount } = useCurrency()

function formatMoney(value: unknown): string | null {
  const n = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN
  if (!isFinite(n)) return null
  return formatCurrencyAmount(n)
}

function getEventMeta(entry: TimelineEntry): MetaChip[] {
  const data = (entry.event_data ?? {}) as Record<string, unknown>
  const chips: MetaChip[] = []

  // Professional name (appointments, treatments)
  const professionalId = typeof data.professional_id === 'string' ? data.professional_id : null
  if (professionalId) {
    const prof = getProfessionalById(professionalId)
    if (prof) {
      chips.push({ icon: 'i-lucide-user-round', label: getProfessionalFullName(prof) })
    }
  }

  const cabinet = typeof data.cabinet === 'string' ? data.cabinet : null
  if (cabinet) {
    chips.push({
      icon: 'i-lucide-door-closed',
      label: t('patients.timeline.meta.cabinet', { name: cabinet })
    })
  }

  const teeth = Array.isArray(data.tooth_numbers) ? data.tooth_numbers : null
  if (teeth && teeth.length > 0) {
    chips.push({
      icon: 'i-lucide-tooth',
      label: t('patients.timeline.meta.teeth', { list: teeth.join(', ') })
    })
  }

  const budgetNumber = typeof data.budget_number === 'string' ? data.budget_number : null
  if (budgetNumber) {
    chips.push({
      icon: 'i-lucide-hash',
      label: t('patients.timeline.meta.number', { value: budgetNumber })
    })
  }

  const invoiceNumber = typeof data.invoice_number === 'string' ? data.invoice_number : null
  if (invoiceNumber) {
    chips.push({
      icon: 'i-lucide-hash',
      label: t('patients.timeline.meta.number', { value: invoiceNumber })
    })
  }

  const totalMoney = formatMoney(data.total)
  if (totalMoney) {
    chips.push({
      icon: 'i-lucide-euro',
      label: t('patients.timeline.meta.total', { amount: totalMoney })
    })
  }

  const sendMethod = typeof data.send_method === 'string' ? data.send_method : null
  if (sendMethod) {
    chips.push({
      icon: 'i-lucide-send',
      label: t('patients.timeline.meta.via', { channel: sendMethod })
    })
  }

  const templateKey = typeof data.template_key === 'string' ? data.template_key : null
  if (templateKey && entry.event_category === 'communication') {
    chips.push({
      icon: 'i-lucide-file-text',
      label: t('patients.timeline.meta.template', { key: templateKey })
    })
  }

  const docType = typeof data.document_type === 'string' ? data.document_type : null
  if (docType) {
    chips.push({
      icon: 'i-lucide-file',
      label: t('patients.timeline.meta.docType', { type: docType })
    })
  }

  return chips
}

// ---- Navigation to source ---------------------------------------------

// Only sources that have their own standalone page are clickable. Everything
// else (appointments, plans, notes, documents) already lives on this very
// patient record, so clicking would navigate to the page the user is on.
function getEntryLink(entry: TimelineEntry): string | null {
  if (entry.source_table === 'budgets' && can(PERMISSIONS.budget.read)) {
    return `/budgets/${entry.source_id}`
  }
  if (entry.source_table === 'invoices' && can(PERMISSIONS.billing.read)) {
    return `/invoices/${entry.source_id}`
  }
  return null
}

async function onEntryClick(entry: TimelineEntry) {
  const link = getEntryLink(entry)
  if (link) await navigateTo(link)
}

// ---- Author --------------------------------------------------------------

function getAuthorName(createdBy: string | undefined): string | null {
  if (!createdBy) return null
  const prof = getProfessionalById(createdBy)
  return prof ? getProfessionalFullName(prof) : null
}

// ---- Intersection observer for infinite scroll ------------------------

const loadMoreTrigger = ref<HTMLElement | null>(null)

onMounted(() => {
  if (!loadMoreTrigger.value) return

  const observer = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting && hasMore.value && !isLoadingMore.value) {
        loadMore()
      }
    },
    { threshold: 0.1 }
  )

  observer.observe(loadMoreTrigger.value)

  onUnmounted(() => {
    observer.disconnect()
  })
})
</script>

<template>
  <div class="patient-timeline">
    <!-- Category Filter -->
    <div class="flex flex-wrap gap-2 mb-4">
      <UButton
        v-for="option in categoryOptions"
        :key="option.value || 'all'"
        :variant="selectedCategory === option.value ? 'solid' : 'outline'"
        size="sm"
        @click="setCategory(option.value)"
      >
        {{ option.label }}
      </UButton>
    </div>

    <!-- Module-provided view for the active category (e.g. grouped clinical
         notes for "treatment"). When a module registers into
         patient.timeline.treatments, it takes over this region. -->
    <ModuleSlot
      v-if="showTreatmentSlot"
      name="patient.timeline.treatments"
      :ctx="treatmentSlotCtx"
    />

    <!-- Loading State -->
    <div
      v-else-if="isLoading"
      class="space-y-4"
    >
      <USkeleton
        v-for="i in 5"
        :key="i"
        class="h-20 w-full"
      />
    </div>

    <!-- Empty State — contextual -->
    <div
      v-else-if="entries.length === 0"
      class="text-center py-12 text-subtle"
    >
      <UIcon
        :name="selectedCategory ? 'i-lucide-filter-x' : 'i-lucide-clock'"
        class="w-12 h-12 mx-auto mb-4 opacity-50"
      />
      <p class="mb-3">
        {{ selectedCategory ? t('patients.timeline.emptyFiltered') : t('patients.timeline.empty') }}
      </p>
      <UButton
        v-if="selectedCategory"
        variant="outline"
        size="sm"
        @click="setCategory(null)"
      >
        {{ t('patients.timeline.clearFilter') }}
      </UButton>
    </div>

    <!-- Timeline Entries — grouped by time bucket -->
    <div
      v-else
      class="relative"
    >
      <!-- Timeline rail -->
      <div class="absolute start-4 top-0 bottom-0 w-0.5 bg-surface-sunken" />

      <div class="space-y-6">
        <section
          v-for="group in groupedEntries"
          :key="group.bucket"
          class="space-y-3"
        >
          <!-- Group header -->
          <h3 class="relative ps-10 text-caption font-medium text-muted uppercase tracking-wide">
            {{ group.label }}
          </h3>

          <div class="space-y-3">
            <div
              v-for="entry in group.entries"
              :key="entry.id"
              class="relative ps-10"
            >
              <!-- Timeline dot -->
              <div
                class="absolute start-2 top-1 w-5 h-5 rounded-full flex items-center justify-center"
                :class="`bg-${getCategoryColor(entry.event_category)}-100 dark:bg-${getCategoryColor(entry.event_category)}-900`"
              >
                <UIcon
                  :name="getEventIcon(entry.event_type)"
                  class="w-3 h-3"
                  :class="`text-${getCategoryColor(entry.event_category)}-600 dark:text-${getCategoryColor(entry.event_category)}-400`"
                />
              </div>

              <!-- Entry Card -->
              <UCard
                class="ms-2 transition-colors"
                :class="[
                  isHighImpact(entry.event_type) ? `border-l-4 border-l-${getCategoryColor(entry.event_category)}-500` : '',
                  isLowImpact(entry.event_type) ? 'opacity-85' : '',
                  getEntryLink(entry) ? 'cursor-pointer hover:bg-surface-muted' : ''
                ]"
                :ui="{ body: isLowImpact(entry.event_type) ? 'p-2' : 'p-3' }"
                @click="onEntryClick(entry)"
              >
                <div class="flex items-start justify-between gap-2">
                  <div class="min-w-0 flex-1">
                    <h4
                      :class="[
                        isHighImpact(entry.event_type) ? 'font-semibold text-default' : 'font-medium',
                        isLowImpact(entry.event_type) ? 'text-sm' : ''
                      ]"
                    >
                      {{ entry.title }}
                    </h4>
                    <p
                      v-if="entry.description"
                      class="text-caption text-muted mt-1 whitespace-pre-line"
                    >
                      {{ entry.description }}
                    </p>

                    <!-- Meta chips from event_data -->
                    <div
                      v-if="getEventMeta(entry).length > 0"
                      class="mt-2 flex flex-wrap gap-1.5"
                    >
                      <span
                        v-for="(chip, idx) in getEventMeta(entry)"
                        :key="idx"
                        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-sunken text-caption text-muted"
                      >
                        <UIcon
                          :name="chip.icon"
                          class="w-3 h-3"
                        />
                        {{ chip.label }}
                      </span>
                    </div>
                  </div>

                  <UIcon
                    v-if="getEntryLink(entry)"
                    name="i-lucide-chevron-right"
                    class="w-4 h-4 text-subtle shrink-0 mt-1"
                  />
                </div>

                <!-- Footer: date + optional author -->
                <div class="mt-2 flex items-center justify-between text-caption text-subtle">
                  <span>{{ formatEntryDate(entry.occurred_at) }}</span>
                  <span
                    v-if="getAuthorName(entry.created_by)"
                    class="inline-flex items-center gap-1"
                  >
                    <UIcon
                      name="i-lucide-user-round"
                      class="w-3 h-3"
                    />
                    {{ t('patients.timeline.author', { name: getAuthorName(entry.created_by) }) }}
                  </span>
                </div>
              </UCard>
            </div>
          </div>
        </section>

        <!-- Load More Trigger -->
        <div
          ref="loadMoreTrigger"
          class="h-4"
        />

        <!-- Loading More Indicator -->
        <div
          v-if="isLoadingMore"
          class="flex justify-center py-4"
        >
          <UIcon
            name="i-lucide-loader-2"
            class="w-6 h-6 animate-spin text-subtle"
          />
        </div>

        <!-- End of Timeline -->
        <div
          v-else-if="!hasMore && entries.length > 0"
          class="text-center py-4 text-caption text-subtle"
        >
          {{ t('patients.timeline.endOfTimeline') }}
        </div>
      </div>
    </div>

    <!-- Total Count -->
    <div
      v-if="total > 0"
      class="mt-4 text-caption text-subtle text-center"
    >
      {{ t('patients.timeline.totalEntries', { count: total }) }}
    </div>
  </div>
</template>

<style scoped>
.patient-timeline {
  width: 100%;
}
</style>
