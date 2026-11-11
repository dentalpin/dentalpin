import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * #819: the CSV import screen is a thin client over
 * ``POST /api/v1/patients/import.csv``. These pin the request it sends:
 * the multipart file, the dry-run / allow_duplicates flags, inline
 * errors (no toast), and a long timeout on the committing run only.
 */
const refresh = vi.fn(async () => true)
mockNuxtImport('useAuth', () => () => ({ refresh, logout: vi.fn() }))
mockNuxtImport('useToast', () => () => ({ add: vi.fn() }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string, fallback?: string) => fallback ?? key }))

const REPORT = { total: 2, valid: 2, created: 0, skipped: 0, errors: [], duplicates: [] }

function csvFile(): File {
  return new File(['first_name,last_name\nAna,García\n'], 'patients.csv', { type: 'text/csv' })
}

async function composable() {
  const { usePatientCsvImport } = await import('#module-layers/patients/frontend/composables/usePatientCsvImport')
  return usePatientCsvImport()
}

describe('usePatientCsvImport', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn(async () => ({ data: REPORT }))
    vi.stubGlobal('$fetch', fetchMock)
  })

  it('checks the file as a dry run with the default timeout', async () => {
    const report = await (await composable()).check(csvFile())

    expect(report).toEqual(REPORT)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('/api/v1/patients/import.csv?dry_run=true&allow_duplicates=false')
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.body as FormData).get('file')).toBeInstanceOf(File)
    expect(init.timeout).toBe(10000)
  })

  it('commits with allow_duplicates and a long timeout', async () => {
    await (await composable()).commit(csvFile(), true)

    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe('/api/v1/patients/import.csv?dry_run=false&allow_duplicates=true')
    // 1000 rows take ~8 s locally; a client that gave up at 10 s would
    // report a failure while the server kept creating patients.
    expect(init.timeout).toBeGreaterThanOrEqual(60_000)
  })

  it('rethrows a whole-file 422 for the page to show inline', async () => {
    fetchMock.mockRejectedValueOnce(Object.assign(new Error('Unprocessable'), {
      statusCode: 422,
      data: { message: 'CSV missing required columns: last_name' }
    }))

    await expect((await composable()).check(csvFile())).rejects.toMatchObject({ statusCode: 422 })
  })
})

describe('csvImportTemplate', () => {
  it('starts with the server column contract, in order, plus a valid example row', async () => {
    const { csvImportTemplate, CSV_IMPORT_COLUMNS } = await import(
      '#module-layers/patients/frontend/composables/usePatientCsvImport'
    )
    const [header, example, trailing] = csvImportTemplate().split('\n')
    expect(header).toBe(CSV_IMPORT_COLUMNS.join(','))
    expect(example!.split(',')).toHaveLength(CSV_IMPORT_COLUMNS.length)
    expect(trailing).toBe('')
  })

  it('lists exactly the columns the server reads', async () => {
    // The screen documents the contract; csv_import.COLUMN_MAP enforces it.
    // A column added on one side only would be silently ignored or
    // advertised without effect.
    const { CSV_IMPORT_COLUMNS, CSV_IMPORT_REQUIRED_COLUMNS } = await import(
      '#module-layers/patients/frontend/composables/usePatientCsvImport'
    )
    const src = readFileSync(
      resolve(__dirname, '../../../backend/app/modules/patients/csv_import.py'),
      'utf-8'
    )
    const mapBlock = src.slice(src.indexOf('COLUMN_MAP = {'), src.indexOf('}', src.indexOf('COLUMN_MAP = {')))
    const serverColumns = [...mapBlock.matchAll(/"(\w+)":/g)].map(m => m[1])
    expect([...CSV_IMPORT_COLUMNS].sort()).toEqual([...serverColumns].sort())
    const required = /REQUIRED_COLUMNS = \(([^)]*)\)/.exec(src)![1]!
    expect([...CSV_IMPORT_REQUIRED_COLUMNS]).toEqual([...required.matchAll(/"(\w+)"/g)].map(m => m[1]))
  })
})
