import { registerSlot } from '~~/app/composables/useModuleSlots'
import { PERMISSIONS } from '~~/app/config/permissions'

/**
 * Slot registrations wiring medical_reference's searchable comboboxes and
 * per-patient warning flags into patients_clinical's extension points.
 *
 * Dependency direction: patients_clinical exposes the slots and renders a
 * plain-input fallback; it never imports this module's components. When
 * medical_reference isn't installed these registrations simply don't
 * exist and the host UI falls back cleanly.
 */
export default defineNuxtPlugin(() => {
  // Searchable name fields on the medical history form. The adapter is
  // defined once and shared by all four registrations.
  const nameFieldComponent = defineAsyncComponent(
    () => import('../components/MedicalReferenceNameField.vue')
  )

  const historyNameSlots = [
    'patients_clinical.medical_history.allergy_name',
    'patients_clinical.medical_history.medication_name',
    'patients_clinical.medical_history.disease_name',
    'patients_clinical.medical_history.surgery_name'
  ] as const

  for (const slot of historyNameSlots) {
    registerSlot(slot, {
      id: `medical_reference.${slot}`,
      component: nameFieldComponent,
      order: 10,
      permission: PERMISSIONS.medicalReference.read
    })
  }

  // Active interaction/contraindication warnings in the patient sticky
  // header — same slot patients_clinical already registers its own alert
  // chips into.
  registerSlot('patient.header.alerts', {
    id: 'medical_reference.patient.header.alerts.flags',
    component: defineAsyncComponent(
      () => import('../components/PatientReferenceFlagsChips.vue')
    ),
    order: 20,
    permission: PERMISSIONS.medicalReference.read
  })
})
