const GENDER_LABEL_KEYS: Record<string, string> = {
  male: 'patients.gender.male',
  female: 'patients.gender.female',
  other: 'patients.gender.other',
  prefer_not_say: 'patients.gender.preferNotSay'
}

/** The i18n key for a stored gender, or null when there is nothing to show. */
export function genderLabelKey(gender: string | null | undefined): string | null {
  return (gender && GENDER_LABEL_KEYS[gender]) || null
}
