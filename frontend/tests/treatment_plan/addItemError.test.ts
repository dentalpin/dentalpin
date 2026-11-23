import { describe, expect, it } from 'vitest'
import { alreadyPlannedIn } from '#module-layers/treatment_plan/frontend/utils/addItemError'

// Shape useApi throws: the global HTTP handler puts the detail in `message`.
function apiError(statusCode: number, message: string) {
  return { statusCode, data: { message, errors: [message] } }
}

describe('alreadyPlannedIn (#1073)', () => {
  it('returns the plan number from a 409 treatment_already_planned', () => {
    expect(alreadyPlannedIn(apiError(409, 'treatment_already_planned:PLAN-2026-0007')))
      .toBe('PLAN-2026-0007')
  })

  it('keeps a clash without a plan number as an empty string', () => {
    expect(alreadyPlannedIn(apiError(409, 'treatment_already_planned:'))).toBe('')
  })

  it('ignores other 409s, other statuses and non-API errors', () => {
    expect(alreadyPlannedIn(apiError(409, 'Plan is locked by an active budget'))).toBeNull()
    expect(alreadyPlannedIn(apiError(400, 'treatment_already_planned:PLAN-1'))).toBeNull()
    expect(alreadyPlannedIn(new Error('network'))).toBeNull()
    expect(alreadyPlannedIn(undefined)).toBeNull()
  })
})
