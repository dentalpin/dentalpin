import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'
import { PERMISSIONS } from '~~/app/config/permissions'

// Mount the global copilot launcher + drawer into the host's app.overlays
// slot. The component teleports to <body>; nothing renders inline. The
// slot is permission-gated, so it only appears for users with copilot.chat.
export default defineNuxtPlugin(() => {
  registerSlot('app.overlays', {
    id: 'copilot.overlay',
    component: defineAsyncComponent(() => import('../components/CopilotMount.vue')),
    order: 10,
    permission: PERMISSIONS.copilot.chat
  })
})
