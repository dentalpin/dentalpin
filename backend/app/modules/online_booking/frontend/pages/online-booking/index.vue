<script setup lang="ts">
import type { ApiResponse, PaginatedResponse } from '~~/app/types'
import { errorMessage, errorStatus } from '~~/app/utils/error'

definePageMeta({ middleware: ['auth'] })

type BookingStatus = 'pending_confirmation' | 'confirmed'
interface BookingRequest {
  id: string
  status: BookingStatus
  start_time: string
  end_time: string
  contact_name: string
  contact_email: string
  contact_phone: string | null
  reason: 'first_visit' | 'checkup'
  default_duration_minutes: number
}
interface Resource { id: string, first_name?: string, last_name?: string, name?: string, is_active?: boolean }
interface PatientChoice { id: string, first_name: string, last_name: string, phone?: string | null, email?: string | null, date_of_birth?: string | null }

const { t, locale } = useI18n()
const { can } = usePermissions()
const { currentClinic } = useClinic()
const api = useApi()
const dataBus = useDataBus()
if (!can('online_booking.read')) await navigateTo('/')
const canWrite = computed(() => can('online_booking.write'))
const canAccept = computed(() => canWrite.value && can('agenda.appointments.write') && can('patients.write'))
const items = ref<BookingRequest[]>([])
const page = ref(1)
const hasMore = ref(false)
const success = ref('')
const loading = ref(true)
const loadError = ref('')
const selected = ref<BookingRequest | null>(null)
const action = ref<'accept' | 'reject' | null>(null)
const patientMode = ref<'existing' | 'new'>('existing')
const patientQuery = ref('')
const patientResults = ref<PatientChoice[]>([])
const patient = ref<PatientChoice | null>(null)
const patientLoading = ref(false)
const searched = ref(false)
const patientError = ref('')
const firstName = ref('')
const lastName = ref('')
const email = ref('')
const phone = ref('')
const professionalId = ref('')
const cabinetId = ref('__none__')
const duration = ref(30)
const professionals = ref<Resource[]>([])
const cabinets = ref<Resource[]>([])
const message = ref('')
const saving = ref(false)
const formError = ref('')
let searchVersion = 0

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await api.get<PaginatedResponse<BookingRequest>>('/api/v1/online_booking/requests', { errorToast: false, query: { page: page.value } })
    items.value = response.data
    hasMore.value = response.page * response.page_size < response.total
  } catch {
    loadError.value = t('onlineBooking.loadError')
  } finally {
    loading.value = false
  }
}

function open(row: BookingRequest, mode: 'accept' | 'reject') {
  success.value = ''
  selected.value = row
  action.value = mode
  patientMode.value = 'existing'
  patient.value = null
  patientQuery.value = ''
  patientResults.value = []
  patientError.value = ''
  searched.value = false
  const names = row.contact_name.trim().split(/\s+/)
  firstName.value = names.length === 2 ? names[0]! : row.contact_name.trim()
  lastName.value = names.length === 2 ? names[1]! : ''
  email.value = row.contact_email || ''
  phone.value = row.contact_phone || ''
  duration.value = row.default_duration_minutes || Math.round((Date.parse(row.end_time) - Date.parse(row.start_time)) / 60000)
  professionalId.value = ''
  cabinetId.value = '__none__'
  message.value = ''
  formError.value = ''
  searchVersion++
  if (mode === 'accept') void nextTick(() => prepareAcceptance(row))
}

async function prepareAcceptance(row: BookingRequest) {
  const version = ++searchVersion
  const [staff, rooms, matches] = await Promise.allSettled([
    api.get<ApiResponse<Resource[]>>('/api/v1/auth/professionals'),
    api.get<ApiResponse<Resource[]>>('/api/v1/agenda/cabinets'),
    api.get<ApiResponse<PatientChoice[]>>(`/api/v1/online_booking/requests/${row.id}/patient-suggestions`, { errorToast: false })
  ])
  if (selected.value?.id !== row.id || action.value !== 'accept') return
  professionals.value = staff.status === 'fulfilled' ? staff.value.data : []
  cabinets.value = rooms.status === 'fulfilled' ? rooms.value.data.filter(room => room.is_active !== false) : []
  if (staff.status === 'rejected' || rooms.status === 'rejected') formError.value = t('onlineBooking.resourcesRequired')
  if (version !== searchVersion) return
  patientResults.value = matches.status === 'fulfilled' ? matches.value.data : []
  searched.value = true
  if (matches.status === 'rejected') patientError.value = t('onlineBooking.searchError')
}

function close() {
  if (saving.value) return
  selected.value = null
  action.value = null
  searchVersion++
}

watch(patientQuery, () => {
  searchVersion++
  patientResults.value = []
  patientLoading.value = false
  patientError.value = ''
  searched.value = false
})

async function searchPatients() {
  const query = patientQuery.value.trim()
  if (query.length < 2) return
  const version = ++searchVersion
  patientLoading.value = true
  patientError.value = ''
  patientResults.value = []
  try {
    const result = await api.get<PaginatedResponse<PatientChoice>>(`/api/v1/patients?search=${encodeURIComponent(query)}&page_size=10`, { errorToast: false })
    if (version === searchVersion) {
      patientResults.value = result.data
      searched.value = true
    }
  } catch {
    if (version === searchVersion) patientError.value = t('onlineBooking.searchError')
  } finally {
    if (version === searchVersion) patientLoading.value = false
  }
}

async function submit() {
  if (!selected.value || !action.value || saving.value) return
  if (action.value === 'accept' && patientMode.value === 'existing' && !patient.value) {
    formError.value = t('onlineBooking.selectPatient')
    return
  }
  if (action.value === 'accept' && patientMode.value === 'new' && (!firstName.value.trim() || !lastName.value.trim())) {
    formError.value = t('onlineBooking.nameRequired')
    return
  }
  if (action.value === 'accept' && (!professionalId.value || duration.value < 5 || duration.value > 480)) {
    formError.value = t('onlineBooking.resourcesRequired')
    return
  }
  if (action.value === 'reject' && !message.value.trim()) {
    formError.value = t('onlineBooking.messageRequired')
    return
  }
  saving.value = true
  formError.value = ''
  try {
    const id = selected.value.id
    if (action.value === 'accept') {
      const body = patientMode.value === 'existing'
        ? { patient_id: patient.value!.id, professional_id: professionalId.value, cabinet_id: cabinetId.value === '__none__' ? null : cabinetId.value, duration_minutes: Number(duration.value) }
        : { first_name: firstName.value.trim(), last_name: lastName.value.trim(), email: email.value.trim() || null, phone: phone.value.trim() || null, professional_id: professionalId.value, cabinet_id: cabinetId.value === '__none__' ? null : cabinetId.value, duration_minutes: Number(duration.value) }
      await api.post(`/api/v1/online_booking/requests/${id}/accept`, body, { errorToast: false })
    } else {
      await api.post(`/api/v1/online_booking/requests/${id}/reject`, { message: message.value.trim() }, { errorToast: false })
    }
    dataBus.publish('online_booking')
    success.value = action.value === 'accept' ? t('onlineBooking.accepted') : t('onlineBooking.rejected')
    selected.value = null
    action.value = null
    await load()
  } catch (error) {
    formError.value = errorStatus(error) === 409 ? t('onlineBooking.conflict') : errorMessage(error, t('onlineBooking.actionError'))
  } finally {
    saving.value = false
  }
}

function changePage(delta: number) {
  page.value += delta
  selected.value = null
  action.value = null
  void load()
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(locale.value, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: currentClinic.value?.timezone || 'UTC'
  }).format(new Date(value))
}
onMounted(load)
</script>

<template>
  <div class="container mx-auto max-w-6xl space-y-6 p-4">
    <header class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="text-h1">
          {{ t('onlineBooking.title') }}
        </h1>
        <p class="mt-1 text-sm text-muted">
          {{ t('onlineBooking.subtitle') }}
        </p>
      </div>
      <UButton
        icon="i-lucide-refresh-cw"
        variant="outline"
        :loading="loading"
        @click="load"
      >
        {{ t('onlineBooking.refresh') }}
      </UButton>
    </header>
    <p
      v-if="success"
      role="status"
      class="text-sm text-success"
    >
      {{ success }}
    </p>
    <div
      v-if="loadError"
      role="alert"
      class="rounded-lg border border-error p-4 text-error"
    >
      {{ loadError }}
    </div>
    <div
      v-else-if="loading"
      aria-live="polite"
      class="space-y-3"
    >
      <USkeleton
        v-for="i in 3"
        :key="i"
        class="h-24 w-full"
      />
    </div>
    <div
      v-else-if="!items.length"
      class="rounded-lg border border-default p-8 text-center"
    >
      <h2 class="font-semibold">
        {{ t('onlineBooking.emptyTitle') }}
      </h2>
      <p class="mt-1 text-sm text-muted">
        {{ t('onlineBooking.emptyBody') }}
      </p>
    </div>
    <section
      v-else
      :aria-label="t('onlineBooking.title')"
      class="divide-y divide-default rounded-lg border border-default"
    >
      <article
        v-for="row in items"
        :key="row.id"
        class="space-y-4 p-4"
      >
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div class="min-w-0 space-y-1">
            <div class="flex flex-wrap items-center gap-2">
              <h2 class="break-words font-semibold">
                {{ row.contact_name }}
              </h2>
              <UBadge
                :color="row.status === 'confirmed' ? 'success' : 'warning'"
                variant="subtle"
              >
                {{ t(`onlineBooking.status.${row.status}`) }}
              </UBadge>
            </div>
            <p class="text-sm">
              {{ formatDate(row.start_time) }} ({{ currentClinic?.timezone || 'UTC' }}) · {{ t(`onlineBooking.reason.${row.reason}`) }}
            </p>
            <p class="break-all text-sm text-muted">
              {{ row.contact_email }}<span v-if="row.contact_phone"> · {{ row.contact_phone }}</span>
            </p>
          </div>
          <div
            v-if="canWrite"
            class="flex gap-2"
          >
            <UButton
              size="sm"
              color="primary"
              variant="solid"
              :disabled="row.status !== 'confirmed' || saving || !canAccept"
              :title="!canAccept ? t('onlineBooking.noPermission') : undefined"
              @click="open(row, 'accept')"
            >
              {{ t('onlineBooking.accept') }}
            </UButton>
            <UButton
              size="sm"
              color="neutral"
              variant="outline"
              :disabled="saving"
              @click="open(row, 'reject')"
            >
              {{ t('onlineBooking.reject') }}
            </UButton>
          </div>
        </div>
        <div
          v-if="selected?.id === row.id"
          class="space-y-4 rounded-md bg-elevated p-4"
        >
          <h3 class="font-semibold">
            {{ action === 'accept' ? t('onlineBooking.acceptTitle') : t('onlineBooking.rejectTitle') }}
          </h3>
          <template v-if="action === 'accept'">
            <div class="grid gap-3 sm:grid-cols-3">
              <UFormField
                :label="t('onlineBooking.professional')"
                required
              >
                <USelect
                  v-model="professionalId"
                  :items="professionals.map(p => ({ label: `${p.first_name} ${p.last_name}`, value: p.id }))"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="t('onlineBooking.cabinet')">
                <USelect
                  v-model="cabinetId"
                  :items="[{ label: t('onlineBooking.noCabinet'), value: '__none__' }, ...cabinets.map(c => ({ label: c.name, value: c.id }))]"
                  class="w-full"
                />
              </UFormField>
              <UFormField
                :label="t('onlineBooking.duration')"
                required
              >
                <UInput
                  v-model.number="duration"
                  type="number"
                  :min="5"
                  :max="480"
                  class="w-full"
                />
              </UFormField>
            </div>
            <fieldset class="space-y-2">
              <legend class="text-sm font-medium">
                {{ t('onlineBooking.patientChoice') }}
              </legend>
              <div class="flex flex-wrap gap-4 text-sm">
                <label class="flex items-center gap-2"><input
                  v-model="patientMode"
                  type="radio"
                  name="booking-patient-mode"
                  value="existing"
                > {{ t('onlineBooking.existing') }}</label>
                <label class="flex items-center gap-2"><input
                  v-model="patientMode"
                  type="radio"
                  name="booking-patient-mode"
                  value="new"
                > {{ t('onlineBooking.newPatient') }}</label>
              </div>
            </fieldset>
            <div
              v-if="patientMode === 'existing'"
              class="space-y-2"
            >
              <p
                v-if="patient"
                class="text-sm"
              >
                {{ t('onlineBooking.selected') }}: <strong>{{ patient.first_name }} {{ patient.last_name }}</strong> <span
                  v-if="patient.date_of_birth || patient.phone"
                  class="text-muted"
                >{{ [patient.date_of_birth, patient.phone].filter(Boolean).join(' · ') }}</span> <UButton
                  size="xs"
                  variant="link"
                  @click="patient = null"
                >
                  {{ t('onlineBooking.change') }}
                </UButton>
              </p>
              <form
                v-else
                class="space-y-2"
                @submit.prevent="searchPatients"
              >
                <label
                  for="patient-search"
                  class="block text-sm font-medium"
                >{{ t('onlineBooking.searchPatient') }}</label>
                <div class="flex flex-wrap gap-2">
                  <UInput
                    id="patient-search"
                    v-model="patientQuery"
                    :placeholder="t('onlineBooking.searchHint')"
                  /><UButton
                    type="submit"
                    variant="outline"
                    :loading="patientLoading"
                    :disabled="patientQuery.trim().length < 2"
                  >
                    {{ t('onlineBooking.search') }}
                  </UButton>
                </div>
                <p
                  v-if="patientError"
                  role="alert"
                  class="text-sm text-error"
                >
                  {{ patientError }}
                </p>
                <p
                  v-if="searched && !patientResults.length"
                  class="text-sm text-muted"
                >
                  {{ t('onlineBooking.noPatients') }}
                </p>
                <ul
                  v-if="patientResults.length"
                  class="space-y-1"
                >
                  <li
                    v-for="p in patientResults"
                    :key="p.id"
                  >
                    <UButton
                      variant="ghost"
                      color="neutral"
                      @click="patient = p"
                    >
                      {{ p.first_name }} {{ p.last_name }}<span
                        v-if="p.date_of_birth || p.phone"
                        class="ml-2 text-muted"
                      >{{ [p.date_of_birth, p.phone].filter(Boolean).join(' · ') }}</span>
                    </UButton>
                  </li>
                </ul>
              </form>
            </div>
            <div
              v-else
              class="grid gap-3 sm:grid-cols-2"
            >
              <UFormField
                :label="t('onlineBooking.firstName')"
                required
              >
                <UInput
                  v-model="firstName"
                  class="w-full"
                  maxlength="100"
                />
              </UFormField>
              <UFormField
                :label="t('onlineBooking.lastName')"
                required
              >
                <UInput
                  v-model="lastName"
                  class="w-full"
                  maxlength="100"
                />
              </UFormField>
              <UFormField :label="t('onlineBooking.email')">
                <UInput
                  v-model="email"
                  type="email"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="t('onlineBooking.phone')">
                <UInput
                  v-model="phone"
                  type="tel"
                  class="w-full"
                  maxlength="20"
                />
              </UFormField>
            </div>
          </template>
          <UFormField
            v-else
            :label="t('onlineBooking.rejectionMessage')"
            required
          >
            <UTextarea
              v-model="message"
              class="w-full"
              :maxlength="500"
              :rows="3"
            />
          </UFormField>
          <p
            v-if="formError"
            role="alert"
            class="text-sm text-error"
          >
            {{ formError }}
          </p>
          <div class="flex flex-wrap gap-2">
            <UButton
              color="primary"
              variant="solid"
              :loading="saving"
              @click="submit"
            >
              {{ action === 'accept' ? t('onlineBooking.confirmAccept') : t('onlineBooking.confirmReject') }}
            </UButton><UButton
              color="neutral"
              variant="outline"
              :disabled="saving"
              @click="close"
            >
              {{ t('onlineBooking.cancel') }}
            </UButton>
          </div>
        </div>
      </article>
    </section>
    <nav
      v-if="page > 1 || hasMore"
      :aria-label="t('onlineBooking.pages')"
      class="flex items-center gap-3"
    >
      <UButton
        variant="outline"
        :disabled="page <= 1 || loading"
        @click="changePage(-1)"
      >
        {{ t('onlineBooking.previous') }}
      </UButton>
      <span class="text-sm">{{ t('onlineBooking.page') }} {{ page }}</span>
      <UButton
        variant="outline"
        :disabled="!hasMore || loading"
        @click="changePage(1)"
      >
        {{ t('onlineBooking.next') }}
      </UButton>
    </nav>
  </div>
</template>
