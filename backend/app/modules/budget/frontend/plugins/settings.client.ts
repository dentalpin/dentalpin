/**
 * Registers budget's settings pages on the host registry. Mounted as
 * cards under ``/settings/billing`` and as full pages at
 * ``/settings/billing/<path>`` via the host's dynamic category route.
 *
 * Mirrors the schedules module pattern (ADR 0003): the plugin imports
 * the registry from ``~~/app/composables/...`` (host shell), not from
 * another module, so ``manifest.depends`` stays at
 * ``["patients", "catalog", "odontogram"]``.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'budget-expiry',
    category: 'billing',
    labelKey: 'budget.settings.cards.expiry.title',
    descriptionKey: 'budget.settings.cards.expiry.description',
    icon: 'i-lucide-calendar-clock',
    permission: 'admin.clinic.write',
    component: () => import('../components/settings/BudgetExpiryPage.vue'),
    searchKeywords: ['budget', 'presupuesto', 'expiry', 'caducidad', 'auto-close', 'cierre'],
    order: 50
  })

  registerSettingsPage({
    path: 'budget-reminders',
    category: 'billing',
    labelKey: 'budget.settings.cards.reminders.title',
    descriptionKey: 'budget.settings.cards.reminders.description',
    icon: 'i-lucide-bell',
    permission: 'admin.clinic.write',
    component: () => import('../components/settings/BudgetRemindersPage.vue'),
    searchKeywords: ['budget', 'presupuesto', 'recordatorio', 'reminder', 'email'],
    order: 51
  })

  registerSettingsPage({
    path: 'budget-public-link',
    category: 'billing',
    labelKey: 'budget.settings.cards.publicLink.title',
    descriptionKey: 'budget.settings.cards.publicLink.description',
    icon: 'i-lucide-shield-check',
    permission: 'admin.clinic.write',
    component: () => import('../components/settings/BudgetPublicLinkPage.vue'),
    searchKeywords: ['budget', 'presupuesto', 'public', 'link', 'auth', 'verificacion', 'security'],
    order: 52
  })
})
