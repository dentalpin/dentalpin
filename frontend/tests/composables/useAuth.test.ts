import { describe, expect, it } from 'vitest'

describe('useAuth composable', () => {
  describe('initialization', () => {
    it('should export useAuth function', async () => {
      const module = await import('~/composables/useAuth')
      expect(module.useAuth).toBeDefined()
      expect(typeof module.useAuth).toBe('function')
    })
  })

  describe('returned interface', () => {
    it('should return expected properties', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      const auth = useAuth()

      // Check returned properties exist
      expect(auth).toHaveProperty('user')
      expect(auth).toHaveProperty('hasSession')
      expect(auth).toHaveProperty('isAuthenticated')
      expect(auth).toHaveProperty('login')
      expect(auth).toHaveProperty('logout')
      expect(auth).toHaveProperty('refresh')
      expect(auth).toHaveProperty('fetchUser')
      expect(auth).toHaveProperty('init')
    })

    it('should have login as an async function', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      const auth = useAuth()

      expect(typeof auth.login).toBe('function')
    })

    it('should have logout as an async function', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      const auth = useAuth()

      expect(typeof auth.logout).toBe('function')
    })

    it('should have refresh as an async function', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      const auth = useAuth()

      expect(typeof auth.refresh).toBe('function')
    })
  })

  describe('initial state', () => {
    it('should not be authenticated initially', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      const auth = useAuth()

      // Without tokens, should not be authenticated
      expect(auth.isAuthenticated.value).toBe(false)
    })

    it('should have null user initially', async () => {
      const { useAuth } = await import('~/composables/useAuth')
      const auth = useAuth()

      expect(auth.user.value).toBe(null)
    })
  })
})
