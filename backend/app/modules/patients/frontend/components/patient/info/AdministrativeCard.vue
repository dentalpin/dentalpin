<script setup lang="ts">
import type { PatientExtended } from '~~/app/types'

interface Props {
  patient: PatientExtended
  canEdit: boolean
}

defineProps<Props>()

const emit = defineEmits<{ edit: [] }>()

const { t } = useI18n()
</script>

<template>
  <UCard
    role="region"
    aria-labelledby="administrative-title"
  >
    <template #header>
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2 min-w-0">
          <UIcon
            name="i-lucide-receipt"
            class="w-5 h-5 text-default shrink-0"
            aria-hidden="true"
          />
          <h2
            id="administrative-title"
            class="text-h2 text-default truncate"
          >
            {{ t('patients.administrative.title') }}
          </h2>
        </div>
        <UButton
          v-if="canEdit"
          variant="soft"
          color="neutral"
          icon="i-lucide-pencil"
          size="sm"
          :aria-label="t('patients.editBilling')"
          @click="emit('edit')"
        >
          <span class="hidden lg:inline">{{ t('common.edit') }}</span>
        </UButton>
      </div>
    </template>

    <div class="mb-4">
      <UBadge
        v-if="patient.has_complete_billing_info"
        color="success"
        variant="subtle"
        size="md"
      >
        <UIcon
          name="i-lucide-check"
          class="w-3.5 h-3.5 me-1"
          aria-hidden="true"
        />
        {{ t('patients.billingComplete') }}
      </UBadge>
      <UBadge
        v-else
        color="warning"
        variant="subtle"
        size="md"
      >
        <UIcon
          name="i-lucide-alert-triangle"
          class="w-3.5 h-3.5 me-1"
          aria-hidden="true"
        />
        {{ t('patients.billingIncomplete') }}
      </UBadge>
    </div>

    <dl class="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3">
      <DataField
        :label="t('patients.billingName')"
        :value="patient.billing_name"
      />
      <DataField
        :label="t('patients.billingTaxId')"
        :value="patient.billing_tax_id"
      />
      <DataField
        :label="t('patients.billingEmail')"
        :value="patient.billing_email"
      />
      <DataField :label="t('patients.billingAddress')">
        <template v-if="patient.billing_address">
          <span class="block break-words">{{ patient.billing_address.street || '' }}</span>
          <span
            v-if="patient.billing_address.city || patient.billing_address.postal_code"
            class="block break-words"
          >{{ patient.billing_address.postal_code }} {{ patient.billing_address.city }}</span>
          <span
            v-if="patient.billing_address.province"
            class="block break-words"
          >{{ patient.billing_address.province }}</span>
        </template>
        <template v-else>
          —
        </template>
      </DataField>
    </dl>
  </UCard>
</template>
