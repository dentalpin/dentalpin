<script setup lang="ts">
import type { LegalGuardian } from '~~/app/types'

interface Props {
  modelValue: LegalGuardian | null | undefined
  readonly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false
})

const emit = defineEmits<{
  'update:modelValue': [value: LegalGuardian | null]
}>()

const { t } = useI18n()

// Default empty guardian
const emptyGuardian: LegalGuardian = {
  name: '',
  relationship: 'parent',
  dni: undefined,
  phone: '',
  email: undefined,
  address: undefined,
  notes: undefined
}

// Local state
const localGuardian = ref<LegalGuardian>({ ...emptyGuardian })
const hasGuardian = ref(!!props.modelValue)
const isUpdatingFromProps = ref(false)

// Initialize from props
watch(() => props.modelValue, (newVal) => {
  isUpdatingFromProps.value = true
  if (newVal) {
    localGuardian.value = { ...newVal }
    hasGuardian.value = true
  } else {
    localGuardian.value = { ...emptyGuardian }
    hasGuardian.value = false
  }
  nextTick(() => {
    isUpdatingFromProps.value = false
  })
}, { immediate: true })

// Watch local changes and emit (skip if update came from props)
watch([hasGuardian, localGuardian], () => {
  if (isUpdatingFromProps.value) return
  if (hasGuardian.value && localGuardian.value.name && localGuardian.value.phone) {
    emit('update:modelValue', { ...localGuardian.value })
  } else if (!hasGuardian.value) {
    emit('update:modelValue', null)
  }
}, { deep: true })

// Relationship options
const relationshipOptions = computed(() => [
  { label: t('patients.legalGuardian.relationships.parent'), value: 'parent' },
  { label: t('patients.legalGuardian.relationships.grandparent'), value: 'grandparent' },
  { label: t('patients.legalGuardian.relationships.legal_tutor'), value: 'legal_tutor' },
  { label: t('patients.legalGuardian.relationships.other'), value: 'other' }
])

function getRelationshipLabel(value: string): string {
  const option = relationshipOptions.value.find(o => o.value === value)
  return option?.label || value
}

function clearGuardian() {
  localGuardian.value = { ...emptyGuardian }
  hasGuardian.value = false
}
</script>

<template>
  <div class="legal-guardian-form">
    <div
      v-if="!readonly"
      class="flex items-center gap-2 mb-4"
    >
      <UCheckbox
        v-model="hasGuardian"
        :label="t('patients.legalGuardian.hasGuardian')"
      />
    </div>

    <div
      v-if="hasGuardian"
      class="space-y-4"
    >
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <UFormField
          :label="t('patients.legalGuardian.name')"
          required
        >
          <template v-if="readonly">
            <p class="text-default">
              {{ localGuardian.name || '-' }}
            </p>
          </template>
          <template v-else>
            <UInput
              v-model="localGuardian.name"
              :placeholder="t('patients.legalGuardian.namePlaceholder')"
            />
          </template>
        </UFormField>

        <UFormField :label="t('patients.legalGuardian.relationship')">
          <template v-if="readonly">
            <p class="text-default">
              {{ getRelationshipLabel(localGuardian.relationship) }}
            </p>
          </template>
          <template v-else>
            <USelect
              v-model="localGuardian.relationship"
              :items="relationshipOptions"
              value-key="value"
              label-key="label"
              :placeholder="t('patients.legalGuardian.relationshipPlaceholder')"
            />
          </template>
        </UFormField>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <UFormField :label="t('patients.legalGuardian.dni')">
          <template v-if="readonly">
            <p class="text-default">
              {{ localGuardian.dni || '-' }}
            </p>
          </template>
          <template v-else>
            <UInput
              v-model="localGuardian.dni"
              :placeholder="t('patients.legalGuardian.dniPlaceholder')"
            />
          </template>
        </UFormField>

        <UFormField
          :label="t('patients.legalGuardian.phone')"
          required
        >
          <template v-if="readonly">
            <p class="text-default">
              <span dir="ltr">{{ localGuardian.phone || '-' }}</span>
            </p>
          </template>
          <template v-else>
            <UInput
              v-model="localGuardian.phone"
              type="tel"
              :placeholder="t('patients.legalGuardian.phonePlaceholder')"
            />
          </template>
        </UFormField>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <UFormField :label="t('patients.legalGuardian.email')">
          <template v-if="readonly">
            <p class="text-default">
              {{ localGuardian.email || '-' }}
            </p>
          </template>
          <template v-else>
            <UInput
              v-model="localGuardian.email"
              type="email"
              :placeholder="t('patients.legalGuardian.emailPlaceholder')"
            />
          </template>
        </UFormField>

        <UFormField :label="t('patients.legalGuardian.address')">
          <template v-if="readonly">
            <p class="text-default">
              {{ localGuardian.address || '-' }}
            </p>
          </template>
          <template v-else>
            <UInput
              v-model="localGuardian.address"
              :placeholder="t('patients.legalGuardian.addressPlaceholder')"
            />
          </template>
        </UFormField>
      </div>

      <UFormField :label="t('patients.legalGuardian.notes')">
        <template v-if="readonly">
          <p class="text-default whitespace-pre-wrap">
            {{ localGuardian.notes || '-' }}
          </p>
        </template>
        <template v-else>
          <UTextarea
            v-model="localGuardian.notes"
            :placeholder="t('patients.legalGuardian.notesPlaceholder')"
            :rows="2"
          />
        </template>
      </UFormField>

      <UButton
        v-if="!readonly && hasGuardian"
        variant="outline"
        color="error"
        size="sm"
        icon="i-lucide-trash-2"
        @click="clearGuardian"
      >
        {{ t('patients.legalGuardian.remove') }}
      </UButton>
    </div>

    <div
      v-else
      class="text-subtle italic"
    >
      {{ t('patients.legalGuardian.noGuardian') }}
    </div>
  </div>
</template>
