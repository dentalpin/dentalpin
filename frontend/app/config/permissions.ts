/**
 * Centralized permission configuration.
 *
 * All permission checks should reference this config instead of
 * hardcoding permission strings throughout the codebase.
 */

// Resource-action permission mapping
export const PERMISSIONS = {
  patients: {
    read: 'patients.read',
    write: 'patients.write'
  },
  medicalHistory: {
    read: 'patients_clinical.medical.read',
    write: 'patients_clinical.medical.write'
  },
  emergencyContact: {
    read: 'patients_clinical.emergency.read',
    write: 'patients_clinical.emergency.write'
  },
  appointments: {
    read: 'agenda.appointments.read',
    write: 'agenda.appointments.write'
  },
  users: {
    read: 'admin.users.read',
    write: 'admin.users.write'
  },
  odontogram: {
    read: 'odontogram.read',
    write: 'odontogram.write',
    treatmentsRead: 'odontogram.treatments.read',
    treatmentsWrite: 'odontogram.treatments.write'
  },
  catalog: {
    read: 'catalog.read',
    write: 'catalog.write',
    admin: 'catalog.admin'
  },
  budget: {
    read: 'budget.read',
    write: 'budget.write',
    admin: 'budget.admin',
    renegotiate: 'budget.renegotiate',
    acceptInClinic: 'budget.accept_in_clinic'
  },
  billing: {
    read: 'billing.read',
    write: 'billing.write',
    admin: 'billing.admin'
  },
  notifications: {
    templatesRead: 'notifications.templates.read',
    templatesWrite: 'notifications.templates.write',
    preferencesRead: 'notifications.preferences.read',
    preferencesWrite: 'notifications.preferences.write',
    logsRead: 'notifications.logs.read',
    send: 'notifications.send',
    settingsRead: 'notifications.settings.read',
    settingsWrite: 'notifications.settings.write'
  },
  reports: {
    billingRead: 'reports.billing.read',
    budgetsRead: 'reports.budgets.read',
    schedulingRead: 'reports.scheduling.read'
  },
  documents: {
    read: 'media.documents.read',
    write: 'media.documents.write'
  },
  attachments: {
    read: 'media.attachments.read',
    write: 'media.attachments.write'
  },
  treatmentPlans: {
    read: 'treatment_plan.plans.read',
    write: 'treatment_plan.plans.write',
    confirm: 'treatment_plan.plans.confirm',
    close: 'treatment_plan.plans.close',
    reactivate: 'treatment_plan.plans.reactivate'
  },
  clinicalNotes: {
    read: 'clinical_notes.notes.read',
    write: 'clinical_notes.notes.write'
  },
  agents: {
    view: 'agents.view',
    supervise: 'agents.supervise',
    configure: 'agents.configure',
    manage: 'agents.manage'
  },
  admin: {
    clinicRead: 'admin.clinic.read',
    clinicWrite: 'admin.clinic.write'
  },
  migrationImport: {
    jobRead: 'migration_import.job.read',
    jobWrite: 'migration_import.job.write',
    jobExecute: 'migration_import.job.execute',
    binaryWrite: 'migration_import.binary.write'
  },
  payments: {
    recordRead: 'payments.record.read',
    recordWrite: 'payments.record.write',
    recordRefund: 'payments.record.refund',
    reportsRead: 'payments.reports.read'
  },
  verifactu: {
    settingsRead: 'verifactu.settings.read',
    settingsConfigure: 'verifactu.settings.configure',
    queueManage: 'verifactu.queue.manage',
    recordsRead: 'verifactu.records.read',
    environmentPromote: 'verifactu.environment.promote'
  },
  recalls: {
    read: 'recalls.read',
    write: 'recalls.write',
    delete: 'recalls.delete'
  },
  whatsappKapso: {
    settingsRead: 'whatsapp_kapso.settings.read',
    settingsWrite: 'whatsapp_kapso.settings.write'
  },
  schedules: {
    clinicHoursRead: 'schedules.clinic_hours.read',
    clinicHoursWrite: 'schedules.clinic_hours.write',
    professionalRead: 'schedules.professional.read',
    professionalWrite: 'schedules.professional.write',
    professionalOwnRead: 'schedules.professional.own.read',
    professionalOwnWrite: 'schedules.professional.own.write'
  },
  periodontogram: {
    read: 'periodontogram.read',
    write: 'periodontogram.write'
  },
  copilot: {
    chat: 'copilot.chat',
    historyRead: 'copilot.history.read',
    historyReadAll: 'copilot.history.read_all',
    supervise: 'copilot.supervise',
    configure: 'copilot.configure'
  },
  accountingExport: {
    read: 'accounting_export.export.read',
    run: 'accounting_export.export.run'
  },
  expenses: {
    read: 'expenses.read',
    write: 'expenses.write'
  },
  contacts: {
    read: 'contacts.read',
    write: 'contacts.write'
  },
  labOrders: {
    read: 'lab_orders.read',
    write: 'lab_orders.write'
  },
  inventory: {
    read: 'inventory.read',
    write: 'inventory.write'
  },
   tasks: {
    read: 'tasks.read',
    write: 'tasks.write'
  },
  smsGateway: {
    read: 'sms_gateway.settings.read',
    write: 'sms_gateway.settings.write'
  }
} as const
