<script setup lang="ts">
/**
 * Create / edit a cabinet (name + colour, plus the active flag when
 * editing, #1237). Pass `cabinet` to edit;
 * omit it to create. Emits `saved` after a successful write. Also used
 * as the onboarding "cabinets" mini-modal (create mode).
 */
import type { Cabinet } from '~/types'

const props = defineProps<{ open: boolean, cabinet?: Cabinet | null }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void, (e: 'saved'): void }>()

const { t } = useI18n()
const clinic = useClinic()

const CABINET_COLORS = [
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444',
  '#8B5CF6', '#EC4899', '#06B6D4', '#F97316'
]

const isOpen = computed({
  get: () => props.open,
  set: (v: boolean) => emit('update:open', v)
})
const isEdit = computed(() => !!props.cabinet)

const form = ref({ name: '', color: CABINET_COLORS[0]!, is_active: true })
const isSaving = ref(false)

watch(() => props.open, (open) => {
  if (!open) return
  form.value = props.cabinet
    ? { name: props.cabinet.name, color: props.cabinet.color, is_active: props.cabinet.is_active !== false }
    : { name: '', color: CABINET_COLORS[0]!, is_active: true }
})

async function submit() {
  isSaving.value = true
  const result = props.cabinet
    ? await clinic.updateCabinet(props.cabinet.id, {
        name: form.value.name,
        color: form.value.color,
        is_active: form.value.is_active
      })
    : await clinic.createCabinet({ name: form.value.name, color: form.value.color })
  isSaving.value = false
  if (result) {
    emit('saved')
    isOpen.value = false
  }
}
</script>

<template>
  <UModal v-model:open="isOpen">
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              :name="isEdit ? 'i-lucide-pencil' : 'i-lucide-square-plus'"
              class="w-5 h-5 text-primary-accent"
            />
            <h3 class="font-semibold text-default">
              {{ isEdit ? t('settings.editCabinet') : t('settings.newCabinet') }}
            </h3>
          </div>
        </template>

        <form
          class="space-y-4"
          @submit.prevent="submit"
        >
          <UFormField :label="t('common.name')">
            <UInput
              v-model="form.name"
              class="w-full"
              required
              autofocus
            />
          </UFormField>

          <UFormField :label="t('common.color')">
            <div class="flex flex-wrap gap-2">
              <button
                v-for="color in CABINET_COLORS"
                :key="color"
                type="button"
                class="w-11 h-11 sm:w-8 sm:h-8 rounded-full border-2 transition-all"
                :class="form.color === color ? 'border-default ring-2 ring-[var(--color-primary)] scale-110' : 'border-transparent'"
                :style="{ backgroundColor: color }"
                :aria-label="color"
                :aria-pressed="form.color === color"
                @click="form.color = color"
              />
            </div>
          </UFormField>

          <UFormField
            v-if="isEdit"
            :description="t('settings.cabinetActiveHint')"
          >
            <USwitch
              v-model="form.is_active"
              :label="t('settings.cabinetActive')"
            />
          </UFormField>

          <div class="flex justify-end gap-2 pt-4">
            <UButton
              variant="ghost"
              @click="isOpen = false"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              type="submit"
              :loading="isSaving"
            >
              {{ isEdit ? t('settings.saveChanges') : t('settings.createCabinet') }}
            </UButton>
          </div>
        </form>
      </UCard>
    </template>
  </UModal>
</template>
