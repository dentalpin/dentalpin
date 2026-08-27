import type {
  ApiResponse,
  CompleteItemRequest,
  GenerateBudgetResponse,
  LinkBudgetRequest,
  PaginatedResponse,
  PlannedTreatmentItem,
  PlannedTreatmentItemCreate,
  PlannedTreatmentItemUpdate,
  TreatmentPlan,
  TreatmentPlanCreate,
  TreatmentPlanDetail,
  TreatmentPlanStatusUpdate,
  TreatmentPlanUpdate
} from '~~/app/types'

/**
 * Price the patient actually pays for a plan item: the sum of its
 * non-cancelled sessions (sessions are repriced to the accepted quote,
 * see backend `TreatmentPlanService._reprice_sessions`). Falls back to
 * the catalog snapshot when the item has no live sessions.
 */
export function itemEffectivePrice(item: PlannedTreatmentItem): number | undefined {
  const live = (item.sessions ?? []).filter(s => s.status !== 'cancelled')
  if (live.length > 0) {
    return live.reduce((acc, s) => acc + (Number(s.amount) || 0), 0)
  }
  return itemCatalogPrice(item)
}

/** Catalog price at planning time; shown struck through when the quote discounted it. */
export function itemCatalogPrice(item: PlannedTreatmentItem): number | undefined {
  const snap = item.treatment?.price_snapshot
  if (snap == null || snap === '') return undefined
  const parsed = Number(snap)
  return Number.isFinite(parsed) ? parsed : undefined
}

export function useTreatmentPlans() {
  const api = useApi()
  const toast = useToast()
  const { t } = useI18n()

  // State
  const plans = ref<TreatmentPlan[]>([])
  const currentPlan = ref<TreatmentPlanDetail | null>(null)
  const loading = ref(false)
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)

  // Fetch plans list
  async function fetchPlans(options: {
    patient_id?: string
    status?: string | string[]
    search?: string
    page?: number
    page_size?: number
  } = {}) {
    loading.value = true
    try {
      const params = new URLSearchParams()
      params.append('page', String(options.page || 1))
      params.append('page_size', String(options.page_size || 20))
      if (options.patient_id) params.append('patient_id', options.patient_id)
      if (options.status) {
        const statuses = Array.isArray(options.status) ? options.status : [options.status]
        statuses.forEach(s => params.append('status', s))
      }
      if (options.search) params.append('search', options.search)

      const response = await api.get<PaginatedResponse<TreatmentPlan>>(
        `/api/v1/treatment_plan/treatment-plans?${params}`
      )
      plans.value = response.data
      total.value = response.total
      page.value = response.page
      pageSize.value = response.page_size
    } catch (error) {
      console.error('Error fetching treatment plans:', error)
      toast.add({
        title: t('errors.loadFailed'),
        color: 'error'
      })
    } finally {
      loading.value = false
    }
  }

  // Fetch plans for a specific patient
  async function fetchPatientPlans(patientId: string) {
    return fetchPlans({ patient_id: patientId })
  }

  // Fetch single plan with details
  async function fetchPlan(planId: string) {
    loading.value = true
    try {
      const response = await api.get<ApiResponse<TreatmentPlanDetail>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}`
      )
      currentPlan.value = response.data
      return response.data
    } catch (error) {
      console.error('Error fetching treatment plan:', error)
      toast.add({
        title: t('errors.loadFailed'),
        color: 'error'
      })
      return null
    } finally {
      loading.value = false
    }
  }

  // Create plan
  async function createPlan(data: TreatmentPlanCreate) {
    loading.value = true
    try {
      const response = await api.post<ApiResponse<TreatmentPlan>>(
        '/api/v1/treatment_plan/treatment-plans',
        data
      )
      toast.add({
        title: t('treatmentPlans.created'),
        color: 'success'
      })
      return response.data
    } catch (error) {
      console.error('Error creating treatment plan:', error)
      toast.add({
        title: t('errors.createFailed'),
        color: 'error'
      })
      return null
    } finally {
      loading.value = false
    }
  }

  // Update plan
  async function updatePlan(planId: string, data: TreatmentPlanUpdate) {
    loading.value = true
    try {
      const response = await api.put<ApiResponse<TreatmentPlan>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}`,
        data
      )
      if (currentPlan.value?.id === planId) {
        currentPlan.value = { ...currentPlan.value, ...response.data }
      }
      toast.add({
        title: t('treatmentPlans.updated'),
        color: 'success'
      })
      return response.data
    } catch (error) {
      console.error('Error updating treatment plan:', error)
      toast.add({
        title: t('errors.updateFailed'),
        color: 'error'
      })
      return null
    } finally {
      loading.value = false
    }
  }

  // Update plan status
  async function updatePlanStatus(planId: string, data: TreatmentPlanStatusUpdate) {
    loading.value = true
    try {
      const response = await api.patch<ApiResponse<TreatmentPlan>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/status`,
        data
      )
      if (currentPlan.value?.id === planId) {
        currentPlan.value = { ...currentPlan.value, ...response.data }
      }
      toast.add({
        title: t('treatmentPlans.statusUpdated'),
        color: 'success'
      })
      return response.data
    } catch (error) {
      console.error('Error updating plan status:', error)
      toast.add({
        title: t('errors.updateFailed'),
        color: 'error'
      })
      return null
    } finally {
      loading.value = false
    }
  }

  // Delete plan
  async function deletePlan(planId: string) {
    loading.value = true
    try {
      await api.del(`/api/v1/treatment_plan/treatment-plans/${planId}`)
      plans.value = plans.value.filter(p => p.id !== planId)
      if (currentPlan.value?.id === planId) {
        currentPlan.value = null
      }
      toast.add({
        title: t('treatmentPlans.deleted'),
        color: 'success'
      })
      return true
    } catch (error) {
      console.error('Error deleting treatment plan:', error)
      toast.add({
        title: t('errors.deleteFailed'),
        color: 'error'
      })
      return false
    } finally {
      loading.value = false
    }
  }

  // Add item to plan
  async function addItem(planId: string, data: PlannedTreatmentItemCreate) {
    loading.value = true
    try {
      const response = await api.post<ApiResponse<PlannedTreatmentItem>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/items`,
        data
      )
      if (currentPlan.value?.id === planId) {
        currentPlan.value.items.push(response.data)
      }
      return response.data
    } catch (error) {
      console.error('Error adding treatment item:', error)
      toast.add({
        title: t('errors.createFailed'),
        color: 'error'
      })
      return null
    } finally {
      loading.value = false
    }
  }

  // Update item
  async function updateItem(
    planId: string,
    itemId: string,
    data: PlannedTreatmentItemUpdate
  ) {
    loading.value = true
    try {
      const response = await api.put<ApiResponse<PlannedTreatmentItem>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/items/${itemId}`,
        data
      )
      if (currentPlan.value?.id === planId) {
        const idx = currentPlan.value.items.findIndex(i => i.id === itemId)
        if (idx !== -1) {
          currentPlan.value.items[idx] = response.data
        }
      }
      return response.data
    } catch (error) {
      console.error('Error updating treatment item:', error)
      toast.add({
        title: t('errors.updateFailed'),
        color: 'error'
      })
      return null
    } finally {
      loading.value = false
    }
  }

  // Change the doctor assigned to a single item. ``null`` clears the override
  // (server-side that becomes "no doctor assigned to this item").
  async function changeItemDoctor(
    planId: string,
    itemId: string,
    professionalId: string | null
  ) {
    return await updateItem(planId, itemId, {
      assigned_professional_id: professionalId
    })
  }

  // Remove item
  async function removeItem(planId: string, itemId: string) {
    loading.value = true
    try {
      await api.del(
        `/api/v1/treatment_plan/treatment-plans/${planId}/items/${itemId}`
      )
      if (currentPlan.value?.id === planId) {
        currentPlan.value.items = currentPlan.value.items.filter(
          i => i.id !== itemId
        )
      }
      return true
    } catch (error) {
      console.error('Error removing treatment item:', error)
      toast.add({
        title: t('errors.deleteFailed'),
        color: 'error'
      })
      return false
    } finally {
      loading.value = false
    }
  }

  // Reorder items (optimistic)
  async function reorderItems(
    planId: string,
    itemIds: string[]
  ): Promise<TreatmentPlanDetail | null> {
    if (currentPlan.value?.id !== planId) {
      console.error('reorderItems: plan not currently loaded')
      return null
    }
    const snapshot = [...currentPlan.value.items]
    const indexById = new Map(itemIds.map((id, i) => [id, i]))
    currentPlan.value.items = [...snapshot].sort((a, b) => {
      const ia = indexById.get(a.id) ?? Number.MAX_SAFE_INTEGER
      const ib = indexById.get(b.id) ?? Number.MAX_SAFE_INTEGER
      return ia - ib
    })

    try {
      const response = await api.patch<ApiResponse<TreatmentPlanDetail>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/items/reorder`,
        { item_ids: itemIds }
      )
      currentPlan.value = response.data
      return response.data
    } catch (error) {
      console.error('Error reordering treatment items:', error)
      if (currentPlan.value?.id === planId) {
        currentPlan.value.items = snapshot
      }
      toast.add({
        title: t('errors.updateFailed'),
        color: 'error'
      })
      return null
    }
  }

  // Complete item
  async function completeItem(
    planId: string,
    itemId: string,
    data: CompleteItemRequest = {}
  ) {
    loading.value = true
    try {
      const response = await api.patch<ApiResponse<PlannedTreatmentItem>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/items/${itemId}/complete`,
        data
      )
      if (currentPlan.value?.id === planId) {
        const idx = currentPlan.value.items.findIndex(i => i.id === itemId)
        if (idx !== -1) {
          currentPlan.value.items[idx] = response.data
        }
      }
      toast.add({
        title: t('treatmentPlans.itemCompleted'),
        color: 'success'
      })
      return response.data
    } catch (error) {
      console.error('Error completing treatment item:', error)
      toast.add({
        title: t('errors.updateFailed'),
        color: 'error'
      })
      return null
    } finally {
      loading.value = false
    }
  }

  async function completeSession(
    planId: string,
    itemId: string,
    sessionId: string,
    payload: { notes?: string, completed_without_appointment?: boolean } = {}
  ) {
    loading.value = true
    try {
      const response = await api.patch<ApiResponse<PlannedTreatmentItem>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/items/${itemId}/sessions/${sessionId}/complete`,
        payload
      )
      if (currentPlan.value?.id === planId) {
        const idx = currentPlan.value.items.findIndex(i => i.id === itemId)
        if (idx !== -1) {
          currentPlan.value.items[idx] = response.data
        }
      }
      toast.add({ title: t('clinical.plans.sessions.markedDone'), color: 'success' })
      return response.data
    } catch (error) {
      console.error('Error completing session:', error)
      toast.add({ title: t('errors.updateFailed'), color: 'error' })
      return null
    } finally {
      loading.value = false
    }
  }

  async function cancelSession(
    planId: string,
    itemId: string,
    sessionId: string,
    payload: { notes?: string } = {}
  ) {
    loading.value = true
    try {
      const response = await api.patch<ApiResponse<PlannedTreatmentItem>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/items/${itemId}/sessions/${sessionId}/cancel`,
        payload
      )
      if (currentPlan.value?.id === planId) {
        const idx = currentPlan.value.items.findIndex(i => i.id === itemId)
        if (idx !== -1) {
          currentPlan.value.items[idx] = response.data
        }
      }
      toast.add({ title: t('clinical.plans.sessions.cancelled'), color: 'warning' })
      return response.data
    } catch (error) {
      console.error('Error cancelling session:', error)
      toast.add({ title: t('errors.updateFailed'), color: 'error' })
      return null
    } finally {
      loading.value = false
    }
  }

  // Link budget
  async function linkToBudget(planId: string, data: LinkBudgetRequest) {
    loading.value = true
    try {
      const response = await api.post<ApiResponse<TreatmentPlan>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/link-budget`,
        data
      )
      if (currentPlan.value?.id === planId) {
        currentPlan.value = { ...currentPlan.value, ...response.data }
      }
      toast.add({
        title: t('treatmentPlans.budgetLinked'),
        color: 'success'
      })
      return response.data
    } catch (error) {
      console.error('Error linking budget:', error)
      toast.add({
        title: t('errors.updateFailed'),
        color: 'error'
      })
      return null
    } finally {
      loading.value = false
    }
  }

  // Sync budget
  async function syncBudget(planId: string) {
    loading.value = true
    try {
      await api.post<ApiResponse<{ synced: boolean }>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/sync-budget`
      )
      toast.add({
        title: t('treatmentPlans.budgetSynced'),
        color: 'success'
      })
      return true
    } catch (error) {
      console.error('Error syncing budget:', error)
      toast.add({
        title: t('errors.updateFailed'),
        color: 'error'
      })
      return false
    } finally {
      loading.value = false
    }
  }

  // Generate budget from plan
  async function generateBudget(planId: string) {
    loading.value = true
    try {
      const response = await api.post<ApiResponse<GenerateBudgetResponse>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/generate-budget`
      )
      if (currentPlan.value?.id === planId) {
        currentPlan.value.budget_id = response.data.budget_id
      }
      toast.add({
        title: t('treatmentPlans.budgetGenerated'),
        color: 'success'
      })
      return response.data
    } catch (error) {
      console.error('Error generating budget:', error)
      toast.add({
        title: t('errors.createFailed'),
        color: 'error'
      })
      return null
    } finally {
      loading.value = false
    }
  }

  // ---------------------------------------------------------------------
  // Workflow transitions (confirm / reopen / close / reactivate)
  // ---------------------------------------------------------------------

  // Workflow transitions intentionally DO NOT mutate ``currentPlan`` —
  // the page handler always follows the action with a full
  // ``fetchPlan`` so the UI reflects the canonical server state
  // (including budget_id, items[], confirmed_at, closure metadata,
  // etc.). Local merges from the action response had race conditions
  // because the ``TreatmentPlan`` schema returned here lacks ``items``.

  async function confirmPlan(planId: string) {
    loading.value = true
    try {
      const response = await api.post<ApiResponse<TreatmentPlan>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/confirm`
      )
      // Confirming provisions a draft quote — link straight to it from
      // the toast so reception doesn't have to dig it out of the
      // budgets list (#207).
      const budgetId = response.data?.budget_id
      toast.add({
        title: t('treatmentPlans.confirmed'),
        color: 'success',
        ...(budgetId
          ? { actions: [{ label: t('clinical.plans.locked.viewBudget'), onClick: () => { navigateTo(`/budgets/${budgetId}`) } }] }
          : {})
      })
      return response.data
    } catch (error) {
      console.error('Error confirming plan:', error)
      toast.add({ title: t('errors.updateFailed'), color: 'error' })
      return null
    } finally {
      loading.value = false
    }
  }

  async function reopenPlan(planId: string) {
    loading.value = true
    try {
      const response = await api.post<ApiResponse<TreatmentPlan>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/reopen`
      )
      toast.add({ title: t('treatmentPlans.reopened'), color: 'success' })
      return response.data
    } catch (error) {
      console.error('Error reopening plan:', error)
      toast.add({ title: t('errors.updateFailed'), color: 'error' })
      return null
    } finally {
      loading.value = false
    }
  }

  async function closePlan(
    planId: string,
    payload: { closure_reason: string, closure_note?: string }
  ) {
    loading.value = true
    try {
      const response = await api.post<ApiResponse<TreatmentPlan>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/close`,
        payload
      )
      toast.add({ title: t('treatmentPlans.closed'), color: 'success' })
      return response.data
    } catch (error) {
      console.error('Error closing plan:', error)
      toast.add({ title: t('errors.updateFailed'), color: 'error' })
      return null
    } finally {
      loading.value = false
    }
  }

  async function reactivatePlan(planId: string) {
    loading.value = true
    try {
      const response = await api.post<ApiResponse<TreatmentPlan>>(
        `/api/v1/treatment_plan/treatment-plans/${planId}/reactivate`
      )
      toast.add({ title: t('treatmentPlans.reactivated'), color: 'success' })
      return response.data
    } catch (error) {
      console.error('Error reactivating plan:', error)
      toast.add({ title: t('errors.updateFailed'), color: 'error' })
      return null
    } finally {
      loading.value = false
    }
  }

  async function logContact(
    planId: string,
    payload: { channel: string, note?: string }
  ) {
    try {
      await api.post(
        `/api/v1/treatment_plan/treatment-plans/${planId}/contact-log`,
        payload
      )
      toast.add({ title: t('treatmentPlans.contactLogged'), color: 'success' })
      return true
    } catch (error) {
      console.error('Error logging contact:', error)
      toast.add({ title: t('errors.updateFailed'), color: 'error' })
      return false
    }
  }

  /**
   * Fetch pending items for a patient from all schedulable plans.
   * Used in appointment modal to select which treatments to schedule.
   *
   * `pending` (plan confirmed, budget not yet accepted) is included on
   * purpose: an unconfirmed draft is schedulable, so confirming a plan
   * must not take that away — clinics book the first visit while the
   * patient is still deciding (#108).
   */
  async function fetchPatientPendingItems(patientId: string): Promise<PlannedTreatmentItem[]> {
    try {
      const params = new URLSearchParams()
      params.append('patient_id', patientId)
      params.append('status', 'active')
      params.append('status', 'draft')
      params.append('status', 'pending')
      params.append('page_size', '100')

      const response = await api.get<PaginatedResponse<TreatmentPlan>>(
        `/api/v1/treatment_plan/treatment-plans?${params}`
      )

      // For each plan, fetch full details to get items
      const allPendingItems: PlannedTreatmentItem[] = []

      for (const plan of response.data) {
        const detailResponse = await api.get<ApiResponse<TreatmentPlanDetail>>(
          `/api/v1/treatment_plan/treatment-plans/${plan.id}`
        )
        if (detailResponse.data?.items) {
          // Filter to pending items only and attach plan info
          const pendingItems = detailResponse.data.items
            .filter(item => item.status === 'pending')
            .map(item => ({
              ...item,
              treatment_plan: {
                id: plan.id,
                plan_number: plan.plan_number,
                title: plan.title,
                status: plan.status
              }
            }))
          allPendingItems.push(...pendingItems)
        }
      }

      return allPendingItems
    } catch (error) {
      console.error('Error fetching patient pending items:', error)
      return []
    }
  }

  return {
    // State
    plans,
    currentPlan,
    loading,
    total,
    page,
    pageSize,

    // Plan operations
    fetchPlans,
    fetchPatientPlans,
    fetchPlan,
    createPlan,
    updatePlan,
    updatePlanStatus,
    deletePlan,

    // Item operations
    addItem,
    updateItem,
    removeItem,
    reorderItems,
    completeItem,
    completeSession,
    cancelSession,
    changeItemDoctor,

    // Workflow transitions
    confirmPlan,
    reopenPlan,
    closePlan,
    reactivatePlan,
    logContact,

    // Budget operations
    linkToBudget,
    syncBudget,
    generateBudget,

    // Appointment integration
    fetchPatientPendingItems
  }
}
