export const DENTUM_THEME_OPTIONS = [
  { id: 'clinical', labelKey: 'appearance.themes.clinical', swatch: '#0EA5E9' },
  { id: 'mint', labelKey: 'appearance.themes.mint', swatch: '#10B981' },
  { id: 'lavender', labelKey: 'appearance.themes.lavender', swatch: '#8B5CF6' },
  { id: 'coral', labelKey: 'appearance.themes.coral', swatch: '#F43F5E' }
] as const

export type DentumTheme = typeof DENTUM_THEME_OPTIONS[number]['id']

const STORAGE_KEY = 'dentum:appearance-theme'
const THEME_IDS = new Set<string>(DENTUM_THEME_OPTIONS.map(option => option.id))

export function useDentumTheme() {
  const theme = useState<DentumTheme>('dentum:appearance-theme', () => 'clinical')

  function applyTheme(value: DentumTheme) {
    theme.value = value

    if (!import.meta.client) return

    document.documentElement.dataset.dentumTheme = value
    try {
      localStorage.setItem(STORAGE_KEY, value)
    } catch {
      // The current session still gets the chosen theme when storage is unavailable.
    }
  }

  function initializeTheme() {
    if (!import.meta.client) return

    let storedTheme: string | null = null
    try {
      storedTheme = localStorage.getItem(STORAGE_KEY)
    } catch {
      // Continue with the default palette when storage is unavailable.
    }

    const value = storedTheme && THEME_IDS.has(storedTheme)
      ? storedTheme as DentumTheme
      : 'clinical'

    theme.value = value
    document.documentElement.dataset.dentumTheme = value
  }

  return { theme, setTheme: applyTheme, initializeTheme }
}
