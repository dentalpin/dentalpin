// @vitest-environment node
import { describe, expect, it } from 'vitest'
import {
  computeBadge,
  computeEinvoiceColor,
  computeEinvoiceLabel,
  isIndianClinic,
  isNonDraft,
  type BadgeCtx
} from '#module-layers/india_gst/frontend/utils/gstBadgeLogic'

const t = (key: string) => key

function makeCtx(overrides: Partial<BadgeCtx> = {}): BadgeCtx {
  return {
    invoice: { status: 'issued', compliance_data: { IN: { severity: 'ok' } } },
    clinic: { country: 'IN', settings: { country: 'IN' } },
    ...overrides
  }
}

describe('isIndianClinic', () => {
  it('returns true when clinic.country is IN', () => {
    expect(isIndianClinic({ clinic: { country: 'IN', settings: null } })).toBe(true)
  })

  it('returns true when clinic.settings.country is IN', () => {
    expect(isIndianClinic({ clinic: { country: null, settings: { country: 'IN' } } })).toBe(true)
  })

  it('returns false for non-Indian country', () => {
    expect(isIndianClinic({ clinic: { country: 'ES', settings: { country: 'ES' } } })).toBe(false)
  })

  it('returns false when no country is set', () => {
    expect(isIndianClinic({ clinic: { country: null, settings: null } })).toBe(false)
  })

  it('returns false when clinic is null', () => {
    expect(isIndianClinic({ clinic: null })).toBe(false)
  })
})

describe('isNonDraft', () => {
  it('returns true for issued status', () => {
    expect(isNonDraft({ invoice: { status: 'issued' } })).toBe(true)
  })

  it('returns true for paid status', () => {
    expect(isNonDraft({ invoice: { status: 'paid' } })).toBe(true)
  })

  it('returns false for draft status', () => {
    expect(isNonDraft({ invoice: { status: 'draft' } })).toBe(false)
  })

  it('returns false for undefined status', () => {
    expect(isNonDraft({ invoice: { status: undefined } })).toBe(false)
  })

  it('returns false when invoice is null', () => {
    expect(isNonDraft({ invoice: null })).toBe(false)
  })
})

describe('computeBadge', () => {
  it('returns null for non-Indian clinic with no GST data', () => {
    const ctx = makeCtx({
      clinic: { country: 'ES', settings: { country: 'ES' } },
      invoice: { status: 'issued', compliance_data: null }
    })
    expect(computeBadge(ctx, t)).toBeNull()
  })

  it('returns null for Indian clinic with draft invoice and no GST data', () => {
    const ctx = makeCtx({
      invoice: { status: 'draft', compliance_data: null }
    })
    expect(computeBadge(ctx, t)).toBeNull()
  })

  it('returns warning badge for Indian clinic with issued invoice and no GST data', () => {
    const ctx = makeCtx({
      invoice: { status: 'issued', compliance_data: null }
    })
    const badge = computeBadge(ctx, t)
    expect(badge).not.toBeNull()
    expect(badge!.color).toBe('warning')
    expect(badge!.label).toBe('indiaGst.badge.needsAttention')
    expect(badge!.tooltip).toBe('indiaGst.badge.missingGst')
  })

  it('returns success badge for ok severity', () => {
    const ctx = makeCtx({
      invoice: { status: 'issued', compliance_data: { IN: { severity: 'ok' } } }
    })
    const badge = computeBadge(ctx, t)
    expect(badge).not.toBeNull()
    expect(badge!.color).toBe('success')
    expect(badge!.label).toBe('indiaGst.badge.gst')
  })

  it('returns warning badge for warning severity', () => {
    const ctx = makeCtx({
      invoice: { status: 'issued', compliance_data: { IN: { severity: 'warning' } } }
    })
    const badge = computeBadge(ctx, t)
    expect(badge!.color).toBe('warning')
  })

  it('returns error badge for error severity', () => {
    const ctx = makeCtx({
      invoice: { status: 'issued', compliance_data: { IN: { severity: 'error' } } }
    })
    const badge = computeBadge(ctx, t)
    expect(badge!.color).toBe('error')
  })

  it('returns neutral badge for pending severity', () => {
    const ctx = makeCtx({
      invoice: { status: 'issued', compliance_data: { IN: { severity: 'pending' } } }
    })
    const badge = computeBadge(ctx, t)
    expect(badge!.color).toBe('neutral')
  })

  it('uses neutral for unknown severity', () => {
    const ctx = makeCtx({
      invoice: { status: 'issued', compliance_data: { IN: { severity: 'unknown' } } }
    })
    const badge = computeBadge(ctx, t)
    expect(badge!.color).toBe('neutral')
  })

  it('uses IRN generated label when einvoice_state is generated', () => {
    const ctx = makeCtx({
      invoice: { status: 'issued', compliance_data: { IN: { severity: 'ok', einvoice_state: 'generated' } } }
    })
    const badge = computeBadge(ctx, t)
    expect(badge!.label).toBe('indiaGst.badge.irnGenerated')
  })

  it('uses einvoice issue label when einvoice_state is rejected', () => {
    const ctx = makeCtx({
      invoice: { status: 'issued', compliance_data: { IN: { severity: 'ok', einvoice_state: 'rejected' } } }
    })
    const badge = computeBadge(ctx, t)
    expect(badge!.label).toBe('indiaGst.badge.einvoiceIssue')
  })

  it('uses einvoice issue label when einvoice_state is error', () => {
    const ctx = makeCtx({
      invoice: { status: 'issued', compliance_data: { IN: { severity: 'ok', einvoice_state: 'error' } } }
    })
    const badge = computeBadge(ctx, t)
    expect(badge!.label).toBe('indiaGst.badge.einvoiceIssue')
  })

  it('uses gst_document_number as tooltip when present', () => {
    const ctx = makeCtx({
      invoice: { status: 'issued', compliance_data: { IN: { severity: 'ok', gst_document_number: 'FAC/FY26-27/0001' } } }
    })
    const badge = computeBadge(ctx, t)
    expect(badge!.tooltip).toBe('FAC/FY26-27/0001')
  })

  it('falls back to gst label as tooltip when no document number', () => {
    const ctx = makeCtx({
      invoice: { status: 'issued', compliance_data: { IN: { severity: 'ok' } } }
    })
    const badge = computeBadge(ctx, t)
    expect(badge!.tooltip).toBe('indiaGst.badge.gst')
  })

  it('defaults severity to ok when not specified', () => {
    const ctx = makeCtx({
      invoice: { status: 'issued', compliance_data: { IN: {} } }
    })
    const badge = computeBadge(ctx, t)
    expect(badge!.color).toBe('success')
  })
})

describe('computeEinvoiceColor', () => {
  it('returns success for generated', () => {
    expect(computeEinvoiceColor('generated')).toBe('success')
  })

  it('returns error for rejected', () => {
    expect(computeEinvoiceColor('rejected')).toBe('error')
  })

  it('returns error for error', () => {
    expect(computeEinvoiceColor('error')).toBe('error')
  })

  it('returns warning for pending', () => {
    expect(computeEinvoiceColor('pending')).toBe('warning')
  })

  it('returns neutral for not_required', () => {
    expect(computeEinvoiceColor('not_required')).toBe('neutral')
  })

  it('returns neutral for not_configured', () => {
    expect(computeEinvoiceColor('not_configured')).toBe('neutral')
  })

  it('returns neutral for null', () => {
    expect(computeEinvoiceColor(null)).toBe('neutral')
  })

  it('returns neutral for undefined', () => {
    expect(computeEinvoiceColor(undefined)).toBe('neutral')
  })
})

describe('computeEinvoiceLabel', () => {
  it('returns translated label for each known state', () => {
    expect(computeEinvoiceLabel('not_required', t)).toBe('indiaGst.einvoice.notRequired')
    expect(computeEinvoiceLabel('not_configured', t)).toBe('indiaGst.einvoice.notConfigured')
    expect(computeEinvoiceLabel('pending', t)).toBe('indiaGst.einvoice.pending')
    expect(computeEinvoiceLabel('generated', t)).toBe('indiaGst.einvoice.generated')
    expect(computeEinvoiceLabel('rejected', t)).toBe('indiaGst.einvoice.rejected')
    expect(computeEinvoiceLabel('error', t)).toBe('indiaGst.einvoice.error')
  })

  it('returns not_required label for null state', () => {
    expect(computeEinvoiceLabel(null, t)).toBe('indiaGst.einvoice.notRequired')
  })

  it('returns not_required label for undefined state', () => {
    expect(computeEinvoiceLabel(undefined, t)).toBe('indiaGst.einvoice.notRequired')
  })

  it('passes through unknown state as label', () => {
    expect(computeEinvoiceLabel('unknown_state', t)).toBe('unknown_state')
  })
})
