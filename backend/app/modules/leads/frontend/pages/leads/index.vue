<script setup lang="ts">
import type { SemanticRole } from '~~/app/config/severity'
import { PERMISSIONS } from '~~/app/config/permissions'
import { useLeads, type Lead, type LeadStatus } from '../../composables/useLeads'
import { hasAvailability } from '../../utils/leadAvailability'

/**
 * /leads — the enquiry queue.
 *
 * Deliberately absent: any notion of a "matched" enquiry. A matched
 * enquiry writes no row here (it becomes a recall), so a matched tab,
 * badge or counter would be a second, disagreeing view of the same
 * thing. The recall is the artefact.
 */
definePageMeta({ middleware: ['auth'] })

const { t, locale } = useI18n()
const { can } = usePermissions()

if (!can(PERMISSIONS.leads.read)) await navigateTo('/')

const leadsApi = useLeads()
const router = useRouter()

const canWrite = computed(() => can(PERMISSIONS.leads.write))
const canSeeSettings = computed(() => can(PERMISSIONS.leads.settingsRead))

const STATUSES: LeadStatus[] = ['new', 'contacted', 'converted', 'discarded']

// new → info, contacted → warning, converted → success, discarded → neutral.
const STATUS_ROLE: Record<LeadStatus, SemanticRole> = {
  new: 'info',
  contacted: 'warning',
  converted: 'success',
  discarded: 'neutral'
}

const AVATAR_TINT: Record<LeadStatus, string> = {
  new: 'bg-[var(--color-info-accent)]/15 text-[var(--color-info-accent)]',
  contacted: 'bg-[var(--color-warning-accent)]/15 text-[var(--color-warning-accent)]',
  converted: 'bg-[var(--color-success-accent)]/15 text-[var(--color-success-accent)]',
  discarded: 'bg-[var(--color-text-muted)]/15 text-[var(--color-text-muted)]'
}

interface LeadListFilters {
  q: string
  status: string[]
}

/**
 * The queue opens on the work that is still to do: **New** only, so
 * converted (and contacted/discarded) cards do not clutter the list of
 * enquiries nobody has called yet.
 *
 * This is a *visible* default, not a hidden backend exclusion: the status
 * chip renders as `Status · 1`, clearing it shows every status (converted
 * history included — a converted lead is marketing data, D6), and the API
 * still answers "no status param = all statuses" so no row is ever
 * silently unreachable.
 */
const DEFAULT_STATUS: LeadStatus[] = ['new']

const {
  filters,
  page,
  pageSize,
  sort,
  rows: leads,
  total,
  totalPages,
  isLoading,
  error,
  setFilter,
  resetFilters,
  refresh
} = useListQuery<LeadListFilters, Lead>({
  defaults: { q: '', status: [...DEFAULT_STATUS] },
  pageSize: 20,
  sortable: ['created_at', 'full_name', 'status'],
  defaultSort: 'created_at:desc',
  searchKey: 'q',
  fetcher: async (q) => {
    const response = await leadsApi.list({
      status: q.filters.status.length ? q.filters.status.join(',') : undefined,
      search: q.filters.q || undefined,
      page: q.page,
      page_size: q.pageSize,
      sort: q.sort
    })
    return { data: response.data, total: response.total }
  }
})

const statusItems = computed(() =>
  STATUSES.map(value => ({ value, label: t(`leads.status.${value}`) }))
)

const sortOptions = computed(() => [
  { field: 'created_at', label: t('leads.receivedAt'), defaultDir: 'desc' as const },
  { field: 'full_name', label: t('leads.fields.fullName'), defaultDir: 'asc' as const },
  { field: 'status', label: t('leads.fields.status'), defaultDir: 'asc' as const }
])

// The default selection is not a "filter the user applied": it must not
// light up the FilterBar reset button, and it must not turn the empty
// state into a bare "no results" (the routing hint below is the whole
// point of that screen).
function isDefaultStatus(selection: string[]): boolean {
  return [...selection].sort().join(',') === [...DEFAULT_STATUS].sort().join(',')
}

const activeFilterCount = computed(() => (isDefaultStatus(filters.value.status) ? 0 : 1))
const hasFilters = computed(() => activeFilterCount.value > 0 || Boolean(filters.value.q))

/** Leave the default Status: New behind and show the whole history. */
function showAllStatuses() {
  setFilter('status', [])
}

function statusRole(status: LeadStatus): SemanticRole {
  return STATUS_ROLE[status] ?? 'neutral'
}

function initials(fullName: string): string {
  const parts = (fullName || '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '?'
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase()
  return `${parts[0]![0]}${parts[parts.length - 1]![0]}`.toUpperCase()
}

/** Relative for the last week, an absolute date beyond that. */
function receivedLabel(iso: string): string {
  const days = Math.round((new Date(iso).getTime() - Date.now()) / 86_400_000)
  if (Math.abs(days) < 7) return new Intl.RelativeTimeFormat(locale.value, { numeric: 'auto' }).format(days, 'day')
  return new Date(iso).toLocaleDateString(locale.value)
}

// --- Drawer / modal wiring ------------------------------------------------

const drawerOpen = ref(false)
const selected = ref<Lead | null>(null)
const modalOpen = ref(false)
const editing = ref<Lead | null>(null)

function openLead(lead: Lead) {
  selected.value = lead
  drawerOpen.value = true
}

function openCreate() {
  editing.value = null
  modalOpen.value = true
}

function openEdit(lead: Lead) {
  editing.value = lead
  modalOpen.value = true
}

function onLeadSaved(lead: Lead) {
  if (selected.value?.id === lead.id) selected.value = lead
  void refresh()
}

function onLeadConverted(lead: Lead) {
  selected.value = lead
  void refresh()
}
</script>

<template>
  <!-- Single template root on purpose (repo convention, and what
       vue/no-multiple-template-root expects): the drawer and the modal are
       teleported by Nuxt UI, so the wrapper has no layout effect. -->
  <div>
    <DataListLayout
      :title="t('leads.title')"
      :subtitle="t('leads.subtitle')"
      :loading="isLoading"
      :empty="!leads.length"
      :error="error"
      :page="page"
      :page-size="pageSize"
      :total="total"
      :total-pages="totalPages"
      @update:page="(value) => (page = value)"
    >
      <template #actions>
        <UButton
          v-if="canWrite"
          color="primary"
          variant="soft"
          icon="i-lucide-plus"
          @click="openCreate"
        >
          {{ t('leads.newLead') }}
        </UButton>
        <UButton
          v-if="canSeeSettings"
          variant="outline"
          color="neutral"
          icon="i-lucide-globe"
          @click="router.push('/settings/integrations/leads')"
        >
          {{ t('leads.websiteForm') }}
        </UButton>
      </template>

      <template #toolbar>
        <FilterBar
          :active-count="activeFilterCount"
          @reset="resetFilters"
        >
          <template #search>
            <SearchBar
              :model-value="filters.q"
              :placeholder="t('leads.searchPlaceholder')"
              max-width="max-w-md"
              @update:model-value="(value) => setFilter('q', value)"
            />
          </template>

          <FilterChipMulti
            :model-value="filters.status"
            :items="statusItems"
            :label="t('leads.filterStatus')"
            icon="i-lucide-circle-dot"
            @update:model-value="(value) => setFilter('status', value)"
          />

          <template #right>
            <SortMenu
              :model-value="sort"
              :options="sortOptions"
              @update:model-value="(value) => (sort = value)"
            />
          </template>
        </FilterBar>
      </template>

      <template #empty>
        <!-- Default view (Status: New, nothing else touched): the empty state
           has to explain the routing rule, because a clinic that just wired
           the form and sees nothing will otherwise think it is broken. Any
           real filter gets the generic "no results" copy instead. -->
        <EmptyState
          icon="i-lucide-inbox"
          :title="hasFilters ? t('lists.empty.title') : t('leads.empty')"
          :description="hasFilters ? t('lists.empty.description') : t('leads.emptyHint')"
        >
          <template
            v-if="!hasFilters"
            #actions
          >
            <!-- An empty New queue is normal once the enquiries are worked.
               Offering the way out of the default filter is what stops
               "where did my leads go?" on a clinic that has history. -->
            <UButton
              variant="outline"
              color="neutral"
              icon="i-lucide-list-filter"
              @click="showAllStatuses"
            >
              {{ t('leads.filters.showAll') }}
            </UButton>
            <UButton
              variant="outline"
              color="neutral"
              icon="i-lucide-phone-call"
              @click="router.push('/recalls')"
            >
              {{ t('leads.routing.openRecalls') }}
            </UButton>
            <UButton
              v-if="canWrite"
              color="primary"
              variant="soft"
              icon="i-lucide-plus"
              @click="openCreate"
            >
              {{ t('leads.emptyAction') }}
            </UButton>
          </template>
        </EmptyState>
      </template>

      <template #rows>
        <DataListItem
          v-for="lead in leads"
          :key="lead.id"
        >
          <template #row>
            <!-- The whole row is the control (role=button, tabindex, Enter/Space).
               The arrow is a plain icon, never a nested button. -->
            <ListRow
              class="!px-0 !py-0 !mx-0"
              clickable
              @click="openLead(lead)"
            >
              <template #leading>
                <UAvatar
                  :alt="lead.full_name"
                  :text="initials(lead.full_name)"
                  size="sm"
                  :ui="{ fallback: AVATAR_TINT[lead.status] }"
                />
              </template>
              <template #title>
                <span class="truncate">{{ lead.full_name }}</span>
                <StatusBadge
                  :role="statusRole(lead.status)"
                  :label="t(`leads.status.${lead.status}`)"
                  size="xs"
                />
              </template>
              <!-- Motive first (it is what the call is about), then the
                   description — both trimmed; the full text is in the
                   drawer, which is one click away. -->
              <template #subtitle>
                <div class="min-w-0 w-full">
                  <div class="text-ui text-default truncate">
                    {{ lead.motive }}
                  </div>
                  <div class="text-caption text-subtle truncate">
                    <span dir="ltr">{{ lead.phone }}</span>
                    <span v-if="lead.description"> · {{ lead.description }}</span>
                  </div>
                </div>
              </template>
              <template #meta>
                <LeadAvailabilityWeek
                  v-if="hasAvailability(lead.availability_days, lead.availability_slot)"
                  class="hidden md:flex"
                  :days="lead.availability_days"
                  :time-slot="lead.availability_slot"
                />
                <span class="text-caption text-subtle whitespace-nowrap">
                  {{ receivedLabel(lead.created_at) }}
                </span>
              </template>
              <template #actions>
                <UIcon
                  name="i-lucide-chevron-right"
                  aria-hidden="true"
                  class="text-subtle"
                />
              </template>
            </ListRow>
          </template>

          <template #card>
            <div
              role="button"
              tabindex="0"
              class="flex flex-col gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] rounded-token-md"
              @click="openLead(lead)"
              @keydown.enter="openLead(lead)"
              @keydown.space.prevent="openLead(lead)"
            >
              <div class="flex items-center gap-3">
                <UAvatar
                  :alt="lead.full_name"
                  :text="initials(lead.full_name)"
                  size="md"
                  :ui="{ fallback: AVATAR_TINT[lead.status] }"
                />
                <div class="flex-1 min-w-0">
                  <div class="font-medium text-default truncate">
                    {{ lead.full_name }}
                  </div>
                  <div
                    class="text-caption text-subtle truncate"
                    dir="ltr"
                  >
                    {{ lead.phone }}
                  </div>
                </div>
                <StatusBadge
                  :role="statusRole(lead.status)"
                  :label="t(`leads.status.${lead.status}`)"
                  size="xs"
                  class="shrink-0"
                />
              </div>
              <div class="text-ui text-default truncate">
                {{ lead.motive }}
              </div>
              <div
                v-if="lead.description"
                class="text-caption text-subtle line-clamp-2"
              >
                {{ lead.description }}
              </div>
              <div class="flex items-center justify-between gap-2">
                <LeadAvailabilityWeek
                  :days="lead.availability_days"
                  :time-slot="lead.availability_slot"
                />
                <span class="text-caption text-subtle whitespace-nowrap">
                  {{ receivedLabel(lead.created_at) }}
                </span>
              </div>
            </div>
          </template>
        </DataListItem>
      </template>
    </DataListLayout>

    <LeadConvertDrawer
      v-model:open="drawerOpen"
      :lead="selected"
      @edit="(lead) => openEdit(lead)"
      @converted="onLeadConverted"
    />

    <LeadEditModal
      v-model:open="modalOpen"
      :lead="editing"
      @saved="onLeadSaved"
    />
  </div>
</template>
