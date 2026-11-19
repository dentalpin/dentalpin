import { flushPromises, mount } from '@vue/test-utils'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { beforeEach, expect, it, vi } from 'vitest'
import type { MfaChallenge } from '~/composables/useMfa'
import MfaChallengeForm from '~/components/auth/MfaChallengeForm.vue'

const { request } = vi.hoisted(() => ({ request: vi.fn() }))
mockNuxtImport('useMfa', () => () => ({ request, message: () => 'Invalid code' }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key }))

const challenge: MfaChallenge = {
  mfa_required: true,
  mfa_token: 'synthetic-challenge',
  mode: 'verify',
  secret: null,
  qr_code: null
}

const stubs = {
  UFormField: { template: '<label><slot /></label>' },
  UButton: { template: '<button><slot /></button>' },
  UInput: {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: `<input :value="modelValue" @input="$emit('update:modelValue', $event.target.value)">`
  }
}

beforeEach(() => request.mockReset())

it('completes sign-in only after verifying a code', async () => {
  request.mockRejectedValueOnce(new Error('invalid')).mockResolvedValueOnce({ recovery_codes: null })
  const wrapper = mount(MfaChallengeForm, { props: { challenge }, global: { stubs } })
  await wrapper.get('input').setValue('012345')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(wrapper.get('[role="alert"]').text()).toBe('Invalid code')
  expect(wrapper.emitted('verified')).toBeUndefined()
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(request).toHaveBeenLastCalledWith(
    'mfa/verify', 'POST', { mfa_token: challenge.mfa_token, code: '012345' }
  )
  expect(wrapper.emitted('verified')).toHaveLength(1)
  wrapper.unmount()
})

it('prompts staff to save recovery codes after confirming enrollment', async () => {
  request.mockResolvedValue({ recovery_codes: ['synthetic-recovery-code'] })
  const wrapper = mount(MfaChallengeForm, {
    props: { challenge: { ...challenge, mode: 'enroll' }, selfEnrollment: true },
    global: { stubs }
  })
  await wrapper.findAll('input')[1]!.setValue('012345')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
  expect(request).toHaveBeenLastCalledWith(
    'mfa/totp/confirm', 'POST', { mfa_token: challenge.mfa_token, code: '012345' }
  )
  expect(wrapper.text()).toContain('synthetic-recovery-code')
  expect(wrapper.emitted('verified')).toBeUndefined()
  await wrapper.get('button').trigger('click')
  expect(wrapper.text()).not.toContain('synthetic-recovery-code')
  expect(wrapper.emitted('verified')).toHaveLength(1)
  wrapper.unmount()
})
