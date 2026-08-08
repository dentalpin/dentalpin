import { existsSync } from 'fs'
import { resolve } from 'path'
import { defineVitestConfig } from '@nuxt/test-utils/config'

// In Docker the backend modules are mounted at /module_layers (read-only).
// Locally they live at ../backend/app/modules relative to the frontend root.
const backendModules = existsSync('/module_layers')
  ? '/module_layers'
  : resolve(__dirname, '../backend/app/modules')

export default defineVitestConfig({
  resolve: {
    alias: {
      '@backend-modules': backendModules
    }
  },
  test: {
    environment: 'nuxt',
    globals: true,
    // Playwright E2E specs live under tests/e2e/. They use their own
    // test runner (see playwright.config.ts + scripts/e2e.sh) and must
    // not be picked up by vitest — doing so throws
    // "Playwright Test did not expect test.describe() to be called here".
    exclude: ['**/node_modules/**', '**/dist/**', 'tests/e2e/**'],
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
