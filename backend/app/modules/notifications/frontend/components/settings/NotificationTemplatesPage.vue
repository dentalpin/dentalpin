<script setup lang="ts">
import DOMPurify from 'isomorphic-dompurify'
import { PERMISSIONS } from '~~/app/config/permissions'
import type { ApiResponse } from '~~/app/types'
import { useNotificationSettings } from '../../composables/useNotificationSettings'
import { communicationLanguages } from '../../utils/communicationLanguages'

type Channel = 'email' | 'whatsapp' | 'sms' | 'push'
type Field = 'subject' | 'body_html' | 'body_text'
type Copy = Record<Field, string | null>
type Variable = { key: string, example: string | number | object[] | null, optional: boolean }
type Selection = { editable: boolean, current: Copy | null, has_override: boolean, default_locale: string | null, variables: Variable[] }
type ValidationError = { code: string, field: Field, line: number, variable?: string }

const { t, locale: uiLocale } = useI18n()
const api = useApi()
const { can } = usePermissions()
const { notificationTypes } = useNotificationSettings()

const label = (key: string, values: Record<string, string | number> = {}) => t(`notifications.templateEditor.${key}`, values)
const channels = computed(() => (['email', 'whatsapp', 'sms', 'push'] as const).map(value => (
  { label: label(`channel.${value}`), value }
)))
const types = computed(() => notificationTypes.value.map(type => ({ label: type.label, value: type.key })))
const channel = ref<Channel>('email')
const type = ref('appointment_confirmation')
const language = ref(communicationLanguages.find(item => item.value === uiLocale.value)?.value ?? 'es')
const path = computed(() => `/api/v1/notifications/templates/editor/${type.value}`)
const query = computed(() => ({ channel: channel.value, locale: language.value }))

const selection = shallowRef<Selection>()
const emptyCopy = (): Copy => ({ subject: null, body_html: null, body_text: null })
const form = ref<Copy>(emptyCopy())
const preview = shallowRef<Copy>()
const loadError = ref(false)
const error = ref('')
const validation = ref<ValidationError>()
const notice = ref('')
const showRestore = ref(false)
const minimal = ref(false)
const pending = ref<'load' | 'preview' | 'save' | 'restore'>()
const dirty = computed(() => JSON.stringify(form.value) !== JSON.stringify(selection.value?.current ?? emptyCopy()))
const canEdit = computed(() => selection.value?.editable && can(PERMISSIONS.notifications.templatesWrite))
const fields = computed<Field[]>(() => channel.value === 'email' ? ['subject', 'body_html', 'body_text'] : ['body_text'])
const required = computed<Field>(() => channel.value === 'email' ? 'body_html' : 'body_text')
let focusedField: { field: Field, element: HTMLInputElement | HTMLTextAreaElement } | undefined

// The preview is never inserted into the app DOM. Remove navigational and
// resource-bearing attributes, then isolate the rendered document.
const previewDocument = computed(() => {
  if (!preview.value?.body_html) return ''
  const sanitized = DOMPurify.sanitize(preview.value.body_html, {
    WHOLE_DOCUMENT: true,
    ADD_TAGS: ['style'],
    FORBID_TAGS: ['meta', 'base', 'link', 'iframe', 'object', 'embed', 'form'],
    FORBID_ATTR: ['href', 'src', 'srcset', 'poster', 'action', 'formaction']
  })
  const policy = '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; form-action \'none\'; base-uri \'none\'">'
  return sanitized.replace(/<head[^>]*>/i, head => head + policy)
})

function choose(set: () => void) {
  if (!dirty.value || window.confirm(label('discard'))) set()
}

function showError(problem: unknown) {
  const detail = (problem as { data?: { detail?: ValidationError } })?.data?.detail
  if (detail?.field && detail.code) {
    validation.value = detail
  } else {
    error.value = label('requestError')
  }
}

function fieldError(field: Field) {
  const issue = validation.value
  if (!issue || issue.field !== field) return undefined
  return label(`errors.${issue.code}`, { line: issue.line, variable: issue.variable ?? '' })
}

async function render(draft = false, useDefault = false) {
  preview.value = undefined
  const { data } = await api.post<ApiResponse<Copy>>(`${path.value}/preview`, {
    content: draft ? form.value : null,
    use_default: useDefault,
    minimal: minimal.value
  }, { query: query.value, errorToast: false })
  preview.value = data
}

async function load() {
  pending.value = 'load'
  loadError.value = false
  showRestore.value = false
  notice.value = ''
  error.value = ''
  validation.value = undefined
  selection.value = undefined
  preview.value = undefined
  form.value = emptyCopy()
  focusedField = undefined
  try {
    const { data } = await api.get<ApiResponse<Selection>>(path.value, { query: query.value })
    selection.value = data
    form.value = { ...(data.current ?? emptyCopy()) }
    try {
      await render()
    } catch (problem) {
      showError(problem)
    }
  } catch {
    loadError.value = true
  } finally {
    pending.value = undefined
  }
}

async function previewDraft(useDefault = false) {
  pending.value = 'preview'
  validation.value = undefined
  error.value = ''
  try {
    await render(canEdit.value && dirty.value && !useDefault, useDefault)
  } catch (problem) {
    showError(problem)
  } finally {
    pending.value = undefined
  }
}

async function write(restore: boolean) {
  pending.value = restore ? 'restore' : 'save'
  validation.value = undefined
  notice.value = ''
  error.value = ''
  try {
    if (restore) {
      await api.del(path.value, { query: query.value, errorToast: false })
    } else {
      await api.put(path.value, form.value, { query: query.value, errorToast: false })
    }
    await load()
    if (!loadError.value) notice.value = label(restore ? 'restored' : 'saved')
  } catch (problem) {
    showError(problem)
  } finally {
    pending.value = undefined
  }
}

function focusField(field: Field, event: FocusEvent) {
  const element = event.target
  if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
    focusedField = { field, element }
  }
}

function insertVariable(key: string) {
  const marker = `{{ ${key} }}`
  const field = focusedField?.field ?? required.value
  const element = focusedField?.element
  const text = form.value[field] ?? ''
  const start = element?.selectionStart ?? text.length
  const end = element?.selectionEnd ?? start
  form.value[field] = text.slice(0, start) + marker + text.slice(end)
  if (element) void nextTick(() => {
    element.focus()
    element.setSelectionRange(start + marker.length, start + marker.length)
  })
}

function setField(field: Field, value: string) {
  form.value[field] = value || null
  validation.value = undefined
  notice.value = ''
}

watch([type, channel, language], load)
onMounted(load)
</script>

<template>
  <div class="space-y-5">
    <div class="grid gap-3 sm:grid-cols-3">
      <UFormField :label="label('type')">
        <USelect
          :model-value="type"
          :items="types"
          :disabled="!!pending"
          class="w-full"
          @update:model-value="value => choose(() => { type = value })"
        />
      </UFormField>
      <UFormField :label="label('channelLabel')">
        <USelect
          :model-value="channel"
          :items="channels"
          :disabled="!!pending"
          class="w-full"
          @update:model-value="value => choose(() => { channel = value })"
        />
      </UFormField>
      <UFormField :label="label('language')">
        <USelect
          :model-value="language"
          :items="communicationLanguages"
          :disabled="!!pending"
          class="w-full"
          @update:model-value="value => choose(() => { language = value })"
        />
      </UFormField>
    </div>

    <div
      v-if="loadError"
      class="space-y-3"
    >
      <UAlert
        color="error"
        variant="soft"
        :title="label('requestError')"
      />
      <UButton
        variant="outline"
        icon="i-lucide-rotate-ccw"
        :label="label('retry')"
        @click="load"
      />
    </div>
    <USkeleton
      v-else-if="!selection"
      class="h-64 w-full"
    />

    <div
      v-else
      class="grid items-start gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]"
    >
      <UCard>
        <template #header>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 class="text-base font-semibold">
              {{ label('content') }}
            </h2>
            <UBadge
              :color="selection.has_override ? 'primary' : 'neutral'"
              variant="soft"
            >
              {{ label(selection.has_override ? 'custom' : selection.default_locale ? 'system' : 'noSystem') }}
            </UBadge>
          </div>
        </template>

        <div class="space-y-4">
          <p
            v-if="!selection.editable"
            class="text-sm text-muted"
          >
            {{ label(channel === 'whatsapp' ? 'manualOnly' : 'readOnlyChannel') }}
          </p>
          <p
            v-else-if="!canEdit"
            class="text-sm text-muted"
          >
            {{ label('readOnlyPermission') }}
          </p>
          <p
            v-else-if="!selection.has_override && selection.default_locale"
            class="text-sm text-muted"
          >
            {{ label('overrideHint') }}
          </p>

          <div
            v-if="canEdit"
            class="space-y-3"
          >
            <UFormField
              v-for="field in fields"
              :key="field"
              :label="label(`field.${field}`)"
              :error="fieldError(field)"
              :required="field === required"
              @focusin="focusField(field, $event)"
            >
              <UInput
                v-if="field === 'subject'"
                :model-value="form[field] ?? ''"
                :maxlength="255"
                :disabled="!!pending"
                class="w-full"
                @update:model-value="setField(field, $event)"
              />
              <UTextarea
                v-else
                :model-value="form[field] ?? ''"
                :rows="field === required ? 7 : 3"
                :maxlength="24000"
                :disabled="!!pending"
                class="w-full"
                :ui="{ base: 'font-mono text-sm' }"
                @update:model-value="setField(field, $event)"
              />
            </UFormField>
          </div>

          <UAlert
            v-if="error || (!canEdit && validation)"
            color="error"
            variant="soft"
            :title="error || label('requestError')"
          />
          <p
            v-if="notice"
            role="status"
            class="text-sm text-success"
          >
            {{ notice }}
          </p>

          <div
            v-if="canEdit"
            class="flex flex-wrap items-center gap-2"
          >
            <UButton
              color="primary"
              variant="solid"
              icon="i-lucide-save"
              :label="t('common.save')"
              :loading="pending === 'save'"
              :disabled="!dirty || !form[required]?.trim() || !!pending"
              @click="write(false)"
            />
            <UButton
              v-if="selection.has_override && !showRestore"
              color="neutral"
              variant="ghost"
              :label="label('restore')"
              :disabled="!!pending"
              @click="showRestore = true"
            />
          </div>
          <div
            v-if="canEdit && showRestore"
            class="space-y-2 rounded-md border border-default p-3"
          >
            <p class="text-sm">
              {{ label(selection.default_locale ? 'restoreConfirm' : 'restoreWithoutDefault') }}
            </p>
            <div class="flex flex-wrap gap-2">
              <UButton
                color="warning"
                variant="soft"
                :label="label('restore')"
                :loading="pending === 'restore'"
                :disabled="!!pending"
                @click="write(true)"
              />
              <UButton
                color="neutral"
                variant="ghost"
                :label="t('common.cancel')"
                :disabled="!!pending"
                @click="showRestore = false"
              />
            </div>
          </div>
        </div>
      </UCard>

      <div class="min-w-0 space-y-5">
        <UCard>
          <template #header>
            <div class="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h2 class="text-base font-semibold">
                  {{ label('preview') }}
                </h2>
                <p class="mt-1 text-sm text-muted">
                  {{ label('sampleOnly') }}
                </p>
              </div>
              <UButton
                variant="outline"
                icon="i-lucide-eye"
                :label="label('refreshPreview')"
                :loading="pending === 'preview'"
                :disabled="!!pending"
                @click="previewDraft()"
              />
            </div>
          </template>
          <p
            v-if="!selection.has_override && selection.default_locale && selection.default_locale !== language"
            class="mb-3 text-sm text-muted"
          >
            {{ label('fallbackLocale', { language: communicationLanguages.find(item => item.value === selection?.default_locale)?.label ?? selection.default_locale }) }}
          </p>
          <div
            v-if="preview?.subject || preview?.body_html || preview?.body_text"
            class="space-y-3"
          >
            <p
              v-if="preview.subject"
              class="text-sm font-semibold"
            >
              {{ preview.subject }}
            </p>
            <iframe
              v-if="previewDocument"
              :title="label('preview')"
              :srcdoc="previewDocument"
              sandbox=""
              referrerpolicy="no-referrer"
              tabindex="-1"
              class="pointer-events-none h-72 w-full rounded-md border border-default bg-white"
            />
            <p
              v-if="preview.body_text"
              class="whitespace-pre-wrap break-words rounded-md bg-elevated p-3 text-sm"
            >
              {{ preview.body_text }}
            </p>
          </div>
          <USkeleton
            v-else-if="pending"
            class="h-24 w-full"
          />
          <p
            v-else
            class="text-sm text-muted"
          >
            {{ label('noPreview') }}
          </p>

          <div
            v-if="selection.variables.some(variable => variable.optional) || (selection.has_override && selection.default_locale)"
            class="mt-4 flex flex-wrap items-center justify-between gap-2"
          >
            <UCheckbox
              v-if="selection.variables.some(variable => variable.optional)"
              v-model="minimal"
              :label="label('omitOptional')"
              :disabled="!!pending"
            />
            <UButton
              v-if="selection.has_override && selection.default_locale"
              color="neutral"
              variant="ghost"
              :label="label('previewDefault')"
              :disabled="!!pending"
              @click="previewDraft(true)"
            />
          </div>
        </UCard>

        <UCard v-if="selection.variables.length">
          <template #header>
            <h2 class="text-base font-semibold">
              {{ label('variables') }}
            </h2>
          </template>
          <ul class="divide-y divide-default">
            <li
              v-for="variable in selection.variables"
              :key="variable.key"
              class="flex flex-wrap items-center justify-between gap-2 py-2 first:pt-0 last:pb-0"
            >
              <div class="min-w-0">
                <p class="text-sm">
                  {{ label(`variable.${variable.key}`) }}
                  <span
                    v-if="variable.optional"
                    class="text-xs text-muted"
                  > · {{ label('optional') }}</span>
                </p>
                <p class="truncate text-xs text-muted">
                  {{ Array.isArray(variable.example) ? label('exampleList') : variable.example }}
                </p>
              </div>
              <UButton
                v-if="canEdit"
                size="xs"
                color="neutral"
                variant="soft"
                icon="i-lucide-plus"
                :label="variable.key"
                :aria-label="label('insert', { variable: variable.key })"
                :disabled="!!pending"
                class="font-mono"
                @click="insertVariable(variable.key)"
              />
              <code
                v-else
                class="text-xs"
              >{{ variable.key }}</code>
            </li>
          </ul>
        </UCard>
      </div>
    </div>
  </div>
</template>
