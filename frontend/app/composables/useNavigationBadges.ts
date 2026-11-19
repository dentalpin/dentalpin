/** Optional module-owned counters keyed by their navigation route. */
export function useNavigationBadges() {
  return useState<Record<string, number | undefined>>('modules:navigation-badges', () => ({}))
}
