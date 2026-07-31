<script setup lang="ts">
/**
 * SetPublicCodeModal — configures the manual code for a public link
 * when the patient has neither phone nor DOB on file. The code is
 * shown to reception only; the email never carries it.
 */

const props = defineProps<{
  open: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'confirm': [payload: { code: string }]
  'cancel': []
}>()

const { t } = useI18n()

const code = ref('')

const isValid = computed(
  () => /^\d{4,6}$/.test(code.value)
)

function submit() {
  if (!isValid.value) return
  emit('confirm', { code: code.value })
}

watch(
  () => props.open,
  (opened) => {
    if (!opened) code.value = ''
  }
)
</script>

<template>
  <UModal
    :open="open"
    @update:open="(v) => emit('update:open', v)"
  >
    <template #content>
      <UCard>
        <template #header>
          <h2 class="text-lg font-semibold">
            {{ t('budget.modals.setPublicCode.title') }}
          </h2>
        </template>

        <div class="space-y-4 text-sm">
          <UAlert
            color="warning"
            variant="soft"
            :description="t('budget.modals.setPublicCode.description')"
            icon="i-lucide-shield-alert"
          />
          <UFormField
            :label="t('budget.modals.setPublicCode.codeLabel')"
            required
          >
            <UInput
              v-model="code"
              type="text"
              inputmode="numeric"
              pattern="[0-9]*"
              maxlength="6"
              :placeholder="'1234'"
            />
          </UFormField>
        </div>

        <template #footer>
          <div class="flex justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :disabled="loading"
              @click="emit('cancel')"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              color="primary"
              :loading="loading"
              :disabled="!isValid"
              @click="submit"
            >
              {{ t('budget.modals.setPublicCode.submit') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
