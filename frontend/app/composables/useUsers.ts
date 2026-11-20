import type { User, UserCreate, UserRole, UserUpdate, PaginatedResponse, ApiResponse } from '~/types'
import { errorMessage } from '~/utils/error'

export interface ClinicUser {
  id: string
  email: string
  first_name: string
  last_name: string
  is_active: boolean
  role: UserRole
  is_professional: boolean
  mfa_enabled?: boolean
  created_at: string
}

export function useUsers() {
  const api = useApi()
  const toast = useToast()
  const { t } = useI18n()

  const users = ref<ClinicUser[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Available roles for user creation
  // Note: Labels are role codes - use t(`settings.roles.${role}`) in templates for translation
  const availableRoles: { value: UserRole, label: string }[] = [
    { value: 'admin', label: 'admin' },
    { value: 'dentist', label: 'dentist' },
    { value: 'hygienist', label: 'hygienist' },
    { value: 'assistant', label: 'assistant' },
    { value: 'receptionist', label: 'receptionist' }
  ]

  async function fetchUsers(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      // The backend returns users with their clinic membership info in paginated format
      const response = await api.get<PaginatedResponse<ClinicUser>>('/api/v1/auth/users')
      users.value = response.data
    } catch (e) {
      error.value = t('settings.errors.loadUsers')
      console.error('Failed to fetch users:', e)
    } finally {
      isLoading.value = false
    }
  }

  async function createUser(data: UserCreate): Promise<User | null> {
    isLoading.value = true
    error.value = null

    try {
      // The catch below toasts a status-specific message itself.
      const response = await api.post<ApiResponse<User>>('/api/v1/auth/users', data, { errorToast: false })
      toast.add({
        title: t('common.success'),
        description: t('settings.messages.userCreated'),
        color: 'success'
      })
      // Refresh the user list
      await fetchUsers()
      return response.data
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number, data?: { message?: string, detail?: string } }
      if (fetchError.statusCode === 409) {
        error.value = t('settings.errors.emailExists')
        toast.add({
          title: t('common.error'),
          description: t('settings.errors.emailExists'),
          color: 'error'
        })
      } else if (fetchError.statusCode === 422) {
        error.value = errorMessage(e, t('settings.errors.invalidData'))
        toast.add({
          title: t('common.error'),
          description: error.value,
          color: 'error'
        })
      } else {
        error.value = t('settings.errors.createUser')
        toast.add({
          title: t('common.error'),
          description: t('settings.errors.createUser'),
          color: 'error'
        })
      }
      console.error('Failed to create user:', e)
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function updateUser(userId: string, data: UserUpdate): Promise<ClinicUser | null> {
    isLoading.value = true
    error.value = null

    try {
      const response = await api.put<ApiResponse<ClinicUser>>(`/api/v1/auth/users/${userId}`, data, { errorToast: false })
      toast.add({
        title: t('common.success'),
        description: t('settings.messages.userUpdated'),
        color: 'success'
      })
      // Refresh the user list
      await fetchUsers()
      return response.data
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number, data?: { message?: string, detail?: string } }
      if (fetchError.statusCode === 409) {
        error.value = t('settings.errors.emailExists')
        toast.add({
          title: t('common.error'),
          description: t('settings.errors.emailExists'),
          color: 'error'
        })
      } else if (fetchError.statusCode === 400) {
        error.value = errorMessage(e, t('settings.errors.operationNotAllowed'))
        toast.add({
          title: t('common.error'),
          description: error.value,
          color: 'error'
        })
      } else if (fetchError.statusCode === 404) {
        error.value = t('settings.errors.userNotFound')
        toast.add({
          title: t('common.error'),
          description: t('settings.errors.userNotFound'),
          color: 'error'
        })
      } else {
        error.value = t('settings.errors.updateUser')
        toast.add({
          title: t('common.error'),
          description: t('settings.errors.updateUser'),
          color: 'error'
        })
      }
      console.error('Failed to update user:', e)
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function deleteUser(userId: string): Promise<boolean> {
    isLoading.value = true
    error.value = null

    try {
      await api.del(`/api/v1/auth/users/${userId}`, { errorToast: false })
      toast.add({
        title: t('common.success'),
        description: t('settings.messages.userDeleted'),
        color: 'success'
      })
      // Refresh the user list
      await fetchUsers()
      return true
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number, data?: { message?: string, detail?: string } }
      if (fetchError.statusCode === 400) {
        error.value = errorMessage(e, t('settings.errors.operationNotAllowed'))
        toast.add({
          title: t('common.error'),
          description: error.value,
          color: 'error'
        })
      } else if (fetchError.statusCode === 404) {
        error.value = t('settings.errors.userNotFound')
        toast.add({
          title: t('common.error'),
          description: t('settings.errors.userNotFound'),
          color: 'error'
        })
      } else {
        error.value = t('settings.errors.deleteUser')
        toast.add({
          title: t('common.error'),
          description: t('settings.errors.deleteUser'),
          color: 'error'
        })
      }
      console.error('Failed to delete user:', e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  /** Mint a one-time set-password link for a member (new account or admin reset). */
  async function createInviteLink(userId: string): Promise<{ url: string, expiresAt: string } | null> {
    try {
      const response = await api.post<ApiResponse<{ token: string, expires_at: string }>>(
        `/api/v1/auth/users/${userId}/invite-link`,
        null,
        { errorToast: false }
      )
      const url = `${window.location.origin}/set-password?token=${encodeURIComponent(response.data.token)}`
      return { url, expiresAt: response.data.expires_at }
    } catch (e) {
      toast.add({
        title: t('common.error'),
        description: t('settings.errors.inviteLink'),
        color: 'error'
      })
      console.error('Failed to create invite link:', e)
      return null
    }
  }

  return {
    users: readonly(users),
    isLoading: readonly(isLoading),
    error: readonly(error),
    availableRoles,
    fetchUsers,
    createUser,
    createInviteLink,
    updateUser,
    deleteUser
  }
}
