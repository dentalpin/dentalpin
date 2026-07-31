<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { RecallReason, RecallPriority, Recall } from '../composables/useRecalls'

interface Props {
  open: boolean
  patientId: string
  /** Pre-fill from a treatment-plan / odontogram action. */
  initialReason?: RecallReason
  initialNote?: string
  initialPriority?: RecallPriority
  initialAssignedProfessionalId?: string | null
  initialDueMonth?: string // YYYY-MM-01
  initialTreatmentId?: string | null
  initialTreatmentCategoryKey?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  initialReason: 'hygiene',
  initialPriority: 'normal'
})

const emit = defineEmits<{
  'update:open': [value: boolean]
  'saved': [recall: Recall]
}>()

const { t, locale } = useI18n()
const toast = useToast()
const recallsApi = useRecalls()

const isSubmitting = ref(false)
const reason = ref<RecallReason>(props.initialReason)
const priority = ref<RecallPriority>(props.initialPriority)
const dueMonth = ref<string>(props.initialDueMonth ?? defaultDueMonth())
const dueDate = ref<string>('')
const note = ref<string>(props.initialNote ?? '')
const assignedProfessionalId = ref<string | null>(props.initialAssignedProfessionalId ?? null)

function defaultDueMonth(): string {
  const today = new Date()
  // Next month, day 1.
  const d = new Date(today.getFullYear(), today.getMonth() + 1, 1)
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  return `${yyyy}-${mm}-01`
}

function shiftMonths(offset: number) {
  const today = new Date()
  const d = new Date(today.getFullYear(), today.getMonth() + offset, 1)
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  dueMonth.value = `${yyyy}-${mm}-01`
}

watch(() => props.open, (v) => {
  if (!v) return
  reason.value = props.initialReason
  priority.value = props.initialPriority
  dueMonth.value = props.initialDueMonth ?? defaultDueMonth()
  dueDate.value = ''
  note.value = props.initialNote ?? ''
  assignedProfessionalId.value = props.initialAssignedProfessionalId ?? null
})

interface ReasonMeta {
  value: RecallReason
  label: string
  icon: string
}

const reasons = computed<ReasonMeta[]>(() => [
  { value: 'hygiene', label: t('recalls.reasons.hygiene'), icon: 'i-lucide-sparkles' },
  { value: 'checkup', label: t('recalls.reasons.checkup'), icon: 'i-lucide-stethoscope' },
  { value: 'ortho_review', label: t('recalls.reasons.ortho_review'), icon: 'i-lucide-smile' },
  { value: 'implant_review', label: t('recalls.reasons.implant_review'), icon: 'i-lucide-anchor' },
  { value: 'post_op', label: t('recalls.reasons.post_op'), icon: 'i-lucide-bandage' },
  { value: 'treatment_followup', label: t('recalls.reasons.treatment_followup'), icon: 'i-lucide-clipboard-check' },
  { value: 'other', label: t('recalls.reasons.other'), icon: 'i-lucide-more-horizontal' }
])

const priorities = computed(() => [
  { value: 'low' as RecallPriority, label: t('recalls.priority.low'), color: 'neutral' as const },
  { value: 'normal' as RecallPriority, label: t('recalls.priority.normal'), color: 'info' as const },
  { value: 'high' as RecallPriority, label: t('recalls.priority.high'), color: 'error' as const }
])

const dueMonthLabel = computed(() => {
  const iso = dueMonth.value.length === 7 ? `${dueMonth.value}-01` : dueMonth.value
  const d = new Date(iso)
  return new Intl.DateTimeFormat(locale.value, {
    year: 'numeric',
    month: 'long'
  }).format(d)
})

const monthShortcuts = computed(() => [
  { offset: 1, label: '+1m' },
  { offset: 3, label: '+3m' },
  { offset: 6, label: '+6m' },
  { offset: 12, label: '+12m' }
])

function isShortcutActive(offset: number): boolean {
  const today = new Date()
  const target = new Date(today.getFullYear(), today.getMonth() + offset, 1)
  const yyyy = target.getFullYear()
  const mm = String(target.getMonth() + 1).padStart(2, '0')
  return dueMonth.value === `${yyyy}-${mm}-01`
}

async function save() {
  if (isSubmitting.value) return
  isSubmitting.value = true
  try {
    const month = dueMonth.value || defaultDueMonth()
    const monthDay1 = month.length === 7 ? `${month}-01` : month
    const res = await recallsApi.create({
      patient_id: props.patientId,
      due_month: monthDay1,
      due_date: dueDate.value || null,
      reason: reason.value,
      reason_note: note.value || null,
      priority: priority.value,
      assigned_professional_id: assignedProfessionalId.value || null,
      linked_treatment_id: props.initialTreatmentId ?? null,
      linked_treatment_category_key: props.initialTreatmentCategoryKey ?? null
    })
    toast.add({ title: t('common.success'), color: 'success' })
    emit('saved', res.data)
    emit('update:open', false)
  } catch (err: unknown) {
    toast.add({
      title: t('common.error'),
      description: (err as { data?: { detail?: string } })?.data?.detail ?? '',
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}

function close() {
  emit('update:open', false)
}
</script>

<template>
  <UModal
    :open="open"
    :title="t('recalls.modal.title')"
    :description="t('recalls.modal.subtitle')"
    :ui="{ content: 'sm:max-w-lg' }"
    @update:open="(v: boolean) => emit('update:open', v)"
  >
    <template #body>
      <div class="space-y-5 p-4 sm:p-5">
        <!-- Step 1: Reason — visual chips, primary thumb-friendly target -->
        <section>
          <label class="block text-caption uppercase tracking-wide text-subtle mb-2">
            {{ t('recalls.modal.reason') }}
          </label>
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
            <button
              v-for="r in reasons"
              :key="r.value"
              type="button"
              :aria-pressed="reason === r.value"
              class="flex items-center gap-2 px-3 py-2 rounded-token-md border text-sm text-left transition-colors"
              :class="reason === r.value
                ? 'border-primary bg-primary/10 text-primary-accent'
                : 'border-default bg-default hover:bg-elevated text-default'"
              @click="reason = r.value"
            >
              <UIcon
                :name="r.icon"
                class="w-4 h-4 shrink-0"
              />
              <span class="truncate">{{ r.label }}</span>
            </button>
          </div>
        </section>

        <!-- Step 2: When — month picker + quick shortcuts -->
        <section>
          <label class="block text-caption uppercase tracking-wide text-subtle mb-2">
            {{ t('recalls.modal.when') }}
          </label>
          <div class="flex flex-wrap items-center gap-2 mb-2">
            <UButton
              v-for="s in monthShortcuts"
              :key="s.offset"
              size="xs"
              :color="isShortcutActive(s.offset) ? 'primary' : 'neutral'"
              :variant="isShortcutActive(s.offset) ? 'soft' : 'outline'"
              @click="shiftMonths(s.offset)"
            >
              {{ s.label }}
            </UButton>
          </div>
          <MonthPickerDropdown v-model="dueMonth" />
          <p class="text-caption text-subtle mt-1.5">
            {{ t('recalls.modal.targetMonth') }}: <span class="text-default font-medium">{{ dueMonthLabel }}</span>
          </p>

          <details class="mt-3 group">
            <summary class="flex items-center gap-1 text-caption text-subtle cursor-pointer hover:text-default select-none">
              <UIcon
                name="i-lucide-chevron-right"
                class="w-3.5 h-3.5 transition-transform group-open:rotate-90"
              />
              {{ t('recalls.modal.preciseDate') }}
            </summary>
            <div class="mt-2">
              <UInput
                v-model="dueDate"
                type="date"
                class="w-full"
              />
            </div>
          </details>
        </section>

        <!-- Step 3: Priority — segmented control -->
        <section>
          <label class="block text-caption uppercase tracking-wide text-subtle mb-2">
            {{ t('recalls.modal.priority') }}
          </label>
          <div class="inline-flex rounded-token-md border border-default bg-default p-0.5 w-full">
            <button
              v-for="p in priorities"
              :key="p.value"
              type="button"
              class="flex-1 px-3 py-1.5 rounded text-sm font-medium transition-colors"
              :class="priority === p.value
                ? 'bg-primary/15 text-primary-accent'
                : 'text-subtle hover:text-default'"
              :aria-pressed="priority === p.value"
              @click="priority = p.value"
            >
              {{ p.label }}
            </button>
          </div>
        </section>

        <!-- Step 4: Note — optional context -->
        <section>
          <label class="block text-caption uppercase tracking-wide text-subtle mb-2">
            {{ t('recalls.modal.note') }}
            <span class="lowercase font-normal text-dimmed">· {{ t('recalls.modal.optional') }}</span>
          </label>
          <UTextarea
            v-model="note"
            :rows="3"
            :maxlength="500"
            :placeholder="t('recalls.modal.notePlaceholder')"
            class="w-full"
          />
          <p
            v-if="note.length > 400"
            class="text-caption text-dimmed mt-1 text-right tnum"
          >
            {{ note.length }} / 500
          </p>
        </section>
      </div>
    </template>
    <template #footer>
      <div class="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 p-3">
        <UButton
          color="neutral"
          variant="ghost"
          :disabled="isSubmitting"
          @click="close"
        >
          {{ t('actions.cancel') }}
        </UButton>
        <UButton
          color="primary"
          icon="i-lucide-bell"
          :loading="isSubmitting"
          @click="save"
        >
          {{ t('recalls.actions.save') }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>
