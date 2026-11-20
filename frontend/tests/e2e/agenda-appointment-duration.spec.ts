import { test, expect } from './_fixtures'

const API_BASE = process.env.E2E_API_BASE || 'http://localhost:8000'
const date = '2035-06-12'

test('agenda keeps a 75-minute appointment when reassigning the patient and saves an explicit duration change', async ({ loggedIn }) => {
  test.setTimeout(60_000)
  const context = loggedIn.context()
  const csrf = (await context.cookies()).find(cookie => cookie.name === 'dp_csrf')?.value
  if (!csrf) throw new Error('The seeded login did not set the CSRF cookie')
  const headers = { 'X-CSRF-Token': csrf }
  const professionals = await context.request.get(`${API_BASE}/api/v1/auth/professionals`, { headers })
  expect(professionals.ok()).toBeTruthy()
  const { data: team } = await professionals.json() as { data: { id: string }[] }
  expect(team.length).toBeGreaterThan(0)

  const suffix = Date.now().toString(36)
  async function createPatient(firstName: string) {
    const response = await context.request.post(`${API_BASE}/api/v1/patients`, {
      headers,
      data: { first_name: firstName, last_name: `${firstName} Example ${suffix}` }
    })
    expect(response.ok(), await response.text()).toBeTruthy()
    const { data } = await response.json() as { data: { id: string, last_name: string } }
    return data
  }

  const original = await createPatient('Alex')
  const replacement = await createPatient('Sam')
  const response = await context.request.post(`${API_BASE}/api/v1/agenda/appointments`, {
    headers,
    data: {
      patient_id: original.id,
      professional_id: team[0]!.id,
      start_time: `${date}T12:00:00`,
      end_time: `${date}T13:15:00`
    }
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  const { data: appointment } = await response.json() as {
    data: { id: string, start_time: string, end_time: string }
  }
  const appointmentPath = `/api/v1/agenda/appointments/${appointment.id}`

  try {
    await loggedIn.goto(`/appointments?date=${date}`)
    await loggedIn.getByText(original.last_name, { exact: true }).click()
    const editor = loggedIn.getByRole('dialog').filter({ hasText: 'Edit appointment' })
    await expect(editor.getByRole('button', { name: '75 min (current)' })).toHaveAttribute('aria-pressed', 'true')
    await editor.getByRole('button', { name: 'Clear', exact: true }).click()
    await editor.getByTestId('visual-selector-input').fill(replacement.last_name)
    await editor.getByText(`${replacement.last_name}, Sam`, { exact: true }).click()
    await expect(editor.getByRole('button', { name: '75 min (current)' })).toHaveAttribute('aria-pressed', 'true')

    // The fixture may have office hours that exclude this synthetic visit.
    loggedIn.on('dialog', dialog => dialog.accept())

    async function save() {
      const saved = loggedIn.waitForResponse(result =>
        result.request().method() === 'PUT' && new URL(result.url()).pathname === appointmentPath
      )
      await editor.getByRole('button', { name: 'Save', exact: true }).click()
      const result = await saved
      expect(result.ok()).toBeTruthy()
      await expect(editor).toBeHidden()
      const { data } = await result.json() as { data: typeof appointment & { patient_id: string } }
      return { data, payload: result.request().postDataJSON() }
    }

    const reassigned = await save()
    expect(reassigned.payload).not.toHaveProperty('start_time')
    expect(reassigned.payload).not.toHaveProperty('end_time')
    expect(reassigned.data.patient_id).toBe(replacement.id)
    expect(reassigned.data.start_time).toBe(appointment.start_time)
    expect(reassigned.data.end_time).toBe(appointment.end_time)

    await loggedIn.getByText(replacement.last_name, { exact: true }).click()
    await editor.getByRole('button', { name: '45 min', exact: true }).click()
    const resized = await save()
    expect(resized.payload).toHaveProperty('end_time')
    expect(resized.data.start_time).toBe(appointment.start_time)
    expect(Date.parse(resized.data.end_time) - Date.parse(resized.data.start_time)).toBe(45 * 60_000)
  } finally {
    await context.request.delete(`${API_BASE}${appointmentPath}`, { headers })
  }
})
