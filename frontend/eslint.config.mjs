// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs'

// Module-layer frontend code (backend/app/modules/*/frontend) lives outside
// this directory, so `eslint .` never saw it — files there were reported as
// "outside of base path" and silently skipped, in CI too. The
// `module_layers` symlink (mirroring the docker-compose mount of the same
// name) brings the layers inside the base path; `npm run lint` passes it
// explicitly because ESLint does not traverse symlinked directories on its
// own. Running from the repo root with --config is not an option: the
// Nuxt-generated config only resolves relative to this directory.
export default withNuxt(
  {
    // Mirror `nuxt/disables/routes`: routed components are allowed
    // single-word names (new.vue, index.vue, [id].vue).
    name: 'dentalpin/module-layers/routes',
    files: ['module_layers/*/frontend/{pages,layouts}/**/*.{js,ts,jsx,tsx,vue}'],
    rules: {
      'vue/multi-word-component-names': 'off'
    }
  },
  {
    // Python bytecode caches under backend/app/modules would otherwise be
    // traversed when `module_layers` is passed as a lint target.
    ignores: ['module_layers/**/__pycache__/**', 'module_layers/**/migrations/**']
  }
)
