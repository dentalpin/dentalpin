import type { ApiResponse } from '~~/app/types'

export interface TreasuryAccount {
  id: string
  name: string
  kind: string
  opening_balance: string
  is_active: boolean
  balance: string
}

export interface TreasuryEntry {
  id: string
  account_id: string
  group_id: string
  kind: string
  amount: string
  at: string
  memo: string | null
}

export function useTreasury() {
  const api = useApi()

  async function listAccounts(): Promise<TreasuryAccount[]> {
    const response = await api.get<ApiResponse<TreasuryAccount[]>>('/api/v1/treasury/accounts')
    return response.data
  }

  async function createAccount(name: string, kind: string, opening?: string): Promise<TreasuryAccount> {
    const response = await api.post<ApiResponse<TreasuryAccount>>(
      '/api/v1/treasury/accounts',
      opening ? { name, kind, opening_balance: opening } : { name, kind },
      // The page surfaces failures itself — keep useApi's toast off.
      { errorToast: false }
    )
    return response.data
  }

  async function updateAccount(id: string, isActive: boolean): Promise<TreasuryAccount> {
    const response = await api.patch<ApiResponse<TreasuryAccount>>(
      `/api/v1/treasury/accounts/${id}`,
      { is_active: isActive },
      { errorToast: false }
    )
    return response.data
  }

  async function transfer(fromId: string, toId: string, amount: string, memo?: string): Promise<TreasuryEntry[]> {
    const response = await api.post<ApiResponse<TreasuryEntry[]>>(
      '/api/v1/treasury/transfers',
      { from_account_id: fromId, to_account_id: toId, amount, memo: memo || null },
      { errorToast: false }
    )
    return response.data
  }

  async function statement(accountId: string): Promise<TreasuryEntry[]> {
    const response = await api.get<ApiResponse<TreasuryEntry[]>>(
      `/api/v1/treasury/accounts/${accountId}/entries`
    )
    return response.data
  }

  async function correct(
    accountId: string, amount: string, direction: 'in' | 'out', memo: string
  ): Promise<TreasuryEntry> {
    const response = await api.post<ApiResponse<TreasuryEntry>>(
      `/api/v1/treasury/accounts/${accountId}/corrections`,
      { amount, direction, memo },
      { errorToast: false }
    )
    return response.data
  }

  return { listAccounts, createAccount, updateAccount, transfer, statement, correct }
}
