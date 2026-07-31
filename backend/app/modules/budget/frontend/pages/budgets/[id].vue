<script setup lang="ts">
import type { BudgetItem, InvoiceListItem, PaginatedResponse, SignatureCreate } from '~~/app/types'
import { BUDGET_STATUS_ROLE } from '~~/app/config/severity'
import { PERMISSIONS } from '~~/app/config/permissions'
import type { EntityChip } from '~~/app/components/shared/EntityStatusChips.vue'
import type { EntityAction } from '~~/app/components/shared/EntityActionBar.vue'
import type { TotalLine } from '~~/app/components/shared/EntityTotalsCard.vue'
import type { InfoItem } from '~~/app/components/shared/EntityInfoCard.vue'
import { errorMessage } from '~~/app/utils/error'
import PublicBudgetLinkCard from '../../components/budget/PublicBudgetLinkCard.vue'
import BudgetSignatureCard from '../../components/budget/BudgetSignatureCard.vue'

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const api = useApi()

const {
  currentBudget,
  isLoading,
  fetchBudget,
  updateBudget,
  removeItem,
  sendBudget,
  acceptBudget,
  rejectBudget,
  cancelBudget,
  duplicateBudget,
  downloadPDF,
  canEdit,
  canSend,
  canAccept,
  canCancel
} = useBudgets()

const hasActiveInvoice = ref(false)

// Check if budget can be invoiced (budget accepted and has uninvoiced items)
function canInvoice(): boolean {
  if (!currentBudget.value) return false
  // Budget must be accepted or completed to be invoiced
  if (!['accepted', 'completed'].includes(currentBudget.value.status)) {
    return false
  }
  // Hide if budget already has a non-cancelled invoice
  if (hasActiveInvoice.value) return false
  // Must have at least one item with available quantity to invoice
  return currentBudget.value.items.some(item =>
    item.quantity > (item.invoiced_quantity || 0)
  )
}

async function checkActiveInvoice(budgetId: string) {
  try {
    const response = await api.get<PaginatedResponse<InvoiceListItem>>(
      `/api/v1/billing/invoices?budget_id=${budgetId}&page_size=100`
    )
    hasActiveInvoice.value = response.data.some(inv => inv.status !== 'cancelled')
  } catch {
    hasActiveInvoice.value = false
  }
}

function goToCreateInvoice() {
  if (!currentBudget.value) return
  router.push(`/invoices/from-budget/${currentBudget.value.id}`)
}

const budgetId = computed(() => route.params.id as string)
const comesFromPatient = computed(() => route.query.from === 'patient' && route.query.patientId)
const backLabel = computed(() => comesFromPatient.value ? t('actions.back') : t('budget.title'))

// Load budget
async function loadBudget() {
  const budget = await fetchBudget(budgetId.value)
  if (!budget) {
    toast.add({
      title: t('common.error'),
      description: t('budget.errors.notFound'),
      color: 'error'
    })
    router.push('/budgets')
    return
  }
  if (can(PERMISSIONS.billing.read)) {
    await checkActiveInvoice(budget.id)
  }
}

onMounted(() => {
  loadBudget()
})

// Modal states
const isAddItemModalOpen = ref(false)
const isSignatureModalOpen = ref(false)
const isSendModalOpen = ref(false)
const isShareLinkModalOpen = ref(false)
const isSignatureViewModalOpen = ref(false)
const signatureAction = ref<'accept' | 'reject'>('accept')

// Send form
const sendForm = reactive({
  send_email: false,
  custom_message: ''
})

// Edit state
const isEditing = ref(false)
const editForm = reactive({
  valid_from: '',
  valid_until: '',
  global_discount_type: '',
  global_discount_value: '',
  internal_notes: '',
  patient_notes: ''
})

function startEditing() {
  if (!currentBudget.value) return
  editForm.valid_from = currentBudget.value.valid_from
  editForm.valid_until = currentBudget.value.valid_until || ''
  editForm.global_discount_type = currentBudget.value.global_discount_type || ''
  editForm.global_discount_value = currentBudget.value.global_discount_value?.toString() || ''
  editForm.internal_notes = currentBudget.value.internal_notes || ''
  editForm.patient_notes = currentBudget.value.patient_notes || ''
  isEditing.value = true
}

async function saveEdits() {
  if (!currentBudget.value) return

  try {
    await updateBudget(currentBudget.value.id, {
      valid_from: editForm.valid_from || undefined,
      valid_until: editForm.valid_until || undefined,
      global_discount_type: (editForm.global_discount_type as 'percentage' | 'absolute') || undefined,
      global_discount_value: editForm.global_discount_value
        ? parseFloat(editForm.global_discount_value)
        : undefined,
      internal_notes: editForm.internal_notes || undefined,
      patient_notes: editForm.patient_notes || undefined
    })

    toast.add({
      title: t('common.success'),
      description: t('budget.messages.updated'),
      color: 'success'
    })
    isEditing.value = false
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('budget.errors.update')),
      color: 'error'
    })
  }
}

// Item management
function handleItemAdded() {
  isAddItemModalOpen.value = false
  loadBudget()
}

async function handleRemoveItem(item: BudgetItem) {
  if (!currentBudget.value) return
  if (!confirm(t('budget.items.remove') + '?')) return

  try {
    await removeItem(currentBudget.value.id, item.id)
    toast.add({
      title: t('common.success'),
      description: t('budget.messages.itemRemoved'),
      color: 'success'
    })
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('budget.errors.delete')),
      color: 'error'
    })
  }
}

// Workflow actions
function openSignatureModal(action: 'accept' | 'reject') {
  signatureAction.value = action
  isSignatureModalOpen.value = true
}

// Signature form
const signatureForm = reactive<SignatureCreate>({
  signed_by_name: '',
  signed_by_email: '',
  relationship_to_patient: 'patient'
})

async function handleSignatureSubmit() {
  if (!currentBudget.value || !signatureForm.signed_by_name) return

  try {
    if (signatureAction.value === 'accept') {
      await acceptBudget(currentBudget.value.id, { signature: signatureForm })
      toast.add({
        title: t('common.success'),
        description: t('budget.messages.accepted'),
        color: 'success'
      })
    } else {
      await rejectBudget(currentBudget.value.id, { signature: signatureForm })
      toast.add({
        title: t('common.success'),
        description: t('budget.messages.rejected'),
        color: 'success'
      })
    }

    isSignatureModalOpen.value = false
    resetSignatureForm()
    await loadBudget()
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, signatureAction.value === 'accept'
        ? t('budget.errors.accept')
        : t('budget.errors.reject')),
      color: 'error'
    })
  }
}

function resetSignatureForm() {
  signatureForm.signed_by_name = ''
  signatureForm.signed_by_email = ''
  signatureForm.relationship_to_patient = 'patient'
}

async function handleCancel() {
  if (!currentBudget.value) return
  if (!confirm(t('budget.confirmations.cancel'))) return

  try {
    await cancelBudget(currentBudget.value.id)
    toast.add({
      title: t('common.success'),
      description: t('budget.messages.cancelled'),
      color: 'success'
    })
    await loadBudget()
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('budget.errors.update')),
      color: 'error'
    })
  }
}

async function handleSend() {
  if (!currentBudget.value) return

  try {
    await sendBudget(currentBudget.value.id, {
      send_email: sendForm.send_email,
      custom_message: sendForm.custom_message || undefined
    })

    const message = sendForm.send_email
      ? t('budget.messages.sentByEmail')
      : t('budget.messages.sentManually')

    toast.add({
      title: t('common.success'),
      description: message,
      color: 'success'
    })

    isSendModalOpen.value = false
    resetSendForm()
    await loadBudget()
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('budget.errors.send')),
      color: 'error'
    })
  }
}

function resetSendForm() {
  sendForm.send_email = false
  sendForm.custom_message = ''
}

async function handleDuplicate() {
  if (!currentBudget.value) return

  try {
    const newBudget = await duplicateBudget(currentBudget.value.id)
    toast.add({
      title: t('common.success'),
      description: t('budget.messages.duplicated'),
      color: 'success'
    })
    router.push(`/budgets/${newBudget.id}`)
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('budget.errors.create')),
      color: 'error'
    })
  }
}

async function handleDownloadPDF() {
  if (!currentBudget.value) return

  try {
    await downloadPDF(currentBudget.value.id, locale.value)
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('budget.pdf.downloadError')),
      color: 'error'
    })
  }
}

// Format helpers
const { format: formatMoney } = useCurrency()

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(locale.value)
}

const statusChips = computed<EntityChip[]>(() => {
  const budget = currentBudget.value
  if (!budget) return []
  return [
    {
      key: 'status',
      role: BUDGET_STATUS_ROLE[budget.status] ?? 'neutral',
      label: t(`budget.status.${budget.status}`)
    }
  ]
})

const primaryActions = computed<EntityAction[]>(() => {
  const budget = currentBudget.value
  if (!budget) return []
  const actions: EntityAction[] = []

  if (canSend(budget) && can(PERMISSIONS.budget.write)) {
    actions.push({
      key: 'send',
      label: t('budget.actions.send'),
      icon: 'i-lucide-send',
      onClick: () => { isSendModalOpen.value = true }
    })
  }

  if (budget.public_token && ['sent', 'accepted', 'rejected', 'expired'].includes(budget.status)) {
    actions.push({
      key: 'shareLink',
      label: t('budget.publicLink.action'),
      icon: 'i-lucide-share-2',
      variant: 'soft',
      onClick: () => { isShareLinkModalOpen.value = true }
    })
  }

  if (['accepted', 'completed'].includes(budget.status)) {
    actions.push({
      key: 'viewSignature',
      label: t('budget.signature.viewAction'),
      icon: 'i-lucide-pen-tool',
      variant: 'soft',
      onClick: () => { isSignatureViewModalOpen.value = true }
    })
  }

  if (canAccept(budget) && can(PERMISSIONS.budget.write)) {
    actions.push({
      key: 'reject',
      label: t('budget.actions.reject'),
      icon: 'i-lucide-x',
      color: 'error',
      variant: 'ghost',
      onClick: () => openSignatureModal('reject')
    })
    actions.push({
      key: 'accept',
      label: t('budget.actions.accept'),
      icon: 'i-lucide-check',
      color: 'success',
      onClick: () => openSignatureModal('accept')
    })
  }

  if (canInvoice() && can(PERMISSIONS.billing.write)) {
    actions.push({
      key: 'createInvoice',
      label: t('invoice.createFromBudget'),
      icon: 'i-lucide-receipt',
      onClick: goToCreateInvoice
    })
  }

  return actions
})

const overflowActions = computed<EntityAction[]>(() => {
  const budget = currentBudget.value
  if (!budget) return []
  const actions: EntityAction[] = [
    {
      key: 'downloadPdf',
      label: t('budget.actions.downloadPdf'),
      icon: 'i-lucide-download',
      onClick: handleDownloadPDF
    }
  ]
  if (can(PERMISSIONS.budget.write)) {
    actions.push({
      key: 'duplicate',
      label: t('budget.actions.duplicate'),
      icon: 'i-lucide-copy',
      onClick: handleDuplicate
    })
  }
  if (canCancel(budget) && can(PERMISSIONS.budget.write)) {
    actions.push({
      key: 'cancel',
      label: t('budget.actions.cancel'),
      icon: 'i-lucide-ban',
      destructive: true,
      onClick: handleCancel
    })
  }
  return actions
})

const totalsLines = computed<TotalLine[]>(() => {
  const budget = currentBudget.value
  if (!budget) return []
  const lines: TotalLine[] = [
    { key: 'subtotal', label: t('budget.subtotal'), value: budget.subtotal }
  ]
  if (budget.total_discount > 0) {
    lines.push({
      key: 'discount',
      label: t('budget.totalDiscount'),
      value: budget.total_discount,
      sign: '-',
      role: 'success'
    })
  }
  if (budget.total_tax > 0) {
    lines.push({
      key: 'tax',
      label: t('budget.totalTax'),
      value: budget.total_tax
    })
  }
  lines.push({
    key: 'total',
    label: t('budget.total'),
    value: budget.total,
    emphasis: 'strong',
    divider: 'above'
  })
  return lines
})

const infoItems = computed<InfoItem[]>(() => {
  const budget = currentBudget.value
  if (!budget) return []
  const items: InfoItem[] = [
    { key: 'number', label: t('budget.budgetNumber'), value: budget.budget_number },
    { key: 'version', label: t('budget.version'), value: `v${budget.version}` }
  ]
  if (budget.creator) {
    items.push({
      key: 'creator',
      label: t('common.createdBy'),
      value: `${budget.creator.first_name} ${budget.creator.last_name}`
    })
  }
  items.push({
    key: 'createdAt',
    label: t('common.date'),
    value: formatDate(budget.created_at)
  })
  if (budget.treatment_plan) {
    const plan = budget.treatment_plan
    items.push({
      key: 'plan',
      label: t('budget.treatmentPlan'),
      link: {
        to: `/treatment-plans/${plan.id}`,
        label: plan.title ? `${plan.plan_number} — ${plan.title}` : plan.plan_number
      }
    })
  }
  return items
})

function getItemName(item: BudgetItem): string {
  if (!item.catalog_item) return '-'
  return item.catalog_item.names[locale.value] || item.catalog_item.names.es || item.catalog_item.internal_code
}
</script>

<template>
  <div class="space-y-6">
    <!-- Loading -->
    <div
      v-if="isLoading"
      class="space-y-4"
    >
      <USkeleton class="h-12 w-1/3" />
      <USkeleton class="h-64 w-full" />
    </div>

    <template v-else-if="currentBudget">
      <!-- Header -->
      <DetailPageHeader
        :title="currentBudget.budget_number"
        :version="currentBudget.version"
        :back-to="{
          to: comesFromPatient ? `/patients/${route.query.patientId}` : '/budgets',
          label: backLabel
        }"
      >
        <template #status>
          <EntityStatusChips :chips="statusChips" />
        </template>
        <template #subtitle>
          <NuxtLink
            v-if="currentBudget.patient"
            :to="`/patients/${currentBudget.patient.id}`"
            class="inline-block text-body text-primary-accent hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300 hover:underline"
          >
            {{ currentBudget.patient.first_name }} {{ currentBudget.patient.last_name }}
          </NuxtLink>
        </template>
        <template #actions>
          <EntityActionBar
            :primary="primaryActions"
            :overflow="overflowActions"
          />
        </template>
      </DetailPageHeader>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Main content -->
        <div class="lg:col-span-2 space-y-6">
          <!-- Budget details -->
          <UCard>
            <template #header>
              <div class="flex items-center justify-between">
                <h2 class="text-h1 text-default">
                  {{ t('budget.view') }}
                </h2>
                <UButton
                  v-if="canEdit(currentBudget) && can(PERMISSIONS.budget.write) && !isEditing"
                  variant="ghost"
                  color="neutral"
                  icon="i-lucide-pencil"
                  size="sm"
                  @click="startEditing"
                >
                  {{ t('common.edit') }}
                </UButton>
              </div>
            </template>

            <!-- View mode -->
            <div
              v-if="!isEditing"
              class="grid grid-cols-1 sm:grid-cols-2 gap-4"
            >
              <div>
                <span class="text-caption text-subtle">{{ t('budget.validFrom') }}</span>
                <p class="font-medium">
                  {{ formatDate(currentBudget.valid_from) }}
                </p>
              </div>
              <div>
                <span class="text-caption text-subtle">{{ t('budget.validUntil') }}</span>
                <p class="font-medium">
                  {{ currentBudget.valid_until ? formatDate(currentBudget.valid_until) : t('budget.noExpiry') }}
                </p>
              </div>
              <div v-if="currentBudget.global_discount_value">
                <span class="text-caption text-subtle">{{ t('budget.globalDiscount') }}</span>
                <p class="font-medium">
                  {{ currentBudget.global_discount_type === 'percentage'
                    ? `${currentBudget.global_discount_value}%`
                    : formatMoney(currentBudget.global_discount_value) }}
                </p>
              </div>
              <div v-if="currentBudget.patient_notes">
                <span class="text-caption text-subtle">{{ t('budget.patientNotes') }}</span>
                <p class="mt-1">
                  {{ currentBudget.patient_notes }}
                </p>
              </div>
            </div>

            <!-- Edit mode -->
            <form
              v-else
              class="space-y-4"
              @submit.prevent="saveEdits"
            >
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <UFormField :label="t('budget.validFrom')">
                  <UInput
                    v-model="editForm.valid_from"
                    type="date"
                  />
                </UFormField>
                <UFormField :label="t('budget.validUntil')">
                  <UInput
                    v-model="editForm.valid_until"
                    type="date"
                  />
                </UFormField>
              </div>

              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <UFormField :label="t('budget.discountType')">
                  <USelect
                    v-model="editForm.global_discount_type"
                    :items="[
                      { label: '-', value: '' },
                      { label: t('budget.percentage'), value: 'percentage' },
                      { label: t('budget.absolute'), value: 'absolute' }
                    ]"
                  />
                </UFormField>
                <UFormField :label="t('budget.discountValue')">
                  <UInput
                    v-model="editForm.global_discount_value"
                    type="number"
                    step="0.01"
                    min="0"
                  />
                </UFormField>
              </div>

              <UFormField :label="t('budget.patientNotes')">
                <UTextarea
                  v-model="editForm.patient_notes"
                  :placeholder="t('budget.patientNotesPlaceholder')"
                  :rows="3"
                />
              </UFormField>

              <UFormField :label="t('budget.internalNotes')">
                <UTextarea
                  v-model="editForm.internal_notes"
                  :placeholder="t('budget.internalNotesPlaceholder')"
                  :rows="3"
                />
              </UFormField>

              <div class="flex justify-end gap-2">
                <UButton
                  variant="outline"
                  color="neutral"
                  @click="isEditing = false"
                >
                  {{ t('common.cancel') }}
                </UButton>
                <UButton
                  type="submit"
                  color="primary"
                >
                  {{ t('common.save') }}
                </UButton>
              </div>
            </form>
          </UCard>

          <!-- Items -->
          <UCard>
            <template #header>
              <div class="flex items-center justify-between">
                <h2 class="text-h1 text-default">
                  {{ t('budget.items.title') }}
                </h2>
                <UButton
                  v-if="canEdit(currentBudget) && can(PERMISSIONS.budget.write)"
                  icon="i-lucide-plus"
                  size="sm"
                  @click="isAddItemModalOpen = true"
                >
                  {{ t('budget.items.add') }}
                </UButton>
              </div>
            </template>

            <div
              v-if="currentBudget.items.length === 0"
              class="text-center py-8 text-subtle"
            >
              {{ t('budget.items.empty') }}
            </div>

            <div v-else>
              <div class="divide-y divide-[var(--color-border-subtle)]">
                <div
                  v-for="item in currentBudget.items"
                  :key="item.id"
                  class="py-4 -mx-4 px-4 flex items-start gap-4 hover:bg-[var(--ui-bg-elevated)] transition-colors"
                >
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span class="font-medium">{{ getItemName(item) }}</span>
                      <span
                        v-if="item.tooth_number"
                        class="inline-flex items-center px-1.5 py-0.5 rounded bg-[var(--ui-bg-elevated)] text-caption font-medium text-default"
                      >
                        #{{ item.tooth_number }}
                        <span
                          v-if="item.surfaces?.length"
                          class="ml-1 text-subtle font-normal"
                        >
                          {{ item.surfaces.join(', ') }}
                        </span>
                      </span>
                    </div>
                    <div class="text-caption text-subtle mt-1 tabular-nums">
                      {{ item.quantity }} × {{ formatMoney(item.unit_price) }}
                      <span
                        v-if="item.line_discount > 0"
                        class="text-success-accent"
                      >
                        -{{ formatMoney(item.line_discount) }}
                      </span>
                    </div>
                    <p
                      v-if="item.notes"
                      class="text-caption text-subtle mt-1"
                    >
                      {{ item.notes }}
                    </p>
                  </div>
                  <div class="text-right shrink-0">
                    <p class="font-semibold tabular-nums">
                      {{ formatMoney(item.line_total) }}
                    </p>
                  </div>
                  <UButton
                    v-if="canEdit(currentBudget) && can(PERMISSIONS.budget.write)"
                    variant="ghost"
                    color="error"
                    icon="i-lucide-trash-2"
                    size="sm"
                    @click="handleRemoveItem(item)"
                  />
                </div>
              </div>

              <div class="pt-3 mt-3 border-t border-default flex justify-between text-caption text-subtle">
                <span>{{ currentBudget.items.length }} {{ currentBudget.items.length === 1 ? t('budget.items.singular') : t('budget.items.plural') }}</span>
                <span class="tabular-nums">{{ t('budget.subtotal') }}: {{ formatMoney(currentBudget.subtotal) }}</span>
              </div>
            </div>
          </UCard>
        </div>

        <!-- Sidebar — module-driven slot first (payments / signatures /
             reminders), then native budget cards. Modules register via
             ``registerSlot('budget.detail.sidebar', ...)``. Budget
             never imports them; the registry is the only contract. -->
        <div class="space-y-6">
          <ModuleSlot
            name="budget.detail.sidebar"
            :ctx="{ budget: currentBudget }"
          />

          <EntityTotalsCard
            :title="t('budget.total')"
            :lines="totalsLines"
          />

          <EntityInfoCard :items="infoItems" />
        </div>
      </div>
    </template>

    <!-- Add Item Modal -->
    <BudgetItemModal
      v-model:open="isAddItemModalOpen"
      :budget-id="budgetId"
      @added="handleItemAdded"
    />

    <!-- Send Modal -->
    <UModal v-model:open="isSendModalOpen">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center justify-between">
              <h2 class="text-h1 text-default">
                {{ t('budget.actions.send') }}
              </h2>
              <UButton
                variant="ghost"
                color="neutral"
                icon="i-lucide-x"
                @click="isSendModalOpen = false"
              />
            </div>
          </template>

          <div class="space-y-4">
            <p class="text-muted dark:text-subtle">
              {{ t('budget.send.description') }}
            </p>

            <div class="flex items-center gap-3">
              <UCheckbox
                v-model="sendForm.send_email"
                :label="t('budget.send.sendByEmail')"
              />
            </div>

            <div
              v-if="sendForm.send_email"
              class="space-y-3"
            >
              <p
                v-if="currentBudget?.patient?.email"
                class="text-caption text-subtle"
              >
                {{ t('budget.send.willSendTo') }}: <strong>{{ currentBudget.patient.email }}</strong>
              </p>
              <p
                v-else
                class="text-sm text-warning-accent"
              >
                {{ t('budget.send.noPatientEmail') }}
              </p>

              <UFormField :label="t('budget.send.customMessage')">
                <UTextarea
                  v-model="sendForm.custom_message"
                  :placeholder="t('budget.send.customMessagePlaceholder')"
                  :rows="3"
                />
              </UFormField>
            </div>

            <p
              v-if="!sendForm.send_email"
              class="text-caption text-subtle"
            >
              {{ t('budget.send.manualNote') }}
            </p>
          </div>

          <template #footer>
            <div class="flex justify-end gap-3">
              <UButton
                variant="outline"
                color="neutral"
                @click="isSendModalOpen = false"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                color="primary"
                :disabled="sendForm.send_email && !currentBudget?.patient?.email"
                @click="handleSend"
              >
                {{ sendForm.send_email ? t('budget.send.sendEmail') : t('budget.send.markAsSent') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>

    <!-- Signature Modal -->
    <UModal v-model:open="isSignatureModalOpen">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center justify-between">
              <h2 class="text-h1 text-default">
                {{ signatureAction === 'accept' ? t('budget.actions.accept') : t('budget.actions.reject') }}
              </h2>
              <UButton
                variant="ghost"
                color="neutral"
                icon="i-lucide-x"
                @click="isSignatureModalOpen = false"
              />
            </div>
          </template>

          <form
            class="space-y-4"
            @submit.prevent="handleSignatureSubmit"
          >
            <UFormField
              :label="t('budget.signature.signedBy')"
              required
            >
              <UInput
                v-model="signatureForm.signed_by_name"
                :placeholder="t('budget.signature.signedBy')"
                required
              />
            </UFormField>

            <UFormField :label="t('budget.signature.email')">
              <UInput
                v-model="signatureForm.signed_by_email"
                type="email"
                :placeholder="t('budget.signature.email')"
              />
            </UFormField>

            <UFormField :label="t('budget.signature.relationship')">
              <USelect
                v-model="signatureForm.relationship_to_patient"
                :items="[
                  { label: t('budget.signature.patient'), value: 'patient' },
                  { label: t('budget.signature.guardian'), value: 'guardian' },
                  { label: t('budget.signature.representative'), value: 'representative' }
                ]"
              />
            </UFormField>
          </form>

          <template #footer>
            <div class="flex justify-end gap-3">
              <UButton
                variant="outline"
                color="neutral"
                @click="isSignatureModalOpen = false"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                :color="signatureAction === 'accept' ? 'success' : 'error'"
                :disabled="!signatureForm.signed_by_name"
                @click="handleSignatureSubmit"
              >
                {{ signatureAction === 'accept' ? t('budget.actions.accept') : t('budget.actions.reject') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>

    <!-- View signature modal -->
    <UModal v-model:open="isSignatureViewModalOpen">
      <template #content>
        <div class="p-1">
          <BudgetSignatureCard
            v-if="currentBudget && ['accepted', 'completed'].includes(currentBudget.status)"
            :budget-id="currentBudget.id"
            :budget-status="currentBudget.status"
            :locale="locale"
          />
        </div>
      </template>
    </UModal>

    <!-- Share public link modal -->
    <UModal v-model:open="isShareLinkModalOpen">
      <template #content>
        <div class="p-1">
          <PublicBudgetLinkCard
            v-if="currentBudget?.public_token"
            :token="currentBudget.public_token"
            :status="currentBudget.status"
            :patient-phone="currentBudget.patient?.phone"
            :patient-first-name="currentBudget.patient?.first_name"
            :budget-number="currentBudget.budget_number"
          />
        </div>
      </template>
    </UModal>
  </div>
</template>
