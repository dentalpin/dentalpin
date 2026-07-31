// Compute the AEAT badge style + tooltip from an invoice's
// compliance_data. Used by both the row badge (invoice list) and the
// header badge (invoice detail). Returns null when there is nothing to
// render so the slot stays invisible for non-ES invoices.

export type ComplianceSeverity = 'ok' | 'warning' | 'pending' | 'error'

export interface ComplianceBadgeData {
  severity: ComplianceSeverity
  color: 'success' | 'warning' | 'info' | 'error'
  icon: string
  shortLabel: string // "AEAT"
  tooltip: string
  errorMessage: string | null
  state: string | null
  errorCode: number | null
}

const SEVERITY_TO_COLOR: Record<ComplianceSeverity, ComplianceBadgeData['color']> = {
  ok: 'success',
  warning: 'warning',
  pending: 'info',
  error: 'error'
}

const SEVERITY_TO_ICON: Record<ComplianceSeverity, string> = {
  ok: 'i-lucide-check',
  warning: 'i-lucide-alert-triangle',
  pending: 'i-lucide-clock-3',
  error: 'i-lucide-x'
}

// Mirrors backend ``services/severity.py``. Used as a fallback when
// the backend hasn't backfilled severity yet for old invoices — we
// derive it from state + error_code on the fly.
function deriveSeverity(state: string | null, errorCode: number | null): ComplianceSeverity {
  if (state === 'accepted') return 'ok'
  if (state === 'accepted_with_errors') return 'warning'
  if (state === 'rejected' || state === 'failed_validation') return 'error'
  if (state === 'failed_transient') {
    const c = errorCode ?? 0
    return c === -2 || c >= 1000 ? 'error' : 'pending'
  }
  return 'pending'
}

// Per-country entry inside ``invoice.compliance_data`` (JSONB — keep
// the shape loose beyond the fields the badge reads).
export interface ComplianceCountryEntry {
  state?: string | null
  error_code?: number | null
  error_message?: string | null
  severity?: ComplianceSeverity | null
  [key: string]: unknown
}

export type ComplianceData = Record<string, ComplianceCountryEntry | undefined>

export function useComplianceBadge(
  complianceData: Ref<ComplianceData | null | undefined> | ComputedRef<ComplianceData | null | undefined>
): ComputedRef<ComplianceBadgeData | null> {
  const { t } = useI18n()

  return computed(() => {
    const cd = unref(complianceData)
    const es = cd?.ES
    if (!es) return null

    const state = (es.state as string | null | undefined) ?? null
    const errorCode = (es.error_code as number | null | undefined) ?? null
    const errorMessage = (es.error_message as string | null | undefined) ?? null
    const severity: ComplianceSeverity
      = (es.severity as ComplianceSeverity | undefined) || deriveSeverity(state, errorCode)

    const tooltipBase = t(`verifactu.badge.tooltip.${severity}`)
    const tooltip = errorMessage && severity === 'error'
      ? `${tooltipBase}${errorCode ? ` (${errorCode})` : ''}: ${errorMessage}`
      : tooltipBase

    return {
      severity,
      color: SEVERITY_TO_COLOR[severity],
      icon: SEVERITY_TO_ICON[severity],
      shortLabel: t('verifactu.badge.short'),
      tooltip,
      errorMessage,
      state,
      errorCode
    }
  })
}
