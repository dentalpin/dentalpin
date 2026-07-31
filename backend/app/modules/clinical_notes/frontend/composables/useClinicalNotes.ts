import type {
  ApiResponse,
  AttachmentOwnerType,
  ClinicalNote,
  ClinicalNoteCreate,
  ClinicalNoteEntry,
  ClinicalNoteOwnerType,
  ClinicalNoteUpdate,
  NoteAttachment,
  NoteAttachmentCreate,
  NoteTemplate,
  NoteType,
  PlanNotesGroup,
  RecentNoteEntry
} from '~~/app/types'

/**
 * Clinical notes — owned by the `clinical_notes` module since issue #60.
 *
 * Polymorphic over four note_type / owner_type pairings:
 *   administrative + diagnosis → owner_type='patient'
 *   treatment                  → owner_type='treatment' (odontogram.Treatment.id)
 *   treatment_plan             → owner_type='plan' (treatment_plans.id)
 *
 * Endpoints under `/api/v1/clinical_notes/`. Visit-level notes still live on
 * `AppointmentTreatment.notes` in the agenda module and are PATCHed there.
 */
export function useClinicalNotes() {
  const api = useApi()
  const toast = useToast()
  const { t } = useI18n()

  const loading = ref(false)

  async function listForOwner(
    ownerType: ClinicalNoteOwnerType,
    ownerId: string
  ): Promise<ClinicalNote[]> {
    loading.value = true
    try {
      const qs = new URLSearchParams({ owner_type: ownerType, owner_id: ownerId })
      const response = await api.get<ApiResponse<ClinicalNote[]>>(
        `/api/v1/clinical_notes/notes?${qs}`
      )
      return response.data
    } finally {
      loading.value = false
    }
  }

  async function listRecentForPatient(
    patientId: string,
    options: { types?: NoteType[], limit?: number, before?: string } = {}
  ): Promise<RecentNoteEntry[]> {
    const qs = new URLSearchParams()
    if (options.limit) qs.set('limit', String(options.limit))
    if (options.before) qs.set('before', options.before)
    if (options.types) {
      for (const t of options.types) qs.append('types', t)
    }
    const url = `/api/v1/clinical_notes/patients/${patientId}/recent${qs.toString() ? `?${qs}` : ''}`
    const response = await api.get<ApiResponse<RecentNoteEntry[]>>(url)
    return response.data
  }

  async function listMergedForPlan(planId: string): Promise<ClinicalNoteEntry[]> {
    const response = await api.get<ApiResponse<ClinicalNoteEntry[]>>(
      `/api/v1/clinical_notes/treatment-plans/${planId}/merged`
    )
    return response.data
  }

  async function listGroupedForPatient(patientId: string): Promise<PlanNotesGroup[]> {
    const response = await api.get<ApiResponse<PlanNotesGroup[]>>(
      `/api/v1/clinical_notes/patients/${patientId}/by-plan`
    )
    return response.data
  }

  async function listTemplates(category?: string): Promise<NoteTemplate[]> {
    const qs = new URLSearchParams()
    if (category) qs.set('category', category)
    const url = `/api/v1/clinical_notes/note-templates${qs.toString() ? `?${qs}` : ''}`
    const response = await api.get<ApiResponse<NoteTemplate[]>>(url)
    return response.data
  }

  async function createNote(input: ClinicalNoteCreate): Promise<ClinicalNote | null> {
    try {
      const response = await api.post<ApiResponse<ClinicalNote>>(
        '/api/v1/clinical_notes/notes',
        input
      )
      toast.add({ title: t('clinicalNotes.toasts.saved'), color: 'success' })
      return response.data
    } catch (error) {
      console.error('Error creating clinical note:', error)
      toast.add({ title: t('clinicalNotes.toasts.saveFailed'), color: 'error' })
      return null
    }
  }

  async function updateNote(noteId: string, body: string): Promise<ClinicalNote | null> {
    try {
      const payload: ClinicalNoteUpdate = { body }
      const response = await api.patch<ApiResponse<ClinicalNote>>(
        `/api/v1/clinical_notes/notes/${noteId}`,
        payload
      )
      toast.add({ title: t('clinicalNotes.toasts.saved'), color: 'success' })
      return response.data
    } catch (error) {
      console.error('Error updating clinical note:', error)
      toast.add({ title: t('clinicalNotes.toasts.saveFailed'), color: 'error' })
      return null
    }
  }

  async function deleteNote(noteId: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/clinical_notes/notes/${noteId}`)
      toast.add({ title: t('clinicalNotes.toasts.deleted'), color: 'success' })
      return true
    } catch (error) {
      console.error('Error deleting clinical note:', error)
      return false
    }
  }

  async function linkAttachment(input: NoteAttachmentCreate): Promise<NoteAttachment | null> {
    try {
      const response = await api.post<ApiResponse<NoteAttachment>>(
        '/api/v1/clinical_notes/attachments',
        input
      )
      return response.data
    } catch (error) {
      console.error('Error linking attachment:', error)
      return null
    }
  }

  async function unlinkAttachment(attachmentId: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/clinical_notes/attachments/${attachmentId}`)
      return true
    } catch (error) {
      console.error('Error unlinking attachment:', error)
      return false
    }
  }

  async function listAttachments(
    ownerType: AttachmentOwnerType,
    ownerId: string
  ): Promise<NoteAttachment[]> {
    const qs = new URLSearchParams({ owner_type: ownerType, owner_id: ownerId })
    const response = await api.get<ApiResponse<NoteAttachment[]>>(
      `/api/v1/clinical_notes/attachments?${qs}`
    )
    return response.data
  }

  return {
    loading,
    listForOwner,
    listRecentForPatient,
    listMergedForPlan,
    listGroupedForPatient,
    listTemplates,
    createNote,
    updateNote,
    deleteNote,
    linkAttachment,
    unlinkAttachment,
    listAttachments
  }
}
