import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// The help drawer anchors a named diagnosis sub-view at `#<diagnosisView>`
// inside the patient-detail fragment (#573). The anchor is hand-written
// HTML in the docs; the view id comes from the module's slot registration.
// Nothing else joins the two - this guard fails when they drift apart
// (a renamed slot id, or a dropped anchor line, would otherwise silently
// send the drawer back to the top of the page).

function slotIds(): string[] {
  const src = readFileSync(
    resolve(__dirname, '../../module_layers/periodontogram/frontend/plugins/slots.client.ts'),
    'utf-8'
  )
  return [...src.matchAll(/id:\s*'([a-z0-9-]+)'/g)].map(m => m[1]!)
}

describe('patient-diagnosis subtab anchors (#573)', () => {
  it('every registered subtab id has a matching anchor in both locales', () => {
    const ids = slotIds()
    expect(ids).toContain('periodontogram')
    for (const locale of ['en', 'es']) {
      const md = readFileSync(
        resolve(__dirname, `../../../docs/user-manual/${locale}/patients/screens/detail.md`),
        'utf-8'
      )
      for (const id of ids) {
        expect(md, `${locale} detail.md is missing the anchor for subtab "${id}"`)
          .toContain(`<a id="${id}"></a>`)
      }
    }
  })
})
