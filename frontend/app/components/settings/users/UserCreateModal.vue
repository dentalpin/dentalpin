<script setup lang="ts">
/**
 * Create a clinic user. Password is optional: without one the account is
 * created locked and the modal switches to an "invite link" panel the
 * admin copies / shares (no SMTP needed). Used by the users settings
 * page and as the onboarding "team" mini-modal.
 *
 * Emits `saved` after a successful create; `update:open` to close.
 */
import type { UserCreate, UserRole } from '~/types'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void, (e: 'saved'): void }>()

const { t, locale } = useI18n()
const toast = useToast()
const { availableRoles, createUser, createInviteLink } = useUsers()

const isOpen = computed({
  get: () => props.open,
  set: (v: boolean) => emit('update:open', v)
})

const translatedRoles = computed(() =>
  availableRoles.map(role => ({ value: role.value, label: t(`settings.roles.${role.value}`) }))
)

const PROFESSIONAL_ROLES: UserRole[] = ['dentist', 'hygienist']

const isCreating = ref(false)
const form = ref({ email: '', password: '', first_name: '', last_name: '' })
const role = ref<UserRole>('dentist')
const isProfessional = ref(true)

// The switch follows the role (dentist/hygienist → professional) but the
// admin can override it — a solo admin-dentist ticks it manually.
watch(role, r => (isProfessional.value = PROFESSIONAL_ROLES.includes(r)))

const invite = ref<{ url: string, expiresAt: string, name: string } | null>(null)
const copied = ref(false)

watch(() => props.open, (open) => {
  if (!open) return
  form.value = { email: '', password: '', first_name: '', last_name: '' }
  role.value = 'dentist'
  isProfessional.value = true
  invite.value = null
  copied.value = false
})

async function submit() {
  isCreating.value = true
  const data: UserCreate = {
    email: form.value.email,
    first_name: form.value.first_name,
    last_name: form.value.last_name,
    role: role.value,
    is_professional: isProfessional.value
  }
  if (form.value.password) data.password = form.value.password
  const user = await createUser(data)
  isCreating.value = false
  if (!user) return
  emit('saved')
  if (data.password) {
    isOpen.value = false
    return
  }
  const link = await createInviteLink(user.id)
  if (link) invite.value = { ...link, name: `${form.value.first_name} ${form.value.last_name}`.trim() }
  else isOpen.value = false
}

async function copy() {
  if (!invite.value) return
  try {
    await navigator.clipboard.writeText(invite.value.url)
    copied.value = true
    toast.add({ title: t('settings.invite.copied'), color: 'success' })
  } catch {
    // Clipboard blocked (http / permissions) — the input stays selectable.
  }
}

const whatsappHref = computed(() => {
  if (!invite.value) return '#'
  const text = t('settings.invite.shareText', { name: invite.value.name, url: invite.value.url })
  return `https://wa.me/?text=${encodeURIComponent(text)}`
})

const expiresLabel = computed(() =>
  invite.value ? new Date(invite.value.expiresAt).toLocaleDateString(locale.value) : ''
)
</script>

<template>
  <UModal v-model:open="isOpen">
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              :name="invite ? 'i-lucide-link' : 'i-lucide-user-plus'"
              class="w-5 h-5 text-primary-accent"
            />
            <h3 class="font-semibold text-default">
              {{ invite ? t('settings.invite.linkTitle') : t('settings.createUser') }}
            </h3>
          </div>
        </template>

        <!-- Invite link panel -->
        <div
          v-if="invite"
          class="space-y-4"
        >
          <p class="text-body text-muted">
            {{ t('settings.invite.linkHelp', { name: invite.name, date: expiresLabel }) }}
          </p>
          <UInput
            :model-value="invite.url"
            readonly
            class="w-full"
            :ui="{ base: 'font-mono text-xs' }"
            @focus="($event.target as HTMLInputElement).select()"
          />
          <div class="flex flex-col sm:flex-row gap-2">
            <UButton
              :icon="copied ? 'i-lucide-check' : 'i-lucide-copy'"
              color="primary"
              class="min-h-[44px] justify-center"
              @click="copy"
            >
              {{ copied ? t('settings.invite.copied') : t('settings.invite.copy') }}
            </UButton>
            <UButton
              icon="i-lucide-message-circle"
              color="neutral"
              variant="soft"
              class="min-h-[44px] justify-center"
              :to="whatsappHref"
              target="_blank"
              rel="noopener"
            >
              {{ t('settings.invite.whatsapp') }}
            </UButton>
          </div>
          <p class="text-caption text-subtle">
            {{ t('settings.invite.secretNote') }}
          </p>
          <div class="flex justify-end pt-2">
            <UButton @click="isOpen = false">
              {{ t('common.close') }}
            </UButton>
          </div>
        </div>

        <!-- Create form -->
        <form
          v-else
          method="post"
          class="space-y-4"
          @submit.prevent="submit"
        >
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <UFormField :label="t('common.firstName')">
              <UInput
                v-model="form.first_name"
                class="w-full"
                required
              />
            </UFormField>
            <UFormField :label="t('common.lastName')">
              <UInput
                v-model="form.last_name"
                class="w-full"
                required
              />
            </UFormField>
          </div>

          <UFormField :label="t('common.email')">
            <UInput
              v-model="form.email"
              type="email"
              class="w-full"
              required
            />
          </UFormField>

          <UFormField :label="t('common.role')">
            <USelect
              v-model="role"
              :items="translatedRoles"
              value-key="value"
              label-key="label"
              class="w-full"
              :placeholder="t('placeholders.selectRole')"
            />
          </UFormField>

          <UFormField :help="t('settings.isProfessionalHelp')">
            <div class="flex items-center gap-3 min-h-[44px]">
              <USwitch v-model="isProfessional" />
              <span class="text-sm text-muted">{{ t('settings.isProfessional') }}</span>
            </div>
          </UFormField>

          <UFormField
            :label="t('common.password')"
            :help="t('settings.invite.passwordOptionalHelp')"
          >
            <UInput
              v-model="form.password"
              type="password"
              class="w-full"
              autocomplete="new-password"
              :placeholder="t('settings.invite.passwordOptionalPlaceholder')"
            />
          </UFormField>

          <div class="flex justify-end gap-2 pt-4">
            <UButton
              variant="ghost"
              @click="isOpen = false"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              type="submit"
              :loading="isCreating"
              :icon="form.password ? undefined : 'i-lucide-link'"
            >
              {{ form.password ? t('settings.createUser') : t('settings.invite.createAndLink') }}
            </UButton>
          </div>
        </form>
      </UCard>
    </template>
  </UModal>
</template>
