<script setup lang="ts">
/**
 * Treasury page: cash/bank accounts with derived balances, transfers
 * between accounts, and per-account statements. Balances are
 * transfer-derived; payment/expense auto-posting is explicitly Later
 * (see module CLAUDE.md).
 */
import type { TreasuryAccount, TreasuryEntry } from '../../composables/useTreasury'

const { t } = useI18n()
const { listAccounts, createAccount, transfer, statement } = useTreasury()

const accounts = ref<TreasuryAccount[]>([])
const entries = ref<TreasuryEntry[]>([])
const selectedId = ref('')
const isLoading = ref(false)

const showAccountModal = ref(false)
const newName = ref('')
const newKind = ref('cash')

const showTransferModal = ref(false)
const transferFrom = ref('')
const transferTo = ref('')
const transferAmount = ref('')
const transferMemo = ref('')

const selected = computed(() => accounts.value.find(a => a.id === selectedId.value))

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
  await createAccount(newName.value.trim(), newKind.value)
  newName.value = ''
  showAccountModal.value = false
  await refresh()
}

async function doTransfer() {
  if (!transferFrom.value || !transferTo.value || !transferAmount.value) return
  await transfer(transferFrom.value, transferTo.value, transferAmount.value, transferMemo.value || undefined)
  showTransferModal.value = false
  transferMemo.value = ''
  await refresh()
}

onMounted(refresh)
watch(selectedId, async () => {
  if (selectedId.value) entries.value = await statement(selectedId.value)
})
</script>

<template>
  <div class="space-y-4 p-4">
    <div class="flex items-center justify-between">
      <h1 class="text-h2">
        {{ t('treasury.title') }}
      </h1>
      <div class="flex gap-2">
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
              <span class="font-mono">{{ account.balance }}</span>
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
            <span class="truncate">{{ t(`treasury.kind.${entry.kind}`) }}{{ entry.memo ? ' — ' + entry.memo : '' }}</span>
            <span class="font-mono shrink-0">{{ entry.amount }}</span>
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
              :items="accounts.map(a => ({ label: a.name, value: a.id }))"
            />
          </UFormField>
          <UFormField :label="t('treasury.toAccount')">
            <USelectMenu
              v-model="transferTo"
              value-key="value"
              :items="accounts.map(a => ({ label: a.name, value: a.id }))"
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
  </div>
</template>
