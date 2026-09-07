export interface NavigationItem {
  label: string
  icon: string
  to: string
  permission?: string
  order?: number
  /**
   * Optional sidebar grouping key (issue #232). Items sharing a key
   * render under one collapsible, non-clickable header; items without
   * a key stay flat. Free-form — the host never hardcodes section
   * names; headers translate via `nav.sections.<key>` with the raw key
   * as fallback.
   */
  section?: string
}

export interface ModuleDefinition {
  name: string
  label: string
  icon: string
  navigation: NavigationItem[]
}

export interface ActiveModule {
  name: string
  version: string
  category: 'official' | 'community'
  summary: string
  navigation: NavigationItem[]
  permissions: string[]
}

export type ModuleState
  = | 'installed'
    | 'uninstalled'
    | 'to_install'
    | 'to_upgrade'
    | 'to_remove'
    | 'disabled'
    | 'error'

export type ModuleCategory = 'official' | 'community'

export interface ModuleInfo {
  name: string
  version: string
  state: ModuleState
  category: ModuleCategory
  removable: boolean
  auto_install: boolean
  installed_at: string | null
  last_state_change: string
  base_revision: string | null
  applied_revision: string | null
  error_message: string | null
  error_at: string | null
  summary: string
  depends: string[]
  in_disk: boolean
}

export interface ModuleStatus {
  by_state: Record<string, number>
  pending: string[]
  errored: string[]
  total: number
}

export interface ModuleDoctorReport {
  ok: boolean
  orphans: string[]
  missing_dependencies: Array<{ module: string, missing: string }>
  manifest_errors: Array<{ module: string, error: string }>
  errored_modules: Array<{ module: string, error: string }>
}

export interface ModuleOperationResult {
  scheduled: string[]
  requires_restart: boolean
}

export interface ModuleOperationLogEntry {
  id: number
  module_name: string
  operation: 'install' | 'uninstall' | 'upgrade'
  step: string
  status: 'started' | 'completed' | 'failed'
  details: Record<string, unknown> | null
  created_at: string
}

export interface PermissionConfig {
  routes: Record<string, string>
  actions: Record<string, Record<string, string>>
}
