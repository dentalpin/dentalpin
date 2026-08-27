<script setup lang="ts">
import type { UserRole, UserUpdate } from '~/types'
import type { ClinicUser } from '~/composables/useUsers'

const { t, locale } = useI18n()
const auth = useAuth()
const { isAdmin } = usePermissions()
const { users, isLoading, availableRoles, fetchUsers, createInviteLink, updateUser, deleteUser } = useUsers()

const translatedRoles = computed(() =>
  availableRoles.map(role => ({
    value: role.value,
    label: t(`settings.roles.${role.value}`)
  }))
)

const ROLE_ORDER: Record<UserRole, number> = {
  admin: 0,
  dentist: 1,
  hygienist: 2,
  assistant: 3,
  receptionist: 4
}

const sortedUsers = computed(() => {
  return [...users.value].sort((a, b) => {
    if (a.is_active !== b.is_active) return a.is_active ? -1 : 1
    const ra = ROLE_ORDER[a.role] ?? 99
    const rb = ROLE_ORDER[b.role] ?? 99
    if (ra !== rb) return ra - rb
    const na = `${a.first_name} ${a.last_name}`.toLowerCase()
    const nb = `${b.first_name} ${b.last_name}`.toLowerCase()
    return na.localeCompare(nb)
  })
})

const showCreate = ref(false)

// Admin-issued access link (new accounts without password, or a reset).
const invite = ref<{ user: ClinicUser, url: string, expiresAt: string } | null>(null)
const inviteCopied = ref(false)
async function openInvite(user: ClinicUser) {
  const link = await createInviteLink(user.id)
  if (link) {
    invite.value = { user, ...link }
    inviteCopied.value = false
  }
}
async function copyInvite() {
  if (!invite.value) return
  try {
    await navigator.clipboard.writeText(invite.value.url)
    inviteCopied.value = true
  } catch {
    // Clipboard blocked — the input stays selectable.
  }
}

const showEdit = ref(false)
const isUpdating = ref(false)
const editing = ref<ClinicUser | null>(null)
const editData = ref({ email: '', first_name: '', last_name: '', is_active: true })
const editSelectedRole = ref<UserRole>('receptionist')
const editIsProfessional = ref(false)

// The checkbox follows the role (dentist/hygienist → professional) but
// the user can override it afterwards — that's the whole point: an
// admin who also practises ticks it manually.
const PROFESSIONAL_ROLES: UserRole[] = ['dentist', 'hygienist']
watch(editSelectedRole, (role) => {
  // Only re-derive on an actual role change — not on the deferred
  // firing caused by openEdit() loading the user into the form.
  if (editing.value && role !== editing.value.role) {
    editIsProfessional.value = PROFESSIONAL_ROLES.includes(role)
  }
})

const showDelete = ref(false)
const isDeleting = ref(false)
const toDelete = ref<ClinicUser | null>(null)

// Guided team step: solo practices are the common case, so offer the
// "I attend patients myself" flip inline instead of hiding it behind
// pencil → edit user → toggle. Only while onboarding points here and
// the admin isn't a professional yet.
const route = useRoute()
const selfUser = computed(() => users.value.find(u => isCurrentUser(u.id)) ?? null)
const showSoloPrompt = computed(() =>
  !!route.query.onboarding && !!selfUser.value && !selfUser.value.is_professional
)
const isMarkingSelf = ref(false)
async function markSelfProfessional(value: boolean) {
  if (!value || !selfUser.value || isMarkingSelf.value) return
  isMarkingSelf.value = true
  await updateUser(selfUser.value.id, { is_professional: true })
  isMarkingSelf.value = false
}

onMounted(() => {
  if (isAdmin.value) fetchUsers()
})

watch(isAdmin, (value) => {
  if (value) fetchUsers()
})

function isCurrentUser(userId: string): boolean {
  return auth.user.value?.id === userId
}

type BadgeColor = 'error' | 'primary' | 'secondary' | 'success' | 'info' | 'warning' | 'neutral'

function getRoleBadgeColor(role: UserRole): BadgeColor {
  const colors: Record<UserRole, BadgeColor> = {
    admin: 'error',
    dentist: 'info',
    hygienist: 'success',
    assistant: 'warning',
    receptionist: 'neutral'
  }
  return colors[role] || 'neutral'
}

function getRoleLabel(role: UserRole): string {
  return t(`settings.roles.${role}`)
}

function openCreate() {
  showCreate.value = true
}

function openEdit(user: ClinicUser) {
  editing.value = user
  editData.value = {
    email: user.email,
    first_name: user.first_name,
    last_name: user.last_name,
    is_active: user.is_active
  }
  editSelectedRole.value = user.role
  editIsProfessional.value = user.is_professional
  showEdit.value = true
}

async function handleUpdate() {
  if (!editing.value) return
  isUpdating.value = true
  const data: UserUpdate = {
    first_name: editData.value.first_name,
    last_name: editData.value.last_name,
    email: editData.value.email,
    role: editSelectedRole.value,
    is_active: editData.value.is_active,
    is_professional: editIsProfessional.value
  }
  const result = await updateUser(editing.value.id, data)
  isUpdating.value = false
  if (result) {
    showEdit.value = false
    editing.value = null
  }
}

function openDelete(user: ClinicUser) {
  toDelete.value = user
  showDelete.value = true
}

async function handleDelete() {
  if (!toDelete.value) return
  isDeleting.value = true
  const result = await deleteUser(toDelete.value.id)
  isDeleting.value = false
  if (result) {
    showDelete.value = false
    toDelete.value = null
  }
}
</script>

<template>
  <SectionCard
    icon="i-lucide-users"
    :title="t('settings.users')"
  >
    <template #actions>
      <UButton
        icon="i-lucide-plus"
        size="sm"
        @click="openCreate"
      >
        {{ t('settings.newUser') }}
      </UButton>
    </template>

    <div
      v-if="showSoloPrompt"
      class="alert-surface-info rounded-token-md px-3 py-2.5 mb-4 flex items-center gap-3"
    >
      <UIcon
        name="i-lucide-stethoscope"
        class="w-4 h-4 shrink-0"
      />
      <div class="min-w-0 flex-1">
        <p class="text-body text-default">
          {{ t('setup.attendPatientsMyself') }}
        </p>
        <p class="text-caption text-muted">
          {{ t('setup.attendPatientsMyselfHelp') }}
        </p>
      </div>
      <USwitch
        :model-value="false"
        :disabled="isMarkingSelf"
        :aria-label="t('setup.attendPatientsMyself')"
        @update:model-value="markSelfProfessional"
      />
    </div>

    <div
      v-if="isLoading"
      class="space-y-3"
    >
      <USkeleton class="h-12 w-full" />
      <USkeleton class="h-12 w-full" />
      <USkeleton class="h-12 w-full" />
    </div>

    <div
      v-else-if="users.length === 0"
      class="text-center py-8 text-muted"
    >
      {{ t('settings.noUsers') }}
    </div>

    <div
      v-else
      class="divide-y divide-[var(--color-border-subtle)]"
    >
      <div
        v-for="user in sortedUsers"
        :key="user.id"
        class="flex items-center justify-between gap-3 py-3 flex-wrap sm:flex-nowrap"
      >
        <div class="flex items-center gap-3 min-w-0 flex-1">
          <UAvatar
            :alt="user.first_name"
            size="sm"
            class="shrink-0"
          />
          <div class="min-w-0">
            <p class="font-medium text-default truncate">
              {{ user.first_name }} {{ user.last_name }}
              <span
                v-if="isCurrentUser(user.id)"
                class="text-caption text-subtle"
              >{{ t('settings.youTag') }}</span>
            </p>
            <p class="text-caption text-subtle truncate">
              {{ user.email }}
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <UBadge
            :color="getRoleBadgeColor(user.role)"
            variant="subtle"
          >
            {{ getRoleLabel(user.role) }}
          </UBadge>
          <UBadge
            v-if="user.is_professional && !PROFESSIONAL_ROLES.includes(user.role)"
            color="info"
            variant="subtle"
            icon="i-lucide-stethoscope"
          >
            {{ t('settings.isProfessional') }}
          </UBadge>
          <UBadge
            v-if="!user.is_active"
            color="error"
            variant="subtle"
          >
            {{ t('common.inactive') }}
          </UBadge>
          <UButton
            v-if="user.is_active"
            icon="i-lucide-link"
            size="xs"
            variant="ghost"
            color="neutral"
            :aria-label="t('settings.invite.rowAction')"
            :title="t('settings.invite.rowAction')"
            @click="openInvite(user)"
          />
          <UButton
            icon="i-lucide-pencil"
            size="xs"
            variant="ghost"
            color="neutral"
            :aria-label="t('settings.editUser')"
            @click="openEdit(user)"
          />
          <UButton
            v-if="!isCurrentUser(user.id)"
            icon="i-lucide-trash-2"
            size="xs"
            variant="ghost"
            color="error"
            :aria-label="t('settings.deleteUser')"
            @click="openDelete(user)"
          />
        </div>
      </div>
    </div>

    <!-- Create modal (password optional → invite link) -->
    <UserCreateModal
      v-model:open="showCreate"
      @saved="fetchUsers"
    />

    <!-- Invite link modal (existing user) -->
    <UModal
      :open="invite !== null"
      @update:open="(v: boolean) => { if (!v) invite = null }"
    >
      <template #content>
        <UCard v-if="invite">
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-link"
                class="w-5 h-5 text-primary-accent"
              />
              <h3 class="font-semibold text-default">
                {{ t('settings.invite.linkTitle') }}
              </h3>
            </div>
          </template>
          <div class="space-y-4">
            <p class="text-body text-muted">
              {{ t('settings.invite.linkHelp', { name: `${invite.user.first_name} ${invite.user.last_name}`, date: new Date(invite.expiresAt).toLocaleDateString(locale) }) }}
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
                :icon="inviteCopied ? 'i-lucide-check' : 'i-lucide-copy'"
                color="primary"
                class="min-h-[44px] justify-center"
                @click="copyInvite"
              >
                {{ inviteCopied ? t('settings.invite.copied') : t('settings.invite.copy') }}
              </UButton>
              <UButton
                icon="i-lucide-message-circle"
                color="neutral"
                variant="soft"
                class="min-h-[44px] justify-center"
                :to="`https://wa.me/?text=${encodeURIComponent(t('settings.invite.shareText', { name: invite.user.first_name, url: invite.url }))}`"
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
              <UButton @click="invite = null">
                {{ t('common.close') }}
              </UButton>
            </div>
          </div>
        </UCard>
      </template>
    </UModal>

    <!-- Edit modal -->
    <UModal v-model:open="showEdit">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-user-pen"
                class="w-5 h-5 text-primary-accent"
              />
              <h3 class="font-semibold text-default">
                {{ t('settings.editUser') }}
              </h3>
            </div>
          </template>

          <form
            class="space-y-4"
            @submit.prevent="handleUpdate"
          >
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <UFormField :label="t('common.firstName')">
                <UInput
                  v-model="editData.first_name"
                  required
                />
              </UFormField>
              <UFormField :label="t('common.lastName')">
                <UInput
                  v-model="editData.last_name"
                  required
                />
              </UFormField>
            </div>

            <UFormField :label="t('common.email')">
              <UInput
                v-model="editData.email"
                type="email"
                required
              />
            </UFormField>

            <UFormField :label="t('common.role')">
              <USelect
                v-model="editSelectedRole"
                :items="translatedRoles"
                value-key="value"
                label-key="label"
                :placeholder="t('placeholders.selectRole')"
              />
            </UFormField>

            <UFormField :help="t('settings.isProfessionalHelp')">
              <div class="flex items-center gap-3">
                <USwitch v-model="editIsProfessional" />
                <span class="text-sm text-muted">{{ t('settings.isProfessional') }}</span>
              </div>
            </UFormField>

            <div
              v-if="editing && !isCurrentUser(editing.id)"
              class="flex items-center gap-3"
            >
              <USwitch v-model="editData.is_active" />
              <span class="text-sm text-muted">{{ t('settings.userActive') }}</span>
              <span
                v-if="!editData.is_active"
                class="text-xs text-danger-accent"
              >
                {{ t('settings.userInactiveNote') }}
              </span>
            </div>

            <div class="flex justify-end gap-2 pt-4">
              <UButton
                variant="ghost"
                @click="showEdit = false"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                type="submit"
                :loading="isUpdating"
              >
                {{ t('settings.saveChanges') }}
              </UButton>
            </div>
          </form>
        </UCard>
      </template>
    </UModal>

    <!-- Delete modal -->
    <UModal v-model:open="showDelete">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-alert-triangle"
                class="w-5 h-5 text-danger-accent"
              />
              <h3 class="font-semibold text-default">
                {{ t('settings.deleteUser') }}
              </h3>
            </div>
          </template>

          <p class="text-muted dark:text-subtle">
            {{ t('settings.deleteUserConfirm') }}
            <strong class="text-default">
              {{ toDelete?.first_name }} {{ toDelete?.last_name }}
            </strong>?
          </p>
          <p class="mt-2 text-caption text-subtle">
            {{ t('settings.deleteUserNote') }}
          </p>

          <div class="flex justify-end gap-2 pt-6">
            <UButton
              variant="ghost"
              @click="showDelete = false"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              color="error"
              :loading="isDeleting"
              @click="handleDelete"
            >
              {{ t('common.delete') }}
            </UButton>
          </div>
        </UCard>
      </template>
    </UModal>
  </SectionCard>
</template>
