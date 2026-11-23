<script setup lang="ts">
import type { EmergencyContact } from '~~/app/types'

interface Props {
  modelValue: EmergencyContact | null | undefined
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false
})

const emit = defineEmits<{
  'update:modelValue': [value: EmergencyContact | null]
}>()

const { t } = useI18n()

// Default empty contact
const emptyContact: EmergencyContact = {
  name: '',
  relationship: undefined,
  phone: '',
  email: undefined,
  is_legal_guardian: false
}

// Local state
const localContact = ref<EmergencyContact>({ ...emptyContact })
const hasContact = ref(!!props.modelValue)
const isUpdatingFromProps = ref(false)

// Initialize from props
watch(() => props.modelValue, (newVal) => {
  isUpdatingFromProps.value = true
  if (newVal) {
    localContact.value = { ...newVal }
    hasContact.value = true
  } else {
    localContact.value = { ...emptyContact }
    hasContact.value = false
  }
  nextTick(() => {
    isUpdatingFromProps.value = false
  })
}, { immediate: true })

// Watch local changes and emit (skip if update came from props)
watch([hasContact, localContact], () => {
  if (isUpdatingFromProps.value) return
  // Incomplete edits go up too: the API refuses them, where holding them
  // back saved the previous value, or deleted, with a success toast (#1064).
  emit('update:modelValue', hasContact.value ? { ...localContact.value } : null)
}, { deep: true })

// Relationship options - computed for reactivity
const relationshipOptions = computed(() => [
  { label: t('patients.emergencyContact.relationships.spouse'), value: 'spouse' },
  { label: t('patients.emergencyContact.relationships.parent'), value: 'parent' },
  { label: t('patients.emergencyContact.relationships.child'), value: 'child' },
  { label: t('patients.emergencyContact.relationships.sibling'), value: 'sibling' },
  { label: t('patients.emergencyContact.relationships.friend'), value: 'friend' },
  { label: t('patients.emergencyContact.relationships.other'), value: 'other' }
])

function clearContact() {
  localContact.value = { ...emptyContact }
  hasContact.value = false
}
</script>

<template>
  <div class="emergency-contact-form">
    <div
      v-if="!readonly"
      class="flex items-center gap-2 mb-4"
    >
      <UCheckbox
        v-model="hasContact"
        :label="t('patients.emergencyContact.hasContact')"
      />
    </div>

    <div
      v-if="hasContact"
      class="space-y-4"
    >
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <UFormField
          :label="t('patients.emergencyContact.name')"
          required
        >
          <UInput
            v-model="localContact.name"
            :placeholder="t('patients.emergencyContact.namePlaceholder')"
            :disabled="readonly"
          />
        </UFormField>

        <UFormField :label="t('patients.emergencyContact.relationship')">
          <USelect
            v-model="localContact.relationship"
            :items="relationshipOptions"
            value-key="value"
            label-key="label"
            :placeholder="t('patients.emergencyContact.relationshipPlaceholder')"
            :disabled="readonly"
          />
        </UFormField>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <UFormField
          :label="t('patients.emergencyContact.phone')"
          required
        >
          <UInput
            v-model="localContact.phone"
            type="tel"
            :placeholder="t('patients.emergencyContact.phonePlaceholder')"
            :disabled="readonly"
          />
        </UFormField>

        <UFormField :label="t('patients.emergencyContact.email')">
          <UInput
            v-model="localContact.email"
            type="email"
            :placeholder="t('patients.emergencyContact.emailPlaceholder')"
            :disabled="readonly"
          />
        </UFormField>
      </div>

      <UCheckbox
        v-model="localContact.is_legal_guardian"
        :label="t('patients.emergencyContact.isLegalGuardian')"
        :disabled="readonly"
      />

      <UButton
        v-if="!readonly && hasContact"
        variant="outline"
        color="error"
        size="sm"
        icon="i-lucide-trash-2"
        @click="clearContact"
      >
        {{ t('patients.emergencyContact.remove') }}
      </UButton>
    </div>

    <div
      v-else
      class="text-subtle italic"
    >
      {{ t('patients.emergencyContact.noContact') }}
    </div>
  </div>
</template>
