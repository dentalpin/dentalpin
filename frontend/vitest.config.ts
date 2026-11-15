import { defineVitestConfig } from '@nuxt/test-utils/config'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// In Docker, backend modules are mounted at /module_layers (read-only).
// Locally, they live at ../backend/app/modules relative to frontend/.
const moduleLayersPath = existsSync('/module_layers')
  ? '/module_layers'
  : fileURLToPath(new URL('../backend/app/modules', import.meta.url))

export default defineVitestConfig({
  resolve: {
    alias: {
      '#module-layers': moduleLayersPath
    }
  },
  test: {
    environment: 'nuxt',
    globals: true,
    // Each worker boots an isolated Nuxt app across all module layers.
    // Cap parallel boots so resource contention does not make otherwise
    // fast composable tests exceed Vitest's default 5 second test timeout.
    maxWorkers: 4,
    testTimeout: 30_000,
    // Nuxt setup compiles all enabled layers and consolidated locales before
    // each isolated suite. On slower developer/CI machines, 10 seconds can
    // expire before a pure test body starts.
    hookTimeout: 120_000,
    // Playwright E2E specs live under tests/e2e/. They use their own
    // test runner (see playwright.config.ts + scripts/e2e.sh) and must
    // not be picked up by vitest — doing so throws
    // "Playwright Test did not expect test.describe() to be called here".
    exclude: ['**/node_modules/**', '**/dist/**', 'tests/e2e/**'],
    setupFiles: ['./tests/setup.ts'],
    environmentOptions: {
      nuxt: {
        mock: {
          intersectionObserver: true,
          indexedDb: true
        }
      }
    }
  }
})
