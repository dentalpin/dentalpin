<script setup lang="ts">
import type { PaginatedResponse } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'
import { PERMISSIONS } from '~~/app/config/permissions'
import { useLeads, type Lead, type LeadConvertPayload } from '../../composables/useLeads'
import { phonesMatch, splitFullName } from '../../utils/leadAutofill'
import { hasAvailability } from '../../utils/leadAvailability'
import {
  hasErrors,
  validatePatientForm,
  type PatientFormErrors,
  type ValidationKey
} from '../../utils/leadValidation'

/**
 * The convert drawer: the lead on the left of the eye, the patient form
 * in front of it. Autofill is the point — the receptionist completes the
 * record while seeing what the person actually asked for.
 *
 * Nothing here blocks conversion when a patient with the same phone
 * exists: families share a phone, so the drawer warns and lets a human
 * decide.
 */
interface Props {
  open: boolean
  lead?: Lead | null
}

const props = withDefaults(defineProps<Props>(), { lead: null })

const emit = defineEmits<{
  'update:open': [value: boolean]
  'edit': [lead: Lead]
  'converted': [lead: Lead]
}>()

const { t, locale } = useI18n()
const toast = useToast()
const api = useApi()
const { can } = usePermissions()
const leadsApi = useLeads()

interface PatientMatch {
  id: string
  first_name: string
  last_name: string
  phone: string | null
}

const saving = ref(false)
const createdPatientId = ref<string | null>(null)
const duplicate = ref<PatientMatch | null>(null)

const form = reactive({
  first_name: '',
  last_name: '',
  phone: '',
  email: '',
  date_of_birth: '',
  national_id: '',
  notes: ''
})

const isConverted = computed(() => props.lead?.status === 'converted')
const convertedPatientId = computed(() => createdPatientId.value ?? props.lead?.patient_id ?? null)
// Mirrors the backend: PATCH needs leads.write, /convert needs leads.write + patients.write.
// Gating on patients.write alone let a dentist (patients.*, leads.read) click into a 403.
const canEdit = computed(() => can(PERMISSIONS.leads.write))
const canConvert = computed(() => canEdit.value && can(PERMISSIONS.patients.write))

// --- Validation -----------------------------------------------------------
// The server would answer 422 and create nothing; catching it here keeps a
// typo'd email from looking like a failed save. Errors surface on blur or
// after a save attempt, and the convert button stays enabled so clicking it
// explains which field is wrong instead of doing nothing.
const submitted = ref(false)
const touched = ref<Record<string, boolean>>({})

const errors = computed<PatientFormErrors>(() =>
  validatePatientForm({
    first_name: form.first_name,
    last_name: form.last_name,
    phone: form.phone,
    email: form.email,
    date_of_birth: form.date_of_birth
  })
)

function showFor(field: keyof PatientFormErrors): boolean {
  return submitted.value || Boolean(touched.value[field])
}

function fieldError(field: keyof PatientFormErrors): string | undefined {
  const key: ValidationKey | undefined = errors.value[field]
  return key && showFor(field) ? t(`leads.validation.${key}`) : undefined
}

function touch(field: keyof PatientFormErrors) {
  touched.value = { ...touched.value, [field]: true }
}

function close() {
  emit('update:open', false)
}

function resetFrom(lead: Lead | null) {
  createdPatientId.value = null
  duplicate.value = null
  if (!lead) {
    Object.assign(form, {
      first_name: '',
      last_name: '',
      phone: '',
      email: '',
      date_of_birth: '',
      national_id: '',
      notes: ''
    })
    return
  }
  const names = splitFullName(lead.full_name)
  Object.assign(form, {
    first_name: names.first_name,
    last_name: names.last_name,
    phone: lead.phone ?? '',
    email: lead.email ?? '',
    date_of_birth: '',
    national_id: '',
    // Notes start empty on purpose: the motive and the call availability are
    // logistics for this call, not patient data. They stay on the lead and in
    // the panel above; the chart gets what the clinician needs, written by a
    // human.
    notes: ''
  })
}

watch(
  () => [props.open, props.lead?.id, props.lead?.status],
  () => {
    if (!props.open) return
    submitted.value = false
    touched.value = {}
    resetFrom(props.lead ?? null)
    if (props.lead && props.lead.status !== 'converted') void checkDuplicate(props.lead.phone)
  },
  { immediate: true }
)

/** Non-blocking duplicate warning (the backend never blocks either). */
async function checkDuplicate(phone: string | null | undefined) {
  duplicate.value = null
  if (!phone || !can(PERMISSIONS.patients.read)) return
  try {
    const response = await api.get<PaginatedResponse<PatientMatch>>(
      `/api/v1/patients?search=${encodeURIComponent(phone)}&page_size=5`
    )
    duplicate.value = response.data.find(patient => phonesMatch(patient.phone, phone)) ?? null
  } catch {
    // No permission or no patients module: the warning is a nicety.
    duplicate.value = null
  }
}

function receivedLabel(iso: string): string {
  return new Date(iso).toLocaleDateString(locale.value)
}

async function convert() {
  if (!props.lead) return
  // Never send a payload the patients module would reject: mark the bad
  // fields and say why, in the user's language.
  submitted.value = true
  if (hasErrors(errors.value)) {
    toast.add({ title: t('leads.validation.fixErrors'), color: 'warning' })
    return
  }

  saving.value = true
  try {
    const payload: LeadConvertPayload = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      phone: form.phone.trim() || null,
      email: form.email.trim() || null,
      date_of_birth: form.date_of_birth || null,
      national_id: form.national_id.trim() || null,
      notes: form.notes.trim() || null
    }
    const response = await leadsApi.convert(props.lead.id, payload)
    createdPatientId.value = response.data.patient.id
    toast.add({ title: t('leads.convert.created'), color: 'success' })
    emit('converted', response.data.lead)
  } catch (e: unknown) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('leads.errors.convert')),
      color: 'error'
    })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <USlideover
    :open="open"
    side="right"
    :title="t('leads.convert.title')"
    :ui="{ content: 'w-[560px] max-w-[95vw] bg-surface' }"
    @update:open="(value: boolean) => emit('update:open', value)"
  >
    <template #content>
      <div class="flex flex-col h-full">
        <header class="flex items-center justify-between gap-2 px-4 h-14 border-b border-default">
          <div class="min-w-0">
            <div class="text-h3 text-default truncate">
              {{ t('leads.convert.title') }}
            </div>
            <div class="text-caption text-subtle truncate">
              {{ lead?.full_name }}
            </div>
          </div>
          <UButton
            variant="ghost"
            color="neutral"
            size="sm"
            icon="i-lucide-x"
            :aria-label="t('common.close')"
            @click="close"
          />
        </header>

        <div class="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
          <template v-if="lead">
            <!-- 1. What the person asked for. -->
            <UCard>
              <template #header>
                <div class="flex items-center justify-between gap-2">
                  <span class="text-ui font-medium text-default">{{ t('leads.convert.enquiry') }}</span>
                  <UButton
                    v-if="canEdit"
                    variant="ghost"
                    color="neutral"
                    size="xs"
                    icon="i-lucide-pencil"
                    @click="emit('edit', lead)"
                  >
                    {{ t('leads.actions.edit') }}
                  </UButton>
                </div>
              </template>
              <dl class="space-y-2 text-ui">
                <div>
                  <dt class="text-caption text-subtle">
                    {{ t('leads.fields.motive') }}
                  </dt>
                  <dd class="text-default">
                    {{ lead.motive }}
                  </dd>
                </div>
                <div v-if="lead.description">
                  <dt class="text-caption text-subtle">
                    {{ t('leads.fields.description') }}
                  </dt>
                  <dd class="text-default whitespace-pre-line">
                    {{ lead.description }}
                  </dd>
                </div>
                <div v-if="hasAvailability(lead.availability_days, lead.availability_slot)">
                  <dt class="text-caption text-subtle">
                    {{ t('leads.fields.availability') }}
                  </dt>
                  <dd class="text-default">
                    <LeadAvailabilityWeek
                      :days="lead.availability_days"
                      :time-slot="lead.availability_slot"
                      size="md"
                    />
                  </dd>
                </div>
                <div class="flex flex-wrap gap-x-6 gap-y-1">
                  <div>
                    <dt class="text-caption text-subtle">
                      {{ t('leads.fields.phone') }}
                    </dt>
                    <dd
                      class="text-default"
                      dir="ltr"
                    >
                      {{ lead.phone }}
                    </dd>
                  </div>
                  <div v-if="lead.email">
                    <dt class="text-caption text-subtle">
                      {{ t('leads.fields.email') }}
                    </dt>
                    <dd
                      class="text-default"
                      dir="ltr"
                    >
                      {{ lead.email }}
                    </dd>
                  </div>
                  <div>
                    <dt class="text-caption text-subtle">
                      {{ t('leads.receivedAt') }}
                    </dt>
                    <dd class="text-default">
                      {{ receivedLabel(lead.created_at) }}
                    </dd>
                  </div>
                </div>
              </dl>
            </UCard>

            <!-- 5. Already converted: never re-convert (the API answers 409). -->
            <template v-if="isConverted || createdPatientId">
              <UAlert
                color="success"
                variant="soft"
                icon="i-lucide-circle-check"
                :title="t('leads.convert.created')"
                :description="t('leads.convert.alreadyConverted')"
              />
              <UButton
                v-if="convertedPatientId"
                color="primary"
                icon="i-lucide-user"
                :to="`/patients/${convertedPatientId}`"
              >
                {{ t('leads.convert.openPatient') }}
              </UButton>
            </template>

            <template v-else>
              <!-- 2. Duplicate warning: warn, never block. -->
              <UAlert
                v-if="duplicate"
                color="warning"
                variant="soft"
                icon="i-lucide-triangle-alert"
                :title="t('leads.convert.duplicateWarning')"
              >
                <template #description>
                  <NuxtLink
                    :to="`/patients/${duplicate.id}`"
                    class="underline"
                  >
                    {{ t('leads.convert.duplicateOpen') }}: {{ duplicate.first_name }}
                    {{ duplicate.last_name }}
                  </NuxtLink>
                </template>
              </UAlert>

              <!-- 3. The patient form. -->
              <UCard>
                <template #header>
                  <span class="text-ui font-medium text-default">{{ t('leads.convert.patient') }}</span>
                </template>

                <form
                  class="space-y-4"
                  @submit.prevent="convert"
                >
                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <UFormField
                      :label="t('patients.firstName')"
                      :error="fieldError('first_name')"
                      required
                    >
                      <UInput
                        v-model="form.first_name"
                        maxlength="100"
                        @blur="touch('first_name')"
                      />
                    </UFormField>
                    <UFormField
                      :label="t('patients.lastName')"
                      :error="fieldError('last_name')"
                      required
                    >
                      <UInput
                        v-model="form.last_name"
                        maxlength="100"
                        @blur="touch('last_name')"
                      />
                    </UFormField>
                  </div>

                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <UFormField
                      :label="t('patients.phone')"
                      :error="fieldError('phone')"
                    >
                      <!-- 20, not 32: that is the patients.phone column this
                           record is written into. -->
                      <UInput
                        v-model="form.phone"
                        type="tel"
                        dir="ltr"
                        maxlength="20"
                        @blur="touch('phone')"
                      />
                    </UFormField>
                    <UFormField
                      :label="t('patients.email')"
                      :error="fieldError('email')"
                    >
                      <UInput
                        v-model="form.email"
                        type="email"
                        dir="ltr"
                        maxlength="254"
                        @blur="touch('email')"
                      />
                    </UFormField>
                  </div>

                  <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <UFormField :label="t('patients.nationalId')">
                      <UInput
                        v-model="form.national_id"
                        placeholder="12345678A"
                        maxlength="50"
                      />
                    </UFormField>
                    <UFormField
                      :label="t('patients.dateOfBirth')"
                      :error="fieldError('date_of_birth')"
                    >
                      <UInput
                        v-model="form.date_of_birth"
                        type="date"
                        @blur="touch('date_of_birth')"
                      />
                    </UFormField>
                  </div>

                  <UFormField :label="t('patients.notes')">
                    <UTextarea
                      v-model="form.notes"
                      :rows="5"
                    />
                  </UFormField>
                </form>
              </UCard>
            </template>
          </template>
        </div>

        <footer
          v-if="lead && !isConverted && !createdPatientId"
          class="flex items-center justify-end gap-2 px-4 h-16 border-t border-default"
        >
          <UButton
            variant="outline"
            color="neutral"
            @click="close"
          >
            {{ t('leads.actions.cancel') }}
          </UButton>
          <UButton
            color="primary"
            :loading="saving"
            :disabled="!canConvert"
            @click="convert"
          >
            {{ t('leads.convert.createPatient') }}
          </UButton>
        </footer>
      </div>
    </template>
  </USlideover>
</template>
