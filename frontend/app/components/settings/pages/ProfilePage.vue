<script setup lang="ts">
const { t } = useI18n()
const auth = useAuth()
</script>

<template>
  <div class="space-y-4">
    <SectionCard
      icon="i-lucide-user"
      :title="t('settings.profile')"
    >
      <div
        v-if="auth.user.value"
        class="space-y-4"
      >
        <div class="flex items-center gap-4">
          <UAvatar
            :alt="auth.user.value.first_name"
            size="lg"
          />
          <div>
            <p class="font-medium text-default">
              {{ auth.user.value.first_name }} {{ auth.user.value.last_name }}
            </p>
            <p class="text-caption text-subtle">
              {{ auth.user.value.email }}
            </p>
          </div>
        </div>
      </div>
    </SectionCard>
    <MfaProfileSettings />
  </div>
</template>
