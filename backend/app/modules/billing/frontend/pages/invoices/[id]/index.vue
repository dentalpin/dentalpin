<script setup lang="ts">
import { INVOICE_STATUS_ROLE } from '~~/app/config/severity'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'
import type { EntityChip } from '~~/app/components/shared/EntityStatusChips.vue'
import type { EntityAction } from '~~/app/components/shared/EntityActionBar.vue'
import type { TotalLine } from '~~/app/components/shared/EntityTotalsCard.vue'
import type { InfoItem } from '~~/app/components/shared/EntityInfoCard.vue'

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const { currentClinic } = useClinic()
const {
  currentInvoice,
  isLoading,
  fetchInvoice,
  issueInvoice,
  voidInvoice,
  sendInvoice,
  createCreditNote,
  downloadPDF,
  canEdit,
  canIssue,
  canRecordPayment,
  canVoid,
  canCreateCreditNote,
  canSend,
  getPaymentMethodLabel,
  formatCurrency
} = useInvoices()

// Context object passed to compliance-module slot entries (e.g.
// Verifactu-ES). Billing remains country-agnostic; the slot registry
// resolves which component to render per clinic country.
const complianceSlotCtx = computed(() => ({
  invoice: currentInvoice.value,
  clinic: currentClinic.value
}))

const invoiceId = computed(() => route.params.id as string)
const comesFromPatient = computed(() => route.query.from === 'patient' && route.query.patientId)
const backLabel = computed(() => comesFromPatient.value ? t('actions.back') : t('invoice.title'))

// Modal states
const showPaymentModal = ref(false)
const showCreditNoteModal = ref(false)
const showSendModal = ref(false)
const showIssueConfirm = ref(false)
const isProcessing = ref(false)
const isDownloadingPdf = ref(false)
const isSending = ref(false)

// Credit note form
const creditNoteForm = ref({
  reason: '',
  items: [] as { invoice_item_id: string, quantity?: number }[]
})

// Send form
const sendForm = ref({
  send_email: true,
  custom_message: ''
})

// Load invoice
onMounted(async () => {
  await fetchInvoice(invoiceId.value)
})

// Format date
function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString(locale.value)
}

// Days overdue (positive when due_date is past). Only meaningful for
// invoices still chasing payment — drafts/paid/voided return null.
const daysOverdue = computed<number | null>(() => {
  const inv = currentInvoice.value
  if (!inv?.due_date) return null
  if (!['issued', 'partial'].includes(inv.status)) return null
  const due = new Date(inv.due_date)
  const now = new Date()
  const diff = Math.floor((now.getTime() - due.getTime()) / (1000 * 60 * 60 * 24))
  return diff > 0 ? diff : null
})

const isOverdue = computed<boolean>(() => daysOverdue.value !== null)

// Check if billing data is incomplete (for drafts, check patient billing info)
const hasBillingDataIncomplete = computed(() => {
  if (!currentInvoice.value) return false
  if (currentInvoice.value.status !== 'draft') return false
  // For drafts, billing comes from patient - check patient's billing completeness
  return currentInvoice.value.patient?.has_complete_billing_info === false
})

// AEAT/compliance rejection summary — picks the worst severity across
// all country-keyed compliance entries. Used to surface a critical
// banner when the invoice was rejected.
const complianceRejection = computed<{ message?: string } | null>(() => {
  const cd = currentInvoice.value?.compliance_data
  if (!cd) return null
  for (const country of Object.keys(cd)) {
    const entry = cd[country] as Record<string, unknown> | undefined
    if (!entry) continue
    const severity = entry.severity as string | undefined
    if (severity === 'error') {
      return { message: (entry.error_message as string | undefined) ?? undefined }
    }
  }
  return null
})

// Actions
function requestIssue() {
  if (!currentInvoice.value) return

  // Check billing data is complete before issuing
  if (hasBillingDataIncomplete.value) {
    toast.add({
      title: t('common.error'),
      description: t('invoice.errors.billingIncomplete'),
      color: 'error'
    })
    return
  }

  showIssueConfirm.value = true
}

async function handleIssue() {
  if (!currentInvoice.value) return

  isProcessing.value = true
  try {
    await issueInvoice(invoiceId.value)
    toast.add({
      title: t('common.success'),
      description: t('invoice.messages.issued'),
      color: 'success'
    })
    showIssueConfirm.value = false
    await fetchInvoice(invoiceId.value)
  } catch (e: unknown) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('invoice.errors.issue')),
      color: 'error'
    })
  } finally {
    isProcessing.value = false
  }
}

async function handleVoid() {
  if (!currentInvoice.value) return
  if (!confirm(t('invoice.confirmations.void'))) return

  isProcessing.value = true
  try {
    await voidInvoice(invoiceId.value)
    toast.add({
      title: t('common.success'),
      description: t('invoice.messages.voided'),
      color: 'success'
    })
    await fetchInvoice(invoiceId.value)
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('invoice.errors.void')),
      color: 'error'
    })
  } finally {
    isProcessing.value = false
  }
}

function openPaymentModal() {
  if (!currentInvoice.value) return
  showPaymentModal.value = true
}

// Voiding a payment was removed from this screen — refunds happen
// in the payments module (POST /api/v1/payments/{id}/refunds).
// Admins refund from /payments.

function openCreditNoteModal() {
  creditNoteForm.value = {
    reason: '',
    items: []
  }
  showCreditNoteModal.value = true
}

async function handleCreateCreditNote() {
  if (!currentInvoice.value) return
  if (!creditNoteForm.value.reason) {
    toast.add({
      title: t('common.error'),
      description: t('invoice.errors.creditNoteReasonRequired'),
      color: 'error'
    })
    return
  }

  isProcessing.value = true
  try {
    const creditNote = await createCreditNote(invoiceId.value, {
      reason: creditNoteForm.value.reason,
      items: creditNoteForm.value.items.length > 0 ? creditNoteForm.value.items : undefined
    })
    toast.add({
      title: t('common.success'),
      description: t('invoice.messages.creditNoteCreated'),
      color: 'success'
    })
    showCreditNoteModal.value = false
    // Navigate to the new credit note
    router.push(`/invoices/${creditNote.id}`)
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('invoice.errors.createCreditNote')),
      color: 'error'
    })
  } finally {
    isProcessing.value = false
  }
}

function openSendModal() {
  sendForm.value = {
    send_email: true,
    custom_message: ''
  }
  showSendModal.value = true
}

async function handleSend() {
  if (!currentInvoice.value) return

  isSending.value = true
  try {
    await sendInvoice(invoiceId.value, {
      send_email: sendForm.value.send_email,
      custom_message: sendForm.value.custom_message || undefined
    })

    const message = sendForm.value.send_email
      ? t('invoice.messages.sentByEmail')
      : t('invoice.messages.sentManually')

    toast.add({
      title: t('common.success'),
      description: message,
      color: 'success'
    })
    showSendModal.value = false
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('invoice.errors.send')),
      color: 'error'
    })
  } finally {
    isSending.value = false
  }
}

async function handleDownloadPDF() {
  if (!currentInvoice.value) return

  isDownloadingPdf.value = true
  try {
    await downloadPDF(invoiceId.value, locale.value)
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('invoice.pdf.downloadError')),
      color: 'error'
    })
  } finally {
    isDownloadingPdf.value = false
  }
}

function goBack() {
  if (comesFromPatient.value) {
    router.push(`/patients/${route.query.patientId}`)
  } else {
    router.push('/invoices')
  }
}

function scrollToCompliancePanel() {
  const el = document.getElementById('invoice-compliance-panel')
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

const statusChips = computed<EntityChip[]>(() => {
  const inv = currentInvoice.value
  if (!inv) return []
  const chips: EntityChip[] = [
    {
      key: 'status',
      role: INVOICE_STATUS_ROLE[inv.status] ?? 'neutral',
      label: t(`invoice.status.${inv.status}`)
    }
  ]
  if (daysOverdue.value !== null) {
    chips.push({
      key: 'overdue',
      role: 'danger',
      label: t('invoice.overdueDays', { n: daysOverdue.value }),
      icon: 'i-lucide-alarm-clock'
    })
  }
  return chips
})

const primaryActions = computed<EntityAction[]>(() => {
  const inv = currentInvoice.value
  if (!inv) return []
  const actions: EntityAction[] = []

  if (canRecordPayment(inv) && can(PERMISSIONS.billing.write)) {
    actions.push({
      key: 'recordPayment',
      label: t('invoice.actions.recordPayment'),
      icon: 'i-lucide-credit-card',
      color: 'success',
      onClick: openPaymentModal
    })
  }

  if (canIssue(inv) && can(PERMISSIONS.billing.write)) {
    actions.push({
      key: 'issue',
      label: t('invoice.actions.issue'),
      icon: 'i-lucide-send',
      color: 'primary',
      onClick: requestIssue
    })
  }

  if (canSend(inv) && can(PERMISSIONS.billing.write)) {
    actions.push({
      key: 'sendEmail',
      label: t('invoice.actions.sendEmail'),
      icon: 'i-lucide-mail',
      variant: 'soft',
      onClick: openSendModal
    })
  }

  if (canEdit(inv) && can(PERMISSIONS.billing.write)) {
    actions.push({
      key: 'edit',
      label: t('common.edit'),
      icon: 'i-lucide-pencil',
      variant: 'soft',
      onClick: goToEdit
    })
  }

  return actions
})

const overflowActions = computed<EntityAction[]>(() => {
  const inv = currentInvoice.value
  if (!inv) return []
  const actions: EntityAction[] = []

  if (inv.status !== 'draft' && can(PERMISSIONS.billing.read)) {
    actions.push({
      key: 'downloadPdf',
      label: t('invoice.actions.downloadPdf'),
      icon: 'i-lucide-download',
      loading: isDownloadingPdf.value,
      onClick: handleDownloadPDF
    })
  }

  if (canCreateCreditNote(inv) && can(PERMISSIONS.billing.write)) {
    actions.push({
      key: 'createCreditNote',
      label: t('invoice.actions.createCreditNote'),
      icon: 'i-lucide-file-minus',
      onClick: openCreditNoteModal
    })
  }

  if (canVoid(inv) && can(PERMISSIONS.billing.admin)) {
    actions.push({
      key: 'void',
      label: t('invoice.actions.void'),
      icon: 'i-lucide-ban',
      destructive: true,
      onClick: handleVoid
    })
  }

  return actions
})

const totalsLines = computed<TotalLine[]>(() => {
  const inv = currentInvoice.value
  if (!inv) return []
  const lines: TotalLine[] = [
    { key: 'subtotal', label: t('invoice.subtotal'), value: inv.subtotal }
  ]
  if (inv.total_discount > 0) {
    lines.push({
      key: 'discount',
      label: t('invoice.discount'),
      value: inv.total_discount,
      sign: '-',
      role: 'success'
    })
  }
  if (inv.total_tax > 0) {
    lines.push({
      key: 'tax',
      label: t('invoice.tax'),
      value: inv.total_tax
    })
  }
  lines.push({
    key: 'total',
    label: t('invoice.total'),
    value: inv.total,
    emphasis: 'strong',
    divider: 'above'
  })
  if (inv.status !== 'draft') {
    lines.push({
      key: 'paid',
      label: t('invoice.paid'),
      value: inv.total_paid,
      role: 'success'
    })
    if (inv.balance_due > 0) {
      lines.push({
        key: 'pending',
        label: t('invoice.balanceDue'),
        value: inv.balance_due,
        role: 'warning',
        divider: 'above'
      })
    }
  }
  return lines
})

const infoItems = computed<InfoItem[]>(() => {
  const inv = currentInvoice.value
  if (!inv) return []
  const items: InfoItem[] = []
  if (inv.issue_date) {
    items.push({ key: 'issueDate', label: t('invoice.info.issueDate'), value: formatDate(inv.issue_date) })
  }
  if (inv.due_date) {
    items.push({ key: 'dueDate', label: t('invoice.info.dueDate'), value: formatDate(inv.due_date) })
  }
  if (inv.issuer) {
    items.push({
      key: 'issuedBy',
      label: t('invoice.info.issuedBy'),
      value: `${inv.issuer.first_name} ${inv.issuer.last_name}`
    })
  } else if (inv.creator) {
    items.push({
      key: 'createdBy',
      label: t('invoice.info.createdBy'),
      value: `${inv.creator.first_name} ${inv.creator.last_name}`
    })
  }
  if (inv.budget) {
    items.push({
      key: 'budget',
      label: t('invoice.info.budget'),
      link: { to: `/budgets/${inv.budget.id}`, label: inv.budget.budget_number }
    })
  }
  if (inv.credit_note_for) {
    items.push({
      key: 'creditNoteFor',
      label: t('invoice.info.creditNoteFor'),
      link: {
        to: `/invoices/${inv.credit_note_for.id}`,
        label: inv.credit_note_for.invoice_number ?? t('invoice.draftNoNumber')
      }
    })
  }
  return items
})

function goToEdit() {
  router.push(`/invoices/${invoiceId.value}/edit`)
}

function goToBudget() {
  if (currentInvoice.value?.budget_id) {
    router.push(`/budgets/${currentInvoice.value.budget_id}`)
  }
}

function goToCreditNoteFor() {
  if (currentInvoice.value?.credit_note_for_id) {
    router.push(`/invoices/${currentInvoice.value.credit_note_for_id}`)
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Loading state -->
    <div
      v-if="isLoading && !currentInvoice"
      class="space-y-4"
    >
      <USkeleton class="h-8 w-48" />
      <USkeleton class="h-64 w-full" />
    </div>

    <!-- Invoice not found -->
    <div
      v-else-if="!currentInvoice"
      class="text-center py-12"
    >
      <UIcon
        name="i-lucide-file-x"
        class="w-12 h-12 text-subtle mx-auto mb-4"
      />
      <h3 class="text-h2 text-default mb-2">
        {{ t('invoice.notFound') }}
      </h3>
      <UButton @click="goBack">
        {{ backLabel }}
      </UButton>
    </div>

    <!-- Invoice content -->
    <template v-else>
      <!-- Header -->
      <DetailPageHeader
        :title="currentInvoice.invoice_number || t('invoice.draftNoNumber')"
        :back-to="{
          to: comesFromPatient ? `/patients/${route.query.patientId}` : '/invoices',
          label: backLabel
        }"
      >
        <template #status>
          <div class="flex flex-wrap items-center gap-1.5">
            <EntityStatusChips :chips="statusChips" />
            <!--
              Compliance modules surface AEAT/factur-x/etc. badges here.
              Renders nothing when there is no compliance data for the
              active country.
            -->
            <ModuleSlot
              name="invoice.detail.header.meta"
              :ctx="complianceSlotCtx"
            />
          </div>
        </template>
        <template #subtitle>
          <NuxtLink
            v-if="currentInvoice.patient"
            :to="`/patients/${currentInvoice.patient.id}`"
            class="inline-block text-body text-primary-accent hover:text-primary-700 dark:text-primary-400 dark:hover:text-primary-300 hover:underline"
          >
            {{ currentInvoice.patient.first_name }} {{ currentInvoice.patient.last_name }}
          </NuxtLink>
        </template>
        <template #actions>
          <EntityActionBar
            :primary="primaryActions"
            :overflow="overflowActions"
          />
        </template>
      </DetailPageHeader>

      <!-- Critical banner — AEAT rejection (or future compliance failures).
           The header badge keeps the at-a-glance signal; this banner makes
           the next action ("Corregir y reenviar") impossible to miss. -->
      <EntityCriticalBanner
        v-if="complianceRejection"
        role="danger"
        :title="t('invoice.criticalBanner.aeatRejected.title')"
        :description="complianceRejection.message"
        :cta="{
          label: t('invoice.criticalBanner.aeatRejected.cta'),
          icon: 'i-lucide-pencil',
          onClick: scrollToCompliancePanel
        }"
      />

      <!-- Main content grid -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Left column - Invoice details -->
        <div class="lg:col-span-2 space-y-6">
          <!-- Invoice info card -->
          <UCard>
            <template #header>
              <h3 class="font-semibold text-default">
                {{ t('invoice.details') }}
              </h3>
            </template>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <dt class="text-caption text-subtle">
                  {{ t('invoice.issueDate') }}
                </dt>
                <dd class="font-medium text-default">
                  {{ formatDate(currentInvoice.issue_date) }}
                </dd>
              </div>
              <div>
                <dt class="text-caption text-subtle">
                  {{ t('invoice.dueDate') }}
                </dt>
                <dd
                  class="font-medium"
                  :class="isOverdue ? 'text-danger-accent' : 'text-default'"
                >
                  {{ formatDate(currentInvoice.due_date) }}
                </dd>
              </div>
              <!-- Billing data incomplete warning -->
              <div
                v-if="hasBillingDataIncomplete"
                class="col-span-2 flex items-center gap-2 px-3 py-2 alert-surface-warning rounded-token-md"
              >
                <UIcon
                  name="i-lucide-alert-triangle"
                  class="w-5 h-5 flex-shrink-0"
                />
                <div class="flex-1">
                  <p class="font-medium">
                    {{ t('invoice.billingDataIncomplete') }}
                  </p>
                  <p class="text-sm text-warning-accent">
                    {{ t('invoice.billingDataIncompleteHint') }}
                  </p>
                </div>
                <UButton
                  size="sm"
                  variant="outline"
                  color="warning"
                  @click="router.push(`/patients/${currentInvoice.patient?.id}`)"
                >
                  {{ t('invoice.editPatientBilling') }}
                </UButton>
              </div>

              <div>
                <dt class="text-caption text-subtle">
                  {{ t('invoice.billingName') }}
                </dt>
                <dd class="font-medium text-default">
                  {{ currentInvoice.billing_name || '-' }}
                </dd>
              </div>
              <div v-if="currentInvoice.billing_tax_id">
                <dt class="text-caption text-subtle">
                  {{ t('invoice.taxId') }}
                </dt>
                <dd class="font-medium text-default">
                  {{ currentInvoice.billing_tax_id }}
                </dd>
              </div>
              <div v-if="currentInvoice.budget">
                <dt class="text-caption text-subtle">
                  {{ t('invoice.linkedBudget') }}
                </dt>
                <dd>
                  <UButton
                    variant="link"
                    size="sm"
                    class="p-0"
                    @click="goToBudget"
                  >
                    {{ currentInvoice.budget.budget_number }}
                  </UButton>
                </dd>
              </div>
              <div v-if="currentInvoice.credit_note_for">
                <dt class="text-caption text-subtle">
                  {{ t('invoice.creditNoteFor') }}
                </dt>
                <dd>
                  <UButton
                    variant="link"
                    size="sm"
                    class="p-0"
                    @click="goToCreditNoteFor"
                  >
                    {{ currentInvoice.credit_note_for.invoice_number || t('invoice.draftNoNumber') }}
                  </UButton>
                </dd>
              </div>
            </div>
          </UCard>

          <!-- Items card -->
          <UCard>
            <template #header>
              <h3 class="font-semibold text-default">
                {{ t('invoice.items') }}
              </h3>
            </template>

            <div class="divide-y divide-[var(--color-border-subtle)]">
              <div
                v-for="item in currentInvoice.items"
                :key="item.id"
                class="py-3 first:pt-0 last:pb-0"
              >
                <div class="flex justify-between items-start gap-4">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span class="font-medium text-default">{{ item.description }}</span>
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
                    <p
                      v-if="item.internal_code"
                      class="text-caption text-subtle mt-1"
                    >
                      {{ item.internal_code }}
                    </p>
                  </div>
                  <div class="text-right">
                    <p class="text-caption text-subtle">
                      {{ item.quantity }} x {{ formatCurrency(item.unit_price) }}
                    </p>
                    <p
                      v-if="item.line_discount > 0"
                      class="text-sm text-success-accent"
                    >
                      -{{ formatCurrency(item.line_discount) }}
                    </p>
                    <p class="font-semibold text-default">
                      {{ formatCurrency(item.line_total) }}
                    </p>
                    <p class="text-xs text-subtle">
                      {{ t('invoice.vat') }} {{ item.vat_rate }}%
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </UCard>

          <!-- Payments card. The link rows live in billing's
               ``invoice_payments`` table; the underlying Payment is in
               the payments module. Refunds happen via
               /api/v1/payments/{id}/refunds — not from this screen. -->
          <UCard v-if="currentInvoice.invoice_payments && currentInvoice.invoice_payments.length > 0">
            <template #header>
              <h3 class="font-semibold text-default">
                {{ t('invoice.payments.title') }}
              </h3>
            </template>

            <div class="divide-y divide-[var(--color-border-subtle)]">
              <div
                v-for="ip in currentInvoice.invoice_payments"
                :key="ip.id"
                class="py-3 first:pt-0 last:pb-0 flex items-center justify-between"
              >
                <div>
                  <p class="font-medium text-default">
                    {{ formatCurrency(ip.amount) }}
                  </p>
                  <p class="text-caption text-subtle">
                    {{ formatDate(ip.created_at) }}
                  </p>
                </div>
              </div>
            </div>
          </UCard>
        </div>

        <!-- Right column - Summary.
             Order on desktop (lg ≥1024px) is the document order:
             Totals → Info → Notes → Compliance.
             On mobile the most operative question is "is it paid?",
             so we want the compliance / totals block at the top — the
             outer grid already places the sidebar below main on mobile,
             but inside the sidebar we keep "money first". -->
        <div class="space-y-6">
          <EntityTotalsCard
            :title="t('invoice.summary')"
            :lines="totalsLines"
          />

          <EntityInfoCard
            v-if="infoItems.length"
            :items="infoItems"
          />

          <!-- Notes card -->
          <UCard v-if="currentInvoice.public_notes || currentInvoice.internal_notes">
            <template #header>
              <h3 class="font-semibold text-default">
                {{ t('invoice.notes') }}
              </h3>
            </template>

            <div class="space-y-4">
              <div v-if="currentInvoice.public_notes">
                <dt class="text-caption text-subtle mb-1">
                  {{ t('invoice.publicNotes') }}
                </dt>
                <dd class="text-default whitespace-pre-wrap">
                  {{ currentInvoice.public_notes }}
                </dd>
              </div>
              <div v-if="currentInvoice.internal_notes">
                <dt class="text-caption text-subtle mb-1">
                  {{ t('invoice.internalNotes') }}
                </dt>
                <dd class="text-default whitespace-pre-wrap">
                  {{ currentInvoice.internal_notes }}
                </dd>
              </div>
            </div>
          </UCard>

          <!--
            Compliance modules (Verifactu-ES, factur-x-FR, ...) plug
            into this slot via `useModuleSlots`. Billing has no compile-
            time dependency on any of them. The anchor id is used by
            the EntityCriticalBanner CTA above to scroll the user
            directly to the correction panel.
          -->
          <div id="invoice-compliance-panel">
            <ModuleSlot
              name="invoice.detail.compliance"
              :ctx="complianceSlotCtx"
            />
          </div>
        </div>
      </div>
    </template>

    <!-- Issue confirmation modal -->
    <UModal
      v-model:open="showIssueConfirm"
      :title="t('invoice.actions.issue')"
    >
      <template #body>
        <div class="p-4">
          <div class="flex items-start gap-3">
            <div class="shrink-0 w-10 h-10 rounded-full alert-surface-warning flex items-center justify-center">
              <UIcon
                name="i-lucide-send"
                class="w-5 h-5"
              />
            </div>
            <div class="flex-1 space-y-2">
              <p class="text-default font-medium">
                {{ t('invoice.confirmations.issue') }}
              </p>
              <p class="text-caption text-subtle">
                {{ t('invoice.confirmations.issueDescription') }}
              </p>
            </div>
          </div>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <UButton
            variant="ghost"
            color="neutral"
            :disabled="isProcessing"
            @click="showIssueConfirm = false"
          >
            {{ t('common.cancel') }}
          </UButton>
          <UButton
            color="primary"
            icon="i-lucide-send"
            :loading="isProcessing"
            @click="handleIssue"
          >
            {{ t('invoice.actions.issue') }}
          </UButton>
        </div>
      </template>
    </UModal>

    <!-- Payment Modal — shared CollectAmountModal UX, identical to BudgetCollectModal. -->
    <InvoiceCollectModal
      v-if="currentInvoice"
      v-model:open="showPaymentModal"
      :invoice-id="invoiceId"
      :invoice-number="currentInvoice.invoice_number"
      :patient-name="currentInvoice.patient
        ? `${currentInvoice.patient.first_name} ${currentInvoice.patient.last_name}`
        : undefined"
      :balance-due="currentInvoice.balance_due"
      :total="currentInvoice.total"
      @recorded="fetchInvoice(invoiceId)"
    />

    <!-- Credit Note Modal -->
    <UModal
      v-model:open="showCreditNoteModal"
      :title="t('invoice.createCreditNote')"
    >
      <template #body>
        <div class="space-y-4 p-4">
          <UFormField :label="t('invoice.creditNoteReason')">
            <UTextarea
              v-model="creditNoteForm.reason"
              :rows="3"
              :placeholder="t('invoice.creditNoteReasonPlaceholder')"
            />
          </UFormField>

          <p class="text-caption text-subtle">
            {{ t('invoice.creditNoteInfo') }}
          </p>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <UButton
            variant="ghost"
            color="neutral"
            @click="showCreditNoteModal = false"
          >
            {{ t('common.cancel') }}
          </UButton>
          <UButton
            color="warning"
            :loading="isProcessing"
            @click="handleCreateCreditNote"
          >
            {{ t('invoice.actions.createCreditNote') }}
          </UButton>
        </div>
      </template>
    </UModal>

    <!-- Send Invoice Modal -->
    <UModal
      v-model:open="showSendModal"
      :title="t('invoice.send.title')"
    >
      <template #body>
        <div class="space-y-4 p-4">
          <p class="text-muted dark:text-subtle">
            {{ t('invoice.send.description') }}
          </p>

          <div class="flex items-center gap-3">
            <UCheckbox
              v-model="sendForm.send_email"
              :label="t('invoice.send.sendByEmail')"
            />
          </div>

          <div
            v-if="sendForm.send_email"
            class="space-y-3"
          >
            <p
              v-if="currentInvoice?.patient?.email"
              class="text-caption text-subtle"
            >
              {{ t('invoice.send.willSendTo') }}: <strong>{{ currentInvoice.patient.email }}</strong>
            </p>
            <p
              v-else
              class="text-sm text-warning-accent"
            >
              {{ t('invoice.send.noPatientEmail') }}
            </p>

            <UFormField :label="t('invoice.send.customMessage')">
              <UTextarea
                v-model="sendForm.custom_message"
                :placeholder="t('invoice.send.customMessagePlaceholder')"
                :rows="3"
              />
            </UFormField>
          </div>

          <p
            v-if="!sendForm.send_email"
            class="text-caption text-subtle"
          >
            {{ t('invoice.send.manualNote') }}
          </p>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <UButton
            variant="ghost"
            color="neutral"
            @click="showSendModal = false"
          >
            {{ t('common.cancel') }}
          </UButton>
          <UButton
            color="primary"
            :loading="isSending"
            :disabled="sendForm.send_email && !currentInvoice?.patient?.email"
            @click="handleSend"
          >
            {{ sendForm.send_email ? t('invoice.send.sendEmail') : t('invoice.send.markAsSent') }}
          </UButton>
        </div>
      </template>
    </UModal>
  </div>
</template>
