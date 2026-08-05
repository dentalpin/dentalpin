<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { useDocuments } from '../../composables/useDocuments'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const docsApi = useDocuments()

// Backend enforces this endpoint's write with `admin.clinic.write` (see
// PHASE14_INSTALL_GUIDE.md — letterhead is clinic-wide settings, not
// module content, mirroring how budget/communications settings are
// scoped). Frontend gating below assumes the shared PERMISSIONS object
// exposes an equivalent key — unconfirmed shape, adjust if it differs
// (e.g. `PERMISSIONS.admin.clinic.write` vs `PERMISSIONS.clinic.write`).
const canEdit = computed(() => can(PERMISSIONS.documents.write))

const practiceName = ref('')
const legalName = ref('')
const addressLine = ref('')
const phone = ref('')
const email = ref('')
const logoUrl = ref('')
const registrationNumber = ref('')
const footerText = ref('')
const saving = ref(false)
const saved = ref(false)

onMounted(async () => {
  const res = await docsApi.getLetterhead().catch(() => null)
  const existing = res?.data
  if (existing) {
    practiceName.value = existing.practice_name || ''
    legalName.value = existing.legal_name || ''
    addressLine.value = existing.address?.line1 || ''
    phone.value = existing.phone || ''
    email.value = existing.email || ''
    logoUrl.value = existing.logo_url || ''
    registrationNumber.value = existing.registration_number || ''
    footerText.value = existing.footer_text || ''
  }
})

async function save() {
  saving.value = true
  saved.value = false
  try {
    await docsApi.saveLetterhead({
      practice_name: practiceName.value,
      legal_name: legalName.value || null,
      address: addressLine.value ? { line1: addressLine.value } : null,
      phone: phone.value || null,
      email: email.value || null,
      logo_url: logoUrl.value || null,
      registration_number: registrationNumber.value || null,
      footer_text: footerText.value || null
    })
    saved.value = true
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="p-4 space-y-4 max-w-xl">
    <h1 class="text-h2 text-default">
      {{ t('documents.letterhead.title') }}
    </h1>

    <UInput v-model="practiceName" :placeholder="t('documents.letterhead.practice_name')" :disabled="!canEdit" />
    <UInput v-model="legalName" :placeholder="t('documents.letterhead.legal_name')" :disabled="!canEdit" />
    <UInput v-model="addressLine" :placeholder="t('documents.letterhead.address')" :disabled="!canEdit" />
    <UInput v-model="phone" :placeholder="t('documents.letterhead.phone')" :disabled="!canEdit" />
    <UInput v-model="email" :placeholder="t('documents.letterhead.email')" :disabled="!canEdit" />
    <UInput v-model="logoUrl" :placeholder="t('documents.letterhead.logo_url')" :disabled="!canEdit" />
    <UInput v-model="registrationNumber" :placeholder="t('documents.letterhead.registration_number')" :disabled="!canEdit" />
    <UTextarea v-model="footerText" :placeholder="t('documents.letterhead.footer_text')" :disabled="!canEdit" />

    <div class="flex items-center gap-2">
      <UButton v-if="canEdit" :loading="saving" @click="save">
        {{ saving ? t('documents.letterhead.saving') : t('documents.letterhead.save') }}
      </UButton>
      <span v-if="saved" class="text-sm text-success">{{ t('documents.letterhead.saved') }}</span>
    </div>
  </div>
</template>
