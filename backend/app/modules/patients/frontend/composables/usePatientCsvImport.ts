import type { ApiResponse } from '~~/app/types'

/**
 * Patient CSV import (#819): a thin client over
 * ``POST /api/v1/patients/import.csv``. Parsing, validation and the
 * duplicate check all stay on the server (``csv_import.py``); this only
 * uploads the file and returns the report.
 */

export interface CsvRowError {
  row: number
  message: string
}

export interface CsvRowDuplicate {
  row: number
  patient_id: string | null
  matched_on: 'national_id' | 'email+date_of_birth' | 'same_file' | string
}

export interface PatientImportReport {
  total: number
  valid: number
  created: number
  skipped: number
  errors: CsvRowError[]
  duplicates: CsvRowDuplicate[]
}

/** Server caps (``csv_import.MAX_CSV_ROWS`` / ``MAX_CSV_BYTES``). */
export const CSV_IMPORT_MAX_ROWS = 1000
export const CSV_IMPORT_MAX_BYTES = 1024 * 1024

/** The column contract, in template order. ``*`` marks the required two. */
export const CSV_IMPORT_COLUMNS = [
  'first_name',
  'last_name',
  'phone',
  'email',
  'date_of_birth',
  'notes',
  'do_not_contact',
  'national_id',
  'national_id_type',
  'billing_name',
  'billing_tax_id'
] as const

export const CSV_IMPORT_REQUIRED_COLUMNS = ['first_name', 'last_name'] as const

/**
 * A committing run creates one patient per row through the normal
 * create path (events included): about 8 s for 1000 rows on a fast
 * machine, so the default 10 s client timeout is too short. A client
 * that gave up would show an error while the server kept creating
 * patients, and a retry would then duplicate every row the duplicate
 * check cannot match (no national id, no email + date of birth).
 */
const COMMIT_TIMEOUT_MS = 5 * 60 * 1000

/** Header row plus one example row, so the file opens with the right columns. */
export function csvImportTemplate(): string {
  const example = [
    'Ana',
    'García',
    '+34600111222',
    'ana@example.com',
    '1990-05-01',
    '',
    'no',
    '12345678Z',
    'dni',
    '',
    ''
  ]
  return `${CSV_IMPORT_COLUMNS.join(',')}\n${example.join(',')}\n`
}

export function usePatientCsvImport() {
  const api = useApi()

  async function upload(
    file: File,
    options: { dryRun: boolean, allowDuplicates?: boolean }
  ): Promise<PatientImportReport> {
    const form = new FormData()
    form.append('file', file)
    const response = await api.post<ApiResponse<PatientImportReport>>(
      '/api/v1/patients/import.csv',
      form,
      {
        query: {
          dry_run: options.dryRun,
          allow_duplicates: options.allowDuplicates ?? false
        },
        // A whole-file rejection (bad header, encoding, over the caps)
        // answers 422; the page renders it inline instead of a toast.
        errorToast: false,
        timeout: options.dryRun ? undefined : COMMIT_TIMEOUT_MS
      }
    )
    return response.data
  }

  return {
    /** Validate only: nothing is written. */
    check: (file: File) => upload(file, { dryRun: true }),
    /** Create the valid rows; duplicates are skipped unless allowed. */
    commit: (file: File, allowDuplicates: boolean) =>
      upload(file, { dryRun: false, allowDuplicates })
  }
}
