/**
 * Settings super-group config — purely a display concern for
 * SettingsCategoryNav.vue.
 *
 * The real settings registry (useSettingsRegistry.ts) has a fixed set of
 * 9 categories and knows nothing about super-groups. This file just maps
 * those 9 category ids into 5 named sections so the settings nav can
 * render headers above clusters of categories. Any category id with no
 * entry here still renders — ungrouped, at the end — so a future new
 * category degrades gracefully instead of disappearing.
 */

export interface SettingsSuperGroupDef {
  id: string
  labelKey: string
  order: number
}

export const SETTINGS_SUPER_GROUPS: SettingsSuperGroupDef[] = [
  { id: 'clinicSetup', labelKey: 'settings.superGroups.clinicSetup', order: 1 },
  { id: 'clinicalConfig', labelKey: 'settings.superGroups.clinicalConfig', order: 2 },
  { id: 'financialConfig', labelKey: 'settings.superGroups.financialConfig', order: 3 },
  { id: 'systemAddons', labelKey: 'settings.superGroups.systemAddons', order: 4 },
  { id: 'myPreferences', labelKey: 'settings.superGroups.myPreferences', order: 5 }
]

export const SETTINGS_CATEGORY_SUPER_GROUP: Record<string, string> = {
  general: 'clinicSetup',
  workspace: 'clinicSetup',
  people: 'clinicSetup',

  clinical: 'clinicalConfig',

  billing: 'financialConfig',

  communications: 'systemAddons',
  integrations: 'systemAddons',
  modules: 'systemAddons',

  account: 'myPreferences'
}
