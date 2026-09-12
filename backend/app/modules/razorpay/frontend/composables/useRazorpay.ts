import type { ApiResponse } from '~~/app/types'

export interface RazorpaySettings {
  mode: 'test' | 'live'
  key_id: string | null
  has_key_secret: boolean
  has_webhook_secret: boolean
  is_active: boolean
  is_verified: boolean
  last_verified_at: string | null
  last_webhook_received_at: string | null
  last_webhook_processed_at: string | null
  last_webhook_event_type: string | null
  last_webhook_error: string | null
  last_webhook_error_at: string | null
}

export interface RazorpaySettingsUpdate {
  mode?: 'test' | 'live'
  key_id?: string
  key_secret?: string
  webhook_secret?: string
  is_active?: boolean
}

export type GatewayMethod = 'upi' | 'qr' | 'card' | 'payment_link'

// Mirrors payment_gateways.constants.PaymentRequestState.
export type PaymentRequestState
  = | 'pending'
    | 'awaiting_customer_action'
    | 'authorised_awaiting_capture'
    | 'succeeded'
    | 'failed'
    | 'expired'
    | 'cancelled'

export type GatewayRefundState = 'requested' | 'processing' | 'completed' | 'failed'

export interface CheckoutInfo {
  redirect_url: string | null
  checkout_payload: Record<string, unknown> | null
  qr_image_url: string | null
  qr_payload: string | null
}

export interface PaymentRequest {
  id: string
  clinic_id: string
  patient_id: string
  provider_key: string
  requested_amount: string
  currency: string
  requested_method: GatewayMethod
  state: PaymentRequestState
  provider_reference: string | null
  provider_payment_reference: string | null
  checkout: CheckoutInfo | null
  expires_at: string | null
  confirmed_at: string | null
  failed_at: string | null
  cancelled_at: string | null
  error_code: string | null
  error_message: string | null
  payment_id: string | null
  created_at: string
}

export interface GatewayRefundRequest {
  id: string
  payment_id: string
  payment_request_id: string
  provider_key: string
  requested_amount: string
  reason_code: string
  reason_note: string | null
  state: GatewayRefundState
  provider_refund_reference: string | null
  refund_id: string | null
  completed_at: string | null
  failed_at: string | null
  error_code: string | null
  error_message: string | null
  created_at: string
}

export interface GatewayInfo {
  request: PaymentRequest | null
  refund_requests: GatewayRefundRequest[]
}

export interface AllocationInput {
  target_type: 'budget' | 'on_account'
  target_id?: string
  amount: number
}

export function useRazorpay() {
  const api = useApi()

  async function getSettings() {
    const res = await api.get<ApiResponse<RazorpaySettings>>('/api/v1/razorpay/settings')
    return res.data
  }

  async function updateSettings(payload: RazorpaySettingsUpdate) {
    const res = await api.put<ApiResponse<RazorpaySettings>>('/api/v1/razorpay/settings', payload)
    return res.data
  }

  async function createPaymentRequest(payload: {
    patient_id: string
    amount: number
    method: GatewayMethod
    allocations: AllocationInput[]
    context?: Record<string, unknown> | null
    idempotency_key?: string
  }) {
    const res = await api.post<ApiResponse<PaymentRequest>>('/api/v1/payment_gateways/requests', {
      ...payload,
      provider_key: 'razorpay'
    })
    return res.data
  }

  async function getPaymentRequest(id: string) {
    const res = await api.get<ApiResponse<PaymentRequest>>(`/api/v1/payment_gateways/requests/${id}`)
    return res.data
  }

  async function refreshPaymentRequest(id: string) {
    const res = await api.post<ApiResponse<PaymentRequest>>(`/api/v1/payment_gateways/requests/${id}/refresh`, {})
    return res.data
  }

  async function cancelPaymentRequest(id: string) {
    const res = await api.post<ApiResponse<PaymentRequest>>(`/api/v1/payment_gateways/requests/${id}/cancel`, {})
    return res.data
  }

  async function getGatewayInfo(paymentId: string) {
    const res = await api.get<ApiResponse<GatewayInfo>>(`/api/v1/payment_gateways/payments/${paymentId}/gateway-info`)
    return res.data
  }

  async function createGatewayRefund(payload: {
    payment_id: string
    amount: number
    reason_code: string
    reason_note?: string | null
  }) {
    const res = await api.post<ApiResponse<GatewayRefundRequest>>('/api/v1/payment_gateways/refunds', payload)
    return res.data
  }

  async function getGatewayRefund(id: string) {
    const res = await api.get<ApiResponse<GatewayRefundRequest>>(`/api/v1/payment_gateways/refunds/${id}`)
    return res.data
  }

  return {
    getSettings,
    updateSettings,
    createPaymentRequest,
    getPaymentRequest,
    refreshPaymentRequest,
    cancelPaymentRequest,
    getGatewayInfo,
    createGatewayRefund,
    getGatewayRefund
  }
}
