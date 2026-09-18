<script setup lang="ts">
/**
 * Treasury page: cash/bank accounts with derived balances, transfers
 * between accounts, and per-account statements. Balances are
 * transfer-derived; payment/expense auto-posting is explicitly Later
 * (see module CLAUDE.md).
 */
import type { TreasuryAccount, TreasuryEntry } from '../../composables/useTreasury'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorDetail } from '~~/app/utils/error'

definePageMeta({ middleware: ['auth'] })

const { t, locale } = useI18n()
const { can } = usePermissions()
const { listAccounts, createAccount, transfer, statement, correct } = useTreasury()
const { currentClinic } = useClinic()
const toast = useToast()

const canWrite = computed(() => can(PERMISSIONS.treasury.write))

if (!can(PERMISSIONS.treasury.read)) await navigateTo('/')

const accounts = ref<TreasuryAccount[]>([])
const entries = ref<TreasuryEntry[]>([])
const selectedId = ref<string | null>(null)
const isLoading = ref(false)

const showAccountModal = ref(false)
const newName = ref('')
const newKind = ref('cash')

const showTransferModal = ref(false)
const transferFrom = ref<string | undefined>(undefined)
const transferTo = ref<string | undefined>(undefined)
const transferAmount = ref('')
const transferMemo = ref('')

const showCorrectModal = ref(false)
const correctAmount = ref('')
const correctDirection = ref<'in' | 'out'>('in')
const correctMemo = ref('')

const selected = computed(() => accounts.value.find(a => a.id === selectedId.value))
const activeAccounts = computed(() => accounts.value.filter(a => a.is_active))

function formatMoney(value: string | number): string {
  const currency = currentClinic.value?.currency || 'EUR'
  try {
    return new Intl.NumberFormat(locale.value, { style: 'currency', currency }).format(Number(value))
  } catch {
    return String(value)
  }
}

function fail(e: unknown) {
  const description = errorDetail(e) ?? String(e)
  toast.add({ title: t('treasury.title'), description, color: 'error' })
}

// Spanish keyboards type 25,50 — the API only accepts 25.50.
function normAmount(raw: string): string {
  return raw.replace(',', '.')
}

function formatDate(iso: string): string {
  const tz = currentClinic.value?.timezone
  try {
    return new Intl.DateTimeFormat(locale.value, {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      ...(tz ? { timeZone: tz } : {})
    }).format(new Date(iso))
  } catch {
    return new Date(iso).toLocaleString()
  }
}

function isOut(kind: string): boolean {
  return kind.endsWith('_out')
}

async function refresh() {
  isLoading.value = true
  try {
    accounts.value = await listAccounts()
    if (!selectedId.value && accounts.value.length > 0) selectedId.value = accounts.value[0]!.id
    if (selectedId.value) entries.value = await statement(selectedId.value)
  } finally {
    isLoading.value = false
  }
}

async function create() {
  if (!newName.value.trim()) return
  try {
    await createAccount(newName.value.trim(), newKind.value)
    newName.value = ''
    showAccountModal.value = false
    await refresh()
  } catch (e: unknown) { fail(e) }
}

async function doTransfer() {
  if (!transferFrom.value || !transferTo.value || !transferAmount.value) return
  try {
    await transfer(transferFrom.value, transferTo.value, normAmount(transferAmount.value), transferMemo.value || undefined)
    showTransferModal.value = false
    transferMemo.value = ''
    await refresh()
  } catch (e: unknown) { fail(e) }
}

async function doCorrect() {
  if (!selectedId.value || !correctAmount.value || !correctMemo.value.trim()) return
  try {
    await correct(selectedId.value, normAmount(correctAmount.value), correctDirection.value, correctMemo.value.trim())
    showCorrectModal.value = false
    correctAmount.value = ''
    correctMemo.value = ''
    await refresh()
  } catch (e: unknown) { fail(e) }
}

onMounted(refresh)
watch(selectedId, async () => {
  if (selectedId.value) entries.value = await statement(selectedId.value)
})
</script>

<template>
  <div
    v-if="can(PERMISSIONS.treasury.read)"
    class="space-y-4 p-4"
  >
    <div class="flex items-center justify-between">
      <h1 class="text-h2">
        {{ t('treasury.title') }}
      </h1>
      <div
        v-if="canWrite"
        class="flex gap-2"
      >
        <UButton
          color="neutral"
          variant="outline"
          icon="i-lucide-plus"
          @click="showAccountModal = true"
        >
          {{ t('treasury.newAccount') }}
        </UButton>
        <UButton
          icon="i-lucide-arrow-left-right"
          :disabled="accounts.length < 2"
          @click="showTransferModal = true"
        >
          {{ t('treasury.transfer') }}
        </UButton>
        <UButton
          color="neutral"
          variant="outline"
          icon="i-lucide-pencil"
          :disabled="!selectedId"
          @click="showCorrectModal = true"
        >
          {{ t('treasury.correct') }}
        </UButton>
      </div>
    </div>

    <div class="grid gap-4 md:grid-cols-3">
      <UCard>
        <template #header>
          {{ t('treasury.accounts') }}
        </template>
        <USkeleton
          v-if="isLoading"
          class="h-24"
        />
        <p
          v-else-if="accounts.length === 0"
          class="text-sm text-muted"
        >
          {{ t('treasury.noAccounts') }}
        </p>
        <ul
          v-else
          class="space-y-1 text-sm"
        >
          <li
            v-for="account in accounts"
            :key="account.id"
          >
            <button
              type="button"
              class="w-full flex justify-between rounded px-2 py-1 hover:bg-surface"
              :class="{ 'bg-surface': account.id === selectedId }"
              @click="selectedId = account.id"
            >
              <span>{{ account.name }}</span>
              <span
                class="font-mono"
                :class="{ 'text-error': Number(account.balance) < 0 }"
              >{{ formatMoney(account.balance) }}</span>
            </button>
          </li>
        </ul>
      </UCard>

      <UCard class="md:col-span-2">
        <template #header>
          {{ selected ? selected.name : t('treasury.statement') }}
        </template>
        <USkeleton
          v-if="isLoading"
          class="h-24"
        />
        <p
          v-else-if="entries.length === 0"
          class="text-sm text-muted"
        >
          {{ t('treasury.noEntries') }}
        </p>
        <ul
          v-else
          class="space-y-1 text-sm"
        >
          <li
            v-for="entry in entries"
            :key="entry.id"
            class="flex justify-between gap-2"
          >
            <span class="truncate">{{ formatDate(entry.at) }} · {{ t(`treasury.kind.${entry.kind}`) }}{{ entry.memo ? ' — ' + entry.memo : '' }}</span>
            <span
              class="font-mono shrink-0"
              :class="{ 'text-error': isOut(entry.kind) }"
            >{{ isOut(entry.kind) ? '−' : '' }}{{ formatMoney(entry.amount) }}</span>
          </li>
        </ul>
      </UCard>
    </div>

    <UModal
      v-model:open="showAccountModal"
      :title="t('treasury.newAccount')"
    >
      <template #body>
        <div class="space-y-3 p-4">
          <UFormField :label="t('treasury.accountName')">
            <UInput v-model="newName" />
          </UFormField>
          <UFormField :label="t('treasury.accountKind')">
            <USelectMenu
              v-model="newKind"
              value-key="value"
              :items="[
                { label: t('treasury.kindCash'), value: 'cash' },
                { label: t('treasury.kindBank'), value: 'bank' }
              ]"
            />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2 p-2">
          <UButton
            color="neutral"
            variant="ghost"
            @click="showAccountModal = false"
          >
            {{ t('common.close') }}
          </UButton>
          <UButton @click="create">
            {{ t('treasury.create') }}
          </UButton>
        </div>
      </template>
    </UModal>

    <UModal
      v-model:open="showTransferModal"
      :title="t('treasury.transfer')"
    >
      <template #body>
        <div class="space-y-3 p-4">
          <UFormField :label="t('treasury.fromAccount')">
            <USelectMenu
              v-model="transferFrom"
              value-key="value"
              :items="activeAccounts.map(a => ({ label: a.name, value: a.id }))"
            />
          </UFormField>
          <UFormField :label="t('treasury.toAccount')">
            <USelectMenu
              v-model="transferTo"
              value-key="value"
              :items="activeAccounts.map(a => ({ label: a.name, value: a.id }))"
            />
          </UFormField>
          <UFormField :label="t('treasury.amount')">
            <UInput
              v-model="transferAmount"
              inputmode="decimal"
            />
          </UFormField>
          <UFormField :label="t('treasury.memo')">
            <UInput v-model="transferMemo" />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2 p-2">
          <UButton
            color="neutral"
            variant="ghost"
            @click="showTransferModal = false"
          >
            {{ t('common.close') }}
          </UButton>
          <UButton @click="doTransfer">
            {{ t('treasury.transfer') }}
          </UButton>
        </div>
      </template>
    </UModal>

    <UModal
      v-model:open="showCorrectModal"
      :title="t('treasury.correct')"
    >
      <template #body>
        <div class="space-y-3 p-4">
          <UFormField :label="t('treasury.correctionDirection')">
            <USelectMenu
              v-model="correctDirection"
              value-key="value"
              :items="[
                { label: t('treasury.kind.correction_in'), value: 'in' },
                { label: t('treasury.kind.correction_out'), value: 'out' }
              ]"
            />
          </UFormField>
          <UFormField :label="t('treasury.amount')">
            <UInput
              v-model="correctAmount"
              inputmode="decimal"
            />
          </UFormField>
          <UFormField :label="t('treasury.memo')">
            <UInput v-model="correctMemo" />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2 p-2">
          <UButton
            color="neutral"
            variant="ghost"
            @click="showCorrectModal = false"
          >
            {{ t('common.close') }}
          </UButton>
          <UButton @click="doCorrect">
            {{ t('treasury.correct') }}
          </UButton>
        </div>
      </template>
    </UModal>
  </div>
</template>
