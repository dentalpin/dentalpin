<script setup lang="ts">
import type { PatientExtended } from '~~/app/types'
import CopyableField from './CopyableField.vue'

interface Props {
  patient: PatientExtended
  isMinor: boolean
  canEdit: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  editContact: []
  editEmergency: []
  editGuardian: []
}>()

const { t, te } = useI18n()

const phoneHref = computed(() => (props.patient.phone ? `tel:${props.patient.phone}` : undefined))
const emailHref = computed(() => (props.patient.email ? `mailto:${props.patient.email}` : undefined))

const formattedAddress = computed(() => {
  const a = props.patient.address
  if (!a) return null
  const lines: string[] = []
  if (a.street) lines.push(a.street)
  const cityLine = [a.postal_code, a.city].filter(Boolean).join(' ')
  if (cityLine) lines.push(cityLine)
  if (a.province) lines.push(a.province)
  if (a.country) lines.push(a.country)
  return lines.length ? lines : null
})

const emergencyRelationshipLabel = computed(() => {
  const rel = props.patient.emergency_contact?.relationship
  if (!rel) return null
  const key = `patients.emergencyContact.relationships.${rel}`
  return te(key) ? t(key) : rel
})

const guardianRelationshipLabel = computed(() => {
  const rel = props.patient.legal_guardian?.relationship
  if (!rel) return null
  const key = `patients.legalGuardian.relationships.${rel}`
  return te(key) ? t(key) : rel
})
</script>

<template>
  <UCard
    role="region"
    aria-labelledby="contact-info-title"
  >
    <template #header>
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2 min-w-0">
          <UIcon
            name="i-lucide-phone"
            class="w-5 h-5 text-default shrink-0"
            aria-hidden="true"
          />
          <h2
            id="contact-info-title"
            class="text-h2 text-default truncate"
          >
            {{ t('patients.contactInfo.title') }}
          </h2>
        </div>
        <UButton
          v-if="canEdit"
          variant="soft"
          color="neutral"
          icon="i-lucide-pencil"
          size="sm"
          :aria-label="t('patients.editDemographics')"
          @click="emit('editContact')"
        >
          <span class="hidden lg:inline">{{ t('common.edit') }}</span>
        </UButton>
      </div>
    </template>

    <dl class="divide-y divide-default">
      <CopyableField
        icon="i-lucide-phone"
        :label="t('patients.phone')"
        :value="patient.phone"
        :href="phoneHref"
        :copy-aria-label="t('patients.contactInfo.copyPhone')"
      />
      <CopyableField
        icon="i-lucide-mail"
        :label="t('patients.email')"
        :value="patient.email"
        :href="emailHref"
        :copy-aria-label="t('patients.contactInfo.copyEmail')"
      />

      <div
        v-if="formattedAddress"
        class="flex items-start gap-3 py-2"
      >
        <UIcon
          name="i-lucide-map-pin"
          class="w-4 h-4 text-subtle shrink-0 mt-1"
          aria-hidden="true"
        />
        <div class="flex-1 min-w-0 flex flex-col sm:flex-row sm:gap-3">
          <dt class="text-caption text-subtle sm:w-32 sm:shrink-0">
            {{ t('patients.contactInfo.address') }}
          </dt>
          <dd class="text-body text-default break-words">
            <span
              v-for="(line, idx) in formattedAddress"
              :key="idx"
              class="block"
            >{{ line }}</span>
          </dd>
        </div>
      </div>
    </dl>

    <!-- Emergency contact sub-block -->
    <section
      class="mt-4 pt-4 border-t border-default"
      aria-labelledby="emergency-contact-title"
    >
      <div class="flex items-center justify-between gap-3 mb-2">
        <h3
          id="emergency-contact-title"
          class="text-caption uppercase tracking-wide text-subtle flex items-center gap-1.5"
        >
          <UIcon
            name="i-lucide-phone-call"
            class="w-3.5 h-3.5"
            aria-hidden="true"
          />
          {{ t('patients.emergencyContact.title') }}
        </h3>
        <UButton
          v-if="canEdit && patient.emergency_contact"
          variant="ghost"
          color="neutral"
          icon="i-lucide-pencil"
          size="sm"
          :aria-label="t('patients.editEmergencyContact')"
          @click="emit('editEmergency')"
        />
      </div>

      <div v-if="patient.emergency_contact">
        <p class="text-body text-default break-words">
          {{ patient.emergency_contact.name }}
          <span
            v-if="emergencyRelationshipLabel"
            class="text-subtle"
          >· {{ emergencyRelationshipLabel }}</span>
        </p>
        <a
          :href="`tel:${patient.emergency_contact.phone}`"
          class="text-primary-accent hover:underline break-words"
        >
          {{ patient.emergency_contact.phone }}
        </a>
        <p
          v-if="patient.emergency_contact.email"
          class="text-caption text-subtle break-words"
        >
          {{ patient.emergency_contact.email }}
        </p>
      </div>
      <div
        v-else
        class="alert-surface-warning rounded-token-md px-3 py-2 flex flex-wrap items-center gap-2"
        role="status"
      >
        <UIcon
          name="i-lucide-alert-circle"
          class="w-4 h-4"
          :style="{ color: 'var(--color-warning-accent)' }"
          aria-hidden="true"
        />
        <span class="text-body">{{ t('patients.emergencyContact.noContact') }}</span>
        <UButton
          v-if="canEdit"
          variant="link"
          color="warning"
          size="sm"
          class="ml-auto"
          @click="emit('editEmergency')"
        >
          {{ t('patients.contactInfo.addEmergency') }} →
        </UButton>
      </div>
    </section>

    <!-- Legal guardian sub-block (only if minor) -->
    <section
      v-if="isMinor"
      class="mt-4 pt-4 border-t border-default"
      aria-labelledby="legal-guardian-title"
    >
      <div class="flex items-center justify-between gap-3 mb-2">
        <h3
          id="legal-guardian-title"
          class="text-caption uppercase tracking-wide text-subtle flex items-center gap-1.5"
        >
          <UIcon
            name="i-lucide-shield-check"
            class="w-3.5 h-3.5"
            aria-hidden="true"
          />
          {{ t('patients.legalGuardian.title') }}
        </h3>
        <UButton
          v-if="canEdit && patient.legal_guardian"
          variant="ghost"
          color="neutral"
          icon="i-lucide-pencil"
          size="sm"
          :aria-label="t('patients.editLegalGuardian')"
          @click="emit('editGuardian')"
        />
      </div>

      <div v-if="patient.legal_guardian">
        <p class="text-body text-default break-words">
          {{ patient.legal_guardian.name }}
          <span
            v-if="guardianRelationshipLabel"
            class="text-subtle"
          >· {{ guardianRelationshipLabel }}</span>
        </p>
        <p
          v-if="patient.legal_guardian.dni"
          class="text-caption text-subtle break-words"
        >
          {{ patient.legal_guardian.dni }}
        </p>
        <a
          :href="`tel:${patient.legal_guardian.phone}`"
          class="text-primary-accent hover:underline break-words"
        >
          {{ patient.legal_guardian.phone }}
        </a>
      </div>
      <div
        v-else
        class="alert-surface-warning rounded-token-md px-3 py-2 flex flex-wrap items-center gap-2"
        role="status"
      >
        <UIcon
          name="i-lucide-alert-triangle"
          class="w-4 h-4"
          :style="{ color: 'var(--color-warning-accent)' }"
          aria-hidden="true"
        />
        <span class="text-body">{{ t('patients.contactInfo.guardianRequired') }}</span>
        <UButton
          v-if="canEdit"
          variant="link"
          color="warning"
          size="sm"
          class="ml-auto"
          @click="emit('editGuardian')"
        >
          {{ t('patients.contactInfo.addGuardian') }} →
        </UButton>
      </div>
    </section>
  </UCard>
</template>
