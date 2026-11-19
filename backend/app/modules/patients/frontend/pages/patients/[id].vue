<script setup lang="ts">
/**
 * Patient detail — dashboard-first IA.
 *
 * The page hosts a persistent sticky header + a UTabs strip. Resumen is
 * a dashboard of smart-cards: each card lives in (and is registered by)
 * its owning module via the ``patient.summary.cards`` slot. The page
 * only fetches data from its own module (``/api/v1/patients/{id}/extended``);
 * cross-module data (appointments, plans, ledger, allergies, etc.) is
 * fetched by the modules that own it inside their slot components.
 *
 * Cross-module data that the page used to fetch (emergency contact,
 * legal guardian, alerts, appointments, plans) now reaches the page
 * only through ``PatientExtended.active_alerts`` / the
 * patients_clinical slots — the page no longer reaches into other
 * modules' APIs directly.
 */
import type { PatientExtended, ApiResponse } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'
import { PERMISSIONS } from '~~/app/config/permissions'
import { parseDateOnly } from '~~/app/utils/wallClock'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const api = useApi()
const toast = useToast()
const { can } = usePermissions()
const { resolve } = useModuleSlots()

const patientId = route.params.id as string
const patientIdRef = computed(() => patientId)

// Handle returnTo query param (from invoice edit page)
const returnTo = computed(() => route.query.returnTo as string | undefined)

// Fetch patient identity from the patients module. The Resumen smart-
// cards each fetch their own module's data via slot registration; the
// page no longer mediates that traffic. The Datos tab still consumes
// patients_clinical data through the legacy stitching below (emergency
// contact, legal guardian, alerts) — that surface will move to
// patients_clinical-owned cards in a follow-up; the goal of this PR is
// to land the new IA without regressing Datos.
const { data: patient, status, refresh } = await useAsyncData(
  `patient:${patientId}`,
  async () => {
    try {
      const [identity, emergency, guardian, alertsResp] = await Promise.all([
        api.get<ApiResponse<PatientExtended>>(
          `/api/v1/patients/${patientId}/extended`
        ),
        api.get<ApiResponse<PatientExtended['emergency_contact']>>(
          `/api/v1/patients_clinical/patients/${patientId}/emergency-contact`
        ).catch(() => ({ data: null })),
        api.get<ApiResponse<PatientExtended['legal_guardian']>>(
          `/api/v1/patients_clinical/patients/${patientId}/legal-guardian`
        ).catch(() => ({ data: null })),
        api.get<ApiResponse<{ alerts: PatientExtended['active_alerts'] }>>(
          `/api/v1/patients_clinical/patients/${patientId}/alerts`
        ).catch(() => ({ data: { alerts: [] } }))
      ])

      return {
        ...identity.data,
        emergency_contact: emergency.data ?? undefined,
        legal_guardian: guardian.data ?? undefined,
        active_alerts: alertsResp.data?.alerts ?? []
      } as PatientExtended
    } catch (error: unknown) {
      const fetchError = error as { statusCode?: number }
      if (fetchError.statusCode === 404) {
        throw createError({
          statusCode: 404,
          message: t('patients.notFound')
        })
      }
      throw error
    }
  }
)

// Medical-history composable lives in patients_clinical but is shared
// via auto-import. We only need it here to drive the section-edit modal
// (medical history form). The Resumen surfaces the same data through a
// patients_clinical-owned card.
const { medicalHistory, isSaving: isSavingMedical, saveMedicalHistory } = useMedicalHistory(patientIdRef)

// Tabs — Resumen is the landing.
const activeTab = ref('summary')

watch(
  () => route.query.tab,
  (tab) => {
    if (tab && typeof tab === 'string') {
      activeTab.value = tab
    } else {
      activeTab.value = 'summary'
    }
  },
  { immediate: true }
)

const patientTabsContext = computed(() => ({ patientId }))
const registeredTabs = computed(() =>
  resolve('patient.detail.tabs', patientTabsContext.value).flatMap(entry =>
    entry.labelKey ? [{ ...entry, label: t(entry.labelKey) }] : []
  )
)

const tabs = computed(() => {
  const items: Array<{ value: string, label: string, icon?: string, slot: string }> = [
    {
      value: 'summary',
      label: t('patientDetail.tabs.summary'),
      icon: 'i-lucide-layout-dashboard',
      slot: 'summary'
    },
    {
      value: 'info',
      label: t('patientDetail.tabs.info'),
      icon: 'i-lucide-user',
      slot: 'info'
    }
  ]

  if (can(PERMISSIONS.odontogram.read) || can(PERMISSIONS.treatmentPlans.read)) {
    items.push({
      value: 'clinical',
      label: t('patientDetail.tabs.clinical'),
      icon: 'i-lucide-stethoscope',
      slot: 'clinical'
    })
  }

  if (can(PERMISSIONS.budget.read) || can(PERMISSIONS.billing.read)) {
    items.push({
      value: 'administration',
      label: t('patientDetail.tabs.administration'),
      icon: 'i-lucide-briefcase',
      slot: 'administration'
    })
  }

  if (can(PERMISSIONS.documents.read)) {
    items.push({
      value: 'gallery',
      label: t('patientDetail.tabs.gallery', 'Galería'),
      icon: 'i-lucide-images',
      slot: 'gallery'
    })
  }

  items.push({
    value: 'timeline',
    label: t('patientDetail.tabs.timeline'),
    icon: 'i-lucide-history',
    slot: 'timeline'
  })

  for (const entry of registeredTabs.value) {
    items.push({ value: entry.id, label: entry.label, slot: 'registered-tab' })
  }
  return items
})

// Permissions used by Datos tab + edit modals.
const canEditMedicalHistory = computed(() => can(PERMISSIONS.medicalHistory.write))
const canEditPatient = computed(() => can(PERMISSIONS.patients.write))

// Section edit modals state
type SectionType = 'demographics' | 'emergency' | 'guardian' | 'billing' | 'medical'
const editModalOpen = ref(false)
const editModalSection = ref<SectionType>('demographics')
const isSubmitting = ref(false)

function openSectionModal(section: SectionType) {
  editModalSection.value = section
  editModalOpen.value = true
}

// Deep-link to a section modal: ?tab=info&edit=medical (medical-history
// card) or ?tab=info&edit=billing (invoice pages, with returnTo).
watch(
  [() => route.query.edit, () => patient.value],
  ([edit]) => {
    if ((edit === 'medical' || edit === 'billing') && patient.value && !editModalOpen.value) {
      openSectionModal(edit)
    }
  },
  { immediate: true }
)

async function handleSectionSave(_section: SectionType, _data: Record<string, unknown>) {
  await refresh()
}

async function handleMedicalSave() {
  const success = await saveMedicalHistory()
  if (success) {
    editModalOpen.value = false
  }
}

// Resumen smart-cards come from the slot registry. We read the live
// entries so we can show a sensible empty state when no module has
// registered cards yet (e.g. fresh install).
const summaryCards = computed(() =>
  patient.value ? resolve('patient.summary.cards', { patient: patient.value }) : []
)

// Archive patient
const isArchiveModalOpen = ref(false)

async function archivePatient() {
  isSubmitting.value = true

  try {
    // Failures are toasted by the catch below — keep single-toast.
    await api.del(`/api/v1/patients/${patientId}`, { errorToast: false })

    toast.add({
      title: t('common.success'),
      description: t('patients.archived'),
      color: 'success'
    })

    await router.push('/patients')
  } catch (error: unknown) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(error, t('common.serverError')),
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
    isArchiveModalOpen.value = false
  }
}

// Check if patient is a minor (under 18)
const isMinor = computed(() => {
  if (!patient.value?.date_of_birth) return false
  const today = new Date()
  const birth = parseDateOnly(patient.value.date_of_birth)
  let years = today.getFullYear() - birth.getFullYear()
  const m = today.getMonth() - birth.getMonth()
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) years--
  return years < 18
})

// Header action handlers — delegate to existing flows. New-appointment
// and new-note land on dedicated pages we already have.
function goBack() {
  if (returnTo.value) {
    router.push(returnTo.value)
  } else {
    router.push('/patients')
  }
}

function openEditPatient() {
  openSectionModal('demographics')
}

function newAppointment() {
  // Send the user to the agenda with `patient_id` in the URL. The agenda
  // reads it into `initialPatientId` and forwards it to the create modal
  // when the user picks a slot. No auto-open — the slot decides the
  // date / time / cabinet.
  router.push(`/appointments?patient_id=${patientId}`)
}

function newNote() {
  // Clinical-notes module owns the composer; we deep-link into the
  // Resumen feed where it lives. A future iteration may expose a
  // dedicated slot for "open composer" — keep it as a simple route
  // change for now.
  router.push(`/patients/${patientId}?tab=summary#new-note`)
}

function collect() {
  router.push(`/patients/${patientId}?tab=administration&adminMode=payments`)
}
</script>

<template>
  <div class="patient-detail space-y-4 pb-24 lg:pb-6">
    <!-- Loading state -->
    <div
      v-if="status === 'pending'"
      class="space-y-4"
    >
      <USkeleton class="h-12 w-full" />
      <USkeleton class="h-96 w-full" />
    </div>

    <!-- Patient content -->
    <template v-else-if="patient">
      <!-- Return to invoice banner -->
      <div
        v-if="returnTo"
        class="alert-surface-info rounded-token-md px-3 py-2 flex items-center justify-between gap-3"
        role="status"
      >
        <span class="text-body">
          {{ t('patients.editingBillingForInvoice') }}
        </span>
        <UButton
          variant="soft"
          color="primary"
          size="sm"
          icon="i-lucide-arrow-left"
          :to="returnTo"
        >
          {{ t('patients.returnToInvoice') }}
        </UButton>
      </div>

      <!-- Persistent header — stays visible across all tabs. -->
      <PatientStickyHeader
        :patient="patient"
        @back="goBack"
        @edit="openEditPatient"
        @new-appointment="newAppointment"
        @new-note="newNote"
        @collect="collect"
        @archive="isArchiveModalOpen = true"
      />

      <main class="w-full min-w-0">
        <UTabs
          v-model="activeTab"
          :items="tabs"
          default-value="summary"
          class="w-full"
          :ui="{ content: 'overflow-visible' }"
        >
          <!-- Resumen — smart-card grid + clinical-notes feed.
               The whole Resumen body is slot-driven; modules register
               their cards via `.client.ts` plugins that only run after
               hydration. Wrapping in <ClientOnly> keeps the SSR tree
               aligned with the client tree (an identically-shaped
               skeleton grid) so Vue doesn't hit hydration mismatches
               that re-layout the page after refresh. -->
          <template #summary>
            <ClientOnly>
              <div class="mt-4 space-y-4 overflow-visible">
                <div
                  v-if="summaryCards.length === 0"
                  class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 lg:gap-4"
                >
                  <div
                    class="md:col-span-2 xl:col-span-3 rounded-token-md border border-dashed border-default px-4 py-8 text-center text-muted"
                  >
                    {{ t('patientDetail.noSummaryCards', 'No hay módulos registrados en el resumen.') }}
                  </div>
                </div>
                <div
                  v-else
                  class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 lg:gap-4"
                >
                  <component
                    :is="entry.component"
                    v-for="entry in summaryCards"
                    :key="entry.id"
                    :ctx="{ patient }"
                  />
                </div>

                <section id="new-note">
                  <ModuleSlot
                    name="patient.summary.feed"
                    :ctx="{ patient }"
                  />
                </section>

                <ModuleSlot
                  name="patient.detail.sidebar"
                  :ctx="{ patient }"
                />
              </div>

              <template #fallback>
                <div class="mt-4 space-y-4">
                  <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 lg:gap-4">
                    <USkeleton
                      v-for="i in 6"
                      :key="i"
                      class="h-36 w-full rounded-token-lg"
                    />
                  </div>
                  <USkeleton class="h-40 w-full rounded-token-lg" />
                </div>
              </template>
            </ClientOnly>
          </template>

          <!-- Datos tab content -->
          <template #info>
            <div class="mt-4 space-y-3 lg:space-y-4 overflow-visible">
              <MedicalSnapshotCard
                :medical-history="medicalHistory"
                :active-alerts="patient.active_alerts"
                :can-edit="canEditMedicalHistory"
                @edit="openSectionModal('medical')"
                @complete-history="openSectionModal('medical')"
              />

              <PersonalInfoCard
                :patient="patient"
                :can-edit="canEditPatient"
                @edit="openSectionModal('demographics')"
              />

              <ContactInfoCard
                :patient="patient"
                :is-minor="isMinor"
                :can-edit="canEditPatient"
                @edit-contact="openSectionModal('demographics')"
                @edit-emergency="openSectionModal('emergency')"
                @edit-guardian="openSectionModal('guardian')"
              />

              <AdministrativeCard
                :patient="patient"
                :can-edit="canEditPatient"
                @edit="openSectionModal('billing')"
              />

              <!-- Danger zone -->
              <div class="alert-surface-danger rounded-token-lg px-4 py-3 flex items-center justify-between gap-4">
                <div class="min-w-0">
                  <div class="text-ui">
                    {{ t('patients.dangerZone.title') }}
                  </div>
                  <div class="text-caption">
                    {{ t('patients.dangerZone.archiveHelp') }}
                  </div>
                </div>
                <UButton
                  variant="outline"
                  color="error"
                  icon="i-lucide-archive"
                  size="sm"
                  @click="isArchiveModalOpen = true"
                >
                  {{ t('patients.archive') }}
                </UButton>
              </div>
            </div>
          </template>

          <!-- Clinical tab content (Odontogram + Treatment Plans) -->
          <template #clinical>
            <div class="mt-4">
              <ClinicalTab
                :patient-id="patientId"
                :readonly="!can(PERMISSIONS.odontogram.write)"
              />
            </div>
          </template>

          <!-- Administration tab content (Budgets + Billing + Payments) -->
          <template #administration>
            <div class="mt-4">
              <AdministrationTab
                :patient-id="patientId"
                :patient="patient"
              />
            </div>
          </template>

          <!-- Gallery tab content -->
          <template #gallery>
            <UCard class="mt-4">
              <PhotoGallery :patient-id="patientId" />
            </UCard>
          </template>

          <!-- Timeline tab content -->
          <template #timeline>
            <UCard class="mt-4">
              <PatientTimeline :patient-id="patientId" />
            </UCard>
          </template>
          <template #registered-tab="{ item }">
            <component
              :is="registeredTabs.find(entry => entry.id === item.value)?.component"
              :ctx="patientTabsContext"
            />
          </template>
        </UTabs>
      </main>

      <!-- Mobile bottom action bar -->
      <PatientBottomActionBar
        :patient="patient"
        @new-appointment="newAppointment"
        @collect="collect"
        @new-note="newNote"
      />
    </template>

    <!-- Section Edit Modal -->
    <PatientSectionEditModal
      v-if="patient"
      v-model:open="editModalOpen"
      :section="editModalSection"
      :patient="patient"
      :medical-history="medicalHistory"
      :is-saving-medical="isSavingMedical"
      @save="handleSectionSave"
      @save-medical="handleMedicalSave"
    />

    <!-- Archive confirmation modal -->
    <UModal v-model:open="isArchiveModalOpen">
      <template #content>
        <UCard>
          <template #header>
            <h2 class="text-h1 text-default">
              {{ t('patients.archiveConfirm', { name: `${patient?.first_name} ${patient?.last_name}` }) }}
            </h2>
          </template>
          <p class="text-body text-muted">
            {{ t('patients.archiveDescription') }}
          </p>
          <template #footer>
            <div class="flex justify-end gap-3">
              <UButton
                variant="outline"
                color="neutral"
                @click="isArchiveModalOpen = false"
              >
                {{ t('patients.cancel') }}
              </UButton>
              <UButton
                color="error"
                :loading="isSubmitting"
                @click="archivePatient"
              >
                {{ t('patients.archive') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>
  </div>
</template>
