// Marker file so Nuxt's `extends` (c12) recognizes this directory as a
// loadable layer. Every pre-existing module layer in this project has
// one — this one was missing from the new Phase 13 modules, which is
// why "Cannot extend config from ..." warnings appeared only for
// these 5 at build time and their pages/components never registered.
export default defineNuxtConfig({})
