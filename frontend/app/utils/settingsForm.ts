export type SettingType = 'string' | 'integer' | 'boolean' | 'enum'

export interface SettingDeclaration {
  key: string
  type: SettingType
  default: unknown
  writable: boolean
  label_key: string
  description_key?: string | null
  choices: string[]
  min_value?: number | null
  max_value?: number | null
  max_length?: number | null
  multiline: boolean
  nullable: boolean
}

export interface ModuleSettings {
  module: string
  settings: SettingDeclaration[]
  values: Record<string, unknown>
}

export function initialFormValues(data: ModuleSettings): Record<string, unknown> {
  const values: Record<string, unknown> = {}
  for (const setting of data.settings) {
    const value = data.values[setting.key]
    values[setting.key] = value === undefined ? setting.default : value
  }
  return values
}

export function writableValues(
  data: ModuleSettings,
  form: Record<string, unknown>
): Record<string, unknown> {
  const initial = initialFormValues(data)
  const payload: Record<string, unknown> = {}
  for (const setting of data.settings) {
    if (!setting.writable) continue
    const value = form[setting.key]
    if (setting.type === 'integer' && !setting.nullable && (value === '' || value === null)) {
      continue
    }
    const next = setting.nullable && value === '' ? null : value
    if (Object.is(next, initial[setting.key])) continue
    payload[setting.key] = next
  }
  return payload
}
