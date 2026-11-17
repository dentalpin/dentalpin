import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'
import { WHATSAPP_MANUAL_PERMISSIONS } from '../permissions'

export default defineNuxtPlugin(() => {
  const active = useActiveModulesState()
  const installed = () => !!active.value?.some(module => module.name === 'whatsapp_manual')
  const button = defineAsyncComponent(() => import('../components/ManualWhatsAppButton.vue'))

  registerSlot('patient.summary.actions', {
    id: 'whatsapp_manual.patient.summary.actions',
    component: button,
    permission: WHATSAPP_MANUAL_PERMISSIONS.write,
    condition: installed,
    order: 30
  })

  registerSlot('app.overlays', {
    id: 'whatsapp_manual.navigation-count',
    component: defineAsyncComponent(() => import('../components/ManualWhatsAppNavigation')),
    permission: WHATSAPP_MANUAL_PERMISSIONS.read,
    condition: installed
  })
})
