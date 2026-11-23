import { errorDetail, errorStatus } from '~~/app/utils/error'

const ALREADY_PLANNED = 'treatment_already_planned'

/**
 * Plan number holding the treatment when adding a plan item failed
 * because the treatment already sits on a plan (#1073), else `null`.
 *
 * The backend answers 409 with the machine-stable string
 * `treatment_already_planned:<plan_number>`; split on the FIRST colon.
 * An empty plan number comes back as `''` (still a clash).
 */
export function alreadyPlannedIn(error: unknown): string | null {
  if (errorStatus(error) !== 409) return null
  const detail = errorDetail(error)
  if (!detail) return null
  const sep = detail.indexOf(':')
  const code = sep === -1 ? detail : detail.slice(0, sep)
  if (code !== ALREADY_PLANNED) return null
  return sep === -1 ? '' : detail.slice(sep + 1)
}
