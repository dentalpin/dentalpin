<script setup lang="ts">
import { errorMessage } from '~~/app/utils/error'
import {
  useLeads,
  type Lead,
  type LeadCreatePayload,
  type LeadStatus
} from '../../composables/useLeads'
// The availability types come from the util that owns DAY_ORDER / SLOT_ORDER.
// Importing them from the composable too is what produced the duplicated
// auto-import of the same type name, and the loose `string[]` form field below
// let the modal hold values the API contract (`DayOfWeek[]`) rejects.
import type { AvailabilitySlot, DayOfWeek } from '../../utils/leadAvailability'
import {
  hasErrors,
  validateLeadForm,
  type LeadFormErrors,
  type ValidationKey
} from '../../utils/leadValidation'

/**
 * Manual creation and editing of a lead.
 *
 * The create path is NOT a plain save: POST /leads/ routes the enquiry
 * (a phone/email that already belongs to a patient queues a recall and
 * writes no lead), so the modal branches on the outcome. Saying "saved"
 * on the recall branch would file a card that does not exist.
 */
interface Props {
  open: boolean
  /** null = create mode. */
  lead?: Lead | null
}

const props = withDefaults(defineProps<Props>(), { lead: null })

const emit = defineEmits<{
  'update:open': [value: boolean]
  'saved': [lead: Lead]
}>()

const { t } = useI18n()
const toast = useToast()
const router = useRouter()
const leadsApi = useLeads()

const STATUSES: LeadStatus[] = ['new', 'contacted', 'converted', 'discarded']

const saving = ref(false)
const form = reactive({
  full_name: '',
  phone: '',
  email: '',
  motive: '',
  description: '',
  availability_days: [] as DayOfWeek[],
  availability_slot: null as AvailabilitySlot | null,
  status: 'new' as LeadStatus
})

// --- Validation -----------------------------------------------------------
// Errors appear once a field has been left (blur) or once the user tried to
// save — never while they are still typing the first characters. The Save
// button stays enabled on purpose: a disabled button with no explanation is
// worse than a warning that says which field is wrong.
const submitted = ref(false)
const touched = ref<Record<string, boolean>>({})

const errors = computed<LeadFormErrors>(() =>
  validateLeadForm({
    full_name: form.full_name,
    phone: form.phone,
    email: form.email,
    motive: form.motive
  })
)

function showFor(field: keyof LeadFormErrors): boolean {
  return submitted.value || Boolean(touched.value[field])
}

function fieldError(field: keyof LeadFormErrors): string | undefined {
  const key: ValidationKey | undefined = errors.value[field]
  return key && showFor(field) ? t(`leads.validation.${key}`) : undefined
}

function touch(field: keyof LeadFormErrors) {
  touched.value = { ...touched.value, [field]: true }
}

const isEdit = computed(() => Boolean(props.lead))

watch(
  () => [props.open, props.lead?.id],
  () => {
    if (!props.open) return
    submitted.value = false
    touched.value = {}
    const lead = props.lead
    form.full_name = lead?.full_name ?? ''
    form.phone = lead?.phone ?? ''
    form.email = lead?.email ?? ''
    form.motive = lead?.motive ?? ''
    form.description = lead?.description ?? ''
    form.availability_days = lead?.availability_days ?? []
    form.availability_slot = lead?.availability_slot ?? null
    form.status = lead?.status ?? 'new'
  },
  { immediate: true }
)

function close() {
  emit('update:open', false)
  submitted.value = false
  touched.value = {}
}

async function submit() {
  // Never send a payload the server would reject: mark every bad field and
  // say so, in the user's language.
  submitted.value = true
  if (hasErrors(errors.value)) {
    toast.add({
      title: t('leads.validation.fixErrors'),
      color: 'warning'
    })
    return
  }

  saving.value = true
  try {
    if (!isEdit.value) {
      const payload: LeadCreatePayload = {
        full_name: form.full_name.trim(),
        phone: form.phone.trim(),
        email: form.email.trim() || null,
        motive: form.motive.trim(),
        description: form.description.trim() || null,
        availability_days: form.availability_days.length ? form.availability_days : null,
        availability_slot: form.availability_slot
      }
      const response = await leadsApi.create(payload)
      const result = response.data
      close()
      if (result.outcome === 'lead_created' && result.lead) {
        toast.add({ title: t('common.success'), description: t('leads.newLead'), color: 'success' })
        emit('saved', result.lead)
      } else {
        // The enquiry is a recall, not a card on this list.
        const name = result.recalled_patient
          ? `${result.recalled_patient.first_name} ${result.recalled_patient.last_name}`
          : form.full_name
        toast.add({
          title: t('leads.routing.recallQueued', { name }),
          color: 'info',
          actions: [
            {
              label: t('leads.routing.openRecalls'),
              onClick: () => {
                void router.push('/recalls')
              }
            }
          ]
        })
      }
      return
    }

    // Edit mode. exclude_unset semantics: only what the user changed.
    const updated = await leadsApi.update(props.lead!.id, {
      full_name: form.full_name.trim(),
      phone: form.phone.trim(),
      email: form.email.trim() || null,
      motive: form.motive.trim(),
      description: form.description.trim() || null,
      availability_days: form.availability_days.length ? form.availability_days : null,
      availability_slot: form.availability_slot,
      status: form.status
    })
    close()
    toast.add({ title: t('common.success'), description: t('leads.fields.status'), color: 'success' })
    emit('saved', updated.data)
  } catch (e: unknown) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('leads.errors.save')),
      color: 'error'
    })
  } finally {
    saving.value = false
  }
}

/** One-click status moves from the call log. */
async function quickStatus(status: LeadStatus) {
  if (!props.lead) return
  saving.value = true
  try {
    const updated = await leadsApi.update(props.lead.id, { status })
    close()
    toast.add({
      title: t('common.success'),
      description: t(`leads.status.${status}`),
      color: 'success'
    })
    emit('saved', updated.data)
  } catch (e: unknown) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('leads.errors.save')),
      color: 'error'
    })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UModal
    :open="open"
    @update:open="(value: boolean) => emit('update:open', value)"
  >
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="text-h1 text-default">
              {{ isEdit ? t('leads.actions.edit') : t('leads.newLead') }}
            </h2>
            <UButton
              variant="ghost"
              color="neutral"
              icon="i-lucide-x"
              :aria-label="t('common.close')"
              @click="close"
            />
          </div>
        </template>

        <form
          class="space-y-4"
          @submit.prevent="submit"
        >
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <UFormField
              :label="t('leads.fields.fullName')"
              :error="fieldError('full_name')"
              required
            >
              <UInput
                v-model="form.full_name"
                :placeholder="t('leads.fields.fullName')"
                maxlength="200"
                @blur="touch('full_name')"
              />
            </UFormField>
            <UFormField
              :label="t('leads.fields.phone')"
              :error="fieldError('phone')"
              required
            >
              <UInput
                v-model="form.phone"
                type="tel"
                dir="ltr"
                :placeholder="t('leads.fields.phone')"
                maxlength="32"
                @blur="touch('phone')"
              />
            </UFormField>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <UFormField
              :label="t('leads.fields.email')"
              :error="fieldError('email')"
            >
              <UInput
                v-model="form.email"
                type="email"
                dir="ltr"
                :placeholder="t('leads.fields.email')"
                maxlength="254"
                @blur="touch('email')"
              />
            </UFormField>
            <UFormField
              :label="t('leads.fields.motive')"
              :error="fieldError('motive')"
              required
            >
              <UInput
                v-model="form.motive"
                :placeholder="t('leads.fields.motive')"
                maxlength="200"
                @blur="touch('motive')"
              />
            </UFormField>
          </div>

          <UFormField :label="t('leads.fields.description')">
            <UTextarea
              v-model="form.description"
              :rows="3"
              :placeholder="t('leads.fields.description')"
            />
          </UFormField>

          <UFormField
            :label="t('leads.fields.availability')"
            :help="t('leads.fields.availabilityHint')"
          >
            <LeadAvailabilityPicker
              v-model:days="form.availability_days"
              v-model:time-slot="form.availability_slot"
            />
          </UFormField>

          <!-- Create mode never offers a status: a brand-new enquiry is
               not yet contacted. -->
          <UFormField
            v-if="isEdit"
            :label="t('leads.fields.status')"
          >
            <USelect
              v-model="form.status"
              :items="STATUSES.map(value => ({ value, label: t(`leads.status.${value}`) }))"
            />
          </UFormField>
        </form>

        <template #footer>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div
              v-if="isEdit"
              class="flex flex-wrap gap-2"
            >
              <UButton
                v-if="lead && lead.status !== 'contacted'"
                variant="outline"
                color="neutral"
                size="sm"
                icon="i-lucide-phone-call"
                :disabled="saving"
                @click="quickStatus('contacted')"
              >
                {{ t('leads.actions.markContacted') }}
              </UButton>
              <UButton
                v-if="lead && lead.status !== 'discarded'"
                variant="ghost"
                color="error"
                size="sm"
                icon="i-lucide-archive"
                :disabled="saving"
                @click="quickStatus('discarded')"
              >
                {{ t('leads.actions.discard') }}
              </UButton>
            </div>
            <div class="flex gap-2 ms-auto">
              <UButton
                variant="outline"
                color="neutral"
                @click="close"
              >
                {{ t('leads.actions.cancel') }}
              </UButton>
              <!-- Enabled even with invalid input: clicking it marks the
                   offending fields and explains what is wrong, which a
                   dead button cannot do. -->
              <UButton
                color="primary"
                :loading="saving"
                @click="submit"
              >
                {{ t('leads.actions.save') }}
              </UButton>
            </div>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
