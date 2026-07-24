<script setup lang="ts">
import type {
  PatientExtended,
  PatientExtendedUpdate,
  EmergencyContact,
  LegalGuardian,
  MedicalHistory,
  PatientAddress,
  PatientBillingAddress
} from '~~/app/types'

type SectionType = 'demographics' | 'emergency' | 'guardian' | 'billing' | 'medical'

interface Props {
  open: boolean
  section: SectionType
  patient: PatientExtended
  medicalHistory?: MedicalHistory
  isSavingMedical?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'save': [section: SectionType, data: Record<string, unknown>]
  'saveMedical': []
}>()

const { t } = useI18n()
const api = useApi()
const toast = useToast()

const isSubmitting = ref(false)

// Section titles
const sectionTitles: Record<SectionType, string> = {
  demographics: 'patients.editDemographics',
  emergency: 'patients.editEmergencyContact',
  guardian: 'patients.editLegalGuardian',
  billing: 'patients.editBilling',
  medical: 'patients.editMedicalHistory'
}

const modalTitle = computed(() => t(sectionTitles[props.section]))

// Form data for demographics
const demographicsForm = reactive({
  first_name: '',
  last_name: '',
  phone: '',
  email: '',
  date_of_birth: '',
  notes: '',
  do_not_contact: false as boolean,
  gender: undefined as string | undefined,
  national_id: '',
  national_id_type: undefined as string | undefined,
  profession: '',
  workplace: '',
  preferred_language: 'es',
  address: {
    street: '',
    city: '',
    postal_code: '',
    province: '',
    country: 'ES'
  } as PatientAddress
})

// Form data for emergency contact
const emergencyForm = ref<EmergencyContact | null>(null)

// Form data for legal guardian
const guardianForm = ref<LegalGuardian | null>(null)

// Form data for billing
const billingForm = reactive({
  billing_name: '',
  billing_tax_id: '',
  billing_email: '',
  billing_address: {
    street: '',
    city: '',
    postal_code: '',
    province: '',
    country: 'ES'
  } as PatientBillingAddress
})

// Gender options
const genderOptions = computed(() => [
  { label: t('patients.gender.male'), value: 'male' },
  { label: t('patients.gender.female'), value: 'female' },
  { label: t('patients.gender.other'), value: 'other' },
  { label: t('patients.gender.preferNotSay'), value: 'prefer_not_say' }
])

// National ID type options
const nationalIdTypeOptions = computed(() => [
  { label: 'DNI', value: 'dni' },
  { label: 'NIE', value: 'nie' },
  { label: t('patients.passport'), value: 'passport' }
])

// Initialize form data when modal opens
watch(() => props.open, (isOpen) => {
  if (isOpen && props.patient) {
    initializeForm()
  }
}, { immediate: true })

function initializeForm() {
  if (props.section === 'demographics') {
    demographicsForm.first_name = props.patient.first_name
    demographicsForm.last_name = props.patient.last_name
    demographicsForm.phone = props.patient.phone || ''
    demographicsForm.email = props.patient.email || ''
    demographicsForm.date_of_birth = props.patient.date_of_birth || ''
    demographicsForm.notes = props.patient.notes || ''
    demographicsForm.do_not_contact = props.patient.do_not_contact ?? false
    demographicsForm.gender = props.patient.gender
    demographicsForm.national_id = props.patient.national_id || ''
    demographicsForm.national_id_type = props.patient.national_id_type
    demographicsForm.profession = props.patient.profession || ''
    demographicsForm.workplace = props.patient.workplace || ''
    demographicsForm.preferred_language = props.patient.preferred_language || 'es'
    demographicsForm.address = props.patient.address || { street: '', city: '', postal_code: '', province: '', country: 'ES' }
  } else if (props.section === 'emergency') {
    emergencyForm.value = props.patient.emergency_contact ? { ...props.patient.emergency_contact } : null
  } else if (props.section === 'guardian') {
    guardianForm.value = props.patient.legal_guardian ? { ...props.patient.legal_guardian } : null
  } else if (props.section === 'billing') {
    billingForm.billing_name = props.patient.billing_name || ''
    billingForm.billing_tax_id = props.patient.billing_tax_id || ''
    billingForm.billing_email = props.patient.billing_email || ''
    billingForm.billing_address = props.patient.billing_address || { street: '', city: '', postal_code: '', province: '', country: 'ES' }
  }
}

function closeModal() {
  emit('update:open', false)
}

async function handleSave() {
  if (props.section === 'medical') {
    emit('saveMedical')
    return
  }

  isSubmitting.value = true

  try {
    let updateData: Partial<PatientExtendedUpdate> | EmergencyContact | LegalGuardian | null = {}
    let endpoint = `/api/v1/patients/${props.patient.id}/extended`
    let method: 'put' | 'del' = 'put'

    if (props.section === 'demographics') {
      const address = demographicsForm.address?.street ? demographicsForm.address : null
      updateData = {
        first_name: demographicsForm.first_name,
        last_name: demographicsForm.last_name,
        phone: demographicsForm.phone || null,
        email: demographicsForm.email || null,
        date_of_birth: demographicsForm.date_of_birth || null,
        notes: demographicsForm.notes || null,
        do_not_contact: demographicsForm.do_not_contact,
        gender: demographicsForm.gender || null,
        national_id: demographicsForm.national_id || null,
        national_id_type: demographicsForm.national_id_type || null,
        profession: demographicsForm.profession || null,
        workplace: demographicsForm.workplace || null,
        preferred_language: demographicsForm.preferred_language || 'es',
        address
      }
    } else if (props.section === 'emergency') {
      endpoint = `/api/v1/patients_clinical/patients/${props.patient.id}/emergency-contact`
      if (emergencyForm.value) {
        updateData = emergencyForm.value
      } else {
        method = 'del'
        updateData = null
      }
    } else if (props.section === 'guardian') {
      endpoint = `/api/v1/patients_clinical/patients/${props.patient.id}/legal-guardian`
      if (guardianForm.value) {
        updateData = guardianForm.value
      } else {
        method = 'del'
        updateData = null
      }
    } else if (props.section === 'billing') {
      const billingAddress = billingForm.billing_address?.street ? billingForm.billing_address : null
      updateData = {
        billing_name: billingForm.billing_name || null,
        billing_tax_id: billingForm.billing_tax_id || null,
        billing_email: billingForm.billing_email || null,
        billing_address: billingAddress
      }
    }

    if (method === 'del') {
      try {
        await api.del(endpoint)
      } catch (e: unknown) {
        // Emergency/guardian may not exist yet — delete 404 is harmless.
        const err = e as { statusCode?: number }
        if (err.statusCode !== 404) throw e
      }
    } else {
      await api.put(endpoint, updateData as Record<string, unknown>)
    }

    toast.add({
      title: t('common.success'),
      description: t('patients.updated'),
      color: 'success'
    })

    closeModal()
    // Emit after close to avoid reactive loop during refresh
    await nextTick()
    emit('save', props.section, (updateData ?? {}) as Record<string, unknown>)
  } catch (error: unknown) {
    const fetchError = error as { statusCode?: number, data?: { message?: string } }
    toast.add({
      title: t('common.error'),
      description: fetchError.data?.message || t('common.serverError'),
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}

const canSave = computed(() => {
  if (props.section === 'demographics') {
    return demographicsForm.first_name && demographicsForm.last_name
  }
  return true
})
</script>

<template>
  <UModal
    :open="open"
    @update:open="emit('update:open', $event)"
  >
    <template #content>
      <UCard :ui="{ root: 'w-full max-w-2xl', body: 'overflow-visible' }">
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="text-h1 text-default">
              {{ modalTitle }}
            </h2>
            <UButton
              variant="ghost"
              color="neutral"
              icon="i-lucide-x"
              size="sm"
              :aria-label="t('common.close', 'Cerrar')"
              @click="closeModal"
            />
          </div>
        </template>

        <!-- Demographics Form -->
        <div
          v-if="section === 'demographics'"
          class="space-y-4 max-h-[65vh] overflow-y-auto pr-1"
        >
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <UFormField
              :label="t('patients.firstName')"
              required
            >
              <UInput
                v-model="demographicsForm.first_name"
                required
              />
            </UFormField>
            <UFormField
              :label="t('patients.lastName')"
              required
            >
              <UInput
                v-model="demographicsForm.last_name"
                required
              />
            </UFormField>
            <UFormField :label="t('patients.phone')">
              <UInput
                v-model="demographicsForm.phone"
                type="tel"
              />
            </UFormField>
            <UFormField :label="t('patients.email')">
              <UInput
                v-model="demographicsForm.email"
                type="email"
              />
            </UFormField>
            <UFormField :label="t('patients.dateOfBirth')">
              <UInput
                v-model="demographicsForm.date_of_birth"
                type="date"
              />
            </UFormField>
            <UFormField :label="t('patients.gender.label')">
              <USelect
                v-model="demographicsForm.gender"
                :items="genderOptions"
                value-key="value"
                label-key="label"
                :placeholder="t('patients.gender.select')"
              />
            </UFormField>
            <UFormField :label="t('patients.nationalIdType')">
              <USelect
                v-model="demographicsForm.national_id_type"
                :items="nationalIdTypeOptions"
                value-key="value"
                label-key="label"
              />
            </UFormField>
            <UFormField :label="t('patients.nationalId')">
              <UInput v-model="demographicsForm.national_id" />
            </UFormField>
            <UFormField :label="t('patients.profession')">
              <UInput v-model="demographicsForm.profession" />
            </UFormField>
            <UFormField :label="t('patients.workplace')">
              <UInput v-model="demographicsForm.workplace" />
            </UFormField>
          </div>
          <UFormField :label="t('patients.notes')">
            <UTextarea
              v-model="demographicsForm.notes"
              :rows="3"
            />
          </UFormField>
          <UFormField
            :label="t('patients.doNotContact.label')"
            :hint="t('patients.doNotContact.hint')"
          >
            <USwitch v-model="demographicsForm.do_not_contact" />
          </UFormField>
        </div>

        <!-- Emergency Contact Form -->
        <div
          v-else-if="section === 'emergency'"
          class="space-y-4 max-h-[65vh] overflow-y-auto pr-1"
        >
          <EmergencyContactForm v-model="emergencyForm" />
        </div>

        <!-- Legal Guardian Form -->
        <div
          v-else-if="section === 'guardian'"
          class="space-y-4 max-h-[65vh] overflow-y-auto pr-1"
        >
          <LegalGuardianForm v-model="guardianForm" />
        </div>

        <!-- Billing Form -->
        <div
          v-else-if="section === 'billing'"
          class="space-y-4 max-h-[65vh] overflow-y-auto pr-1"
        >
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <UFormField :label="t('patients.billingName')">
              <UInput
                v-model="billingForm.billing_name"
                :placeholder="t('patients.billingNamePlaceholder')"
              />
            </UFormField>
            <UFormField :label="t('patients.billingTaxId')">
              <UInput
                v-model="billingForm.billing_tax_id"
                placeholder="NIF/CIF"
              />
            </UFormField>
            <UFormField :label="t('patients.billingEmail')">
              <UInput
                v-model="billingForm.billing_email"
                type="email"
              />
            </UFormField>
          </div>
          <div class="mt-4">
            <h4 class="text-sm font-medium text-muted mb-3">
              {{ t('patients.billingAddress') }}
            </h4>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="md:col-span-2">
                <UFormField :label="t('invoice.street')">
                  <UInput v-model="billingForm.billing_address.street" />
                </UFormField>
              </div>
              <UFormField :label="t('invoice.city')">
                <UInput v-model="billingForm.billing_address.city" />
              </UFormField>
              <UFormField :label="t('invoice.postalCode')">
                <UInput v-model="billingForm.billing_address.postal_code" />
              </UFormField>
              <UFormField :label="t('invoice.province')">
                <UInput v-model="billingForm.billing_address.province" />
              </UFormField>
              <UFormField :label="t('invoice.country')">
                <UInput v-model="billingForm.billing_address.country" />
              </UFormField>
            </div>
          </div>
        </div>

        <!-- Medical History Form -->
        <div
          v-else-if="section === 'medical'"
          class="max-h-[65vh] overflow-y-auto pr-1"
        >
          <MedicalHistoryForm
            v-if="medicalHistory"
            :model-value="medicalHistory"
            :patient-id="props.patient?.id"
            hide-actions
          />
        </div>

        <template #footer>
          <div class="flex justify-end gap-3">
            <UButton
              variant="outline"
              color="neutral"
              @click="closeModal"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              :loading="isSubmitting || isSavingMedical"
              :disabled="!canSave"
              @click="handleSave"
            >
              {{ t('common.save') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
