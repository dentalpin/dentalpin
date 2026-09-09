<script setup lang="ts">
import type { ModuleDoctorReport } from '~/types'

interface Props {
  report: ModuleDoctorReport
}

const props = defineProps<Props>()
const { t } = useI18n()

const expanded = ref(false)

const counts = computed(() => ({
  orphans: props.report.orphans.length,
  missingDeps: props.report.missing_dependencies.length,
  manifestErrors: props.report.manifest_errors.length,
  errored: props.report.errored_modules.length
}))
</script>

<template>
  <UAlert
    color="warning"
    variant="soft"
    icon="i-lucide-alert-triangle"
    :title="t('settings.modules.doctor.banner')"
  >
    <template #description>
      <div class="space-y-2">
        <div class="flex flex-wrap gap-4 text-sm">
          <span v-if="counts.orphans > 0">
            <strong>{{ counts.orphans }}</strong>
            {{ t('settings.modules.doctor.orphans') }}
          </span>
          <span v-if="counts.missingDeps > 0">
            <strong>{{ counts.missingDeps }}</strong>
            {{ t('settings.modules.doctor.missingDeps') }}
          </span>
          <span v-if="counts.manifestErrors > 0">
            <strong>{{ counts.manifestErrors }}</strong>
            {{ t('settings.modules.doctor.manifestErrors') }}
          </span>
          <span v-if="counts.errored > 0">
            <strong>{{ counts.errored }}</strong>
            {{ t('settings.modules.doctor.errored') }}
          </span>
        </div>

        <UButton
          variant="ghost"
          size="xs"
          :icon="expanded ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
          @click="expanded = !expanded"
        >
          {{ expanded ? t('common.hide') : t('common.viewDetails') }}
        </UButton>

        <div
          v-if="expanded"
          class="mt-3 space-y-3 text-sm"
        >
          <div v-if="report.orphans.length > 0">
            <p class="font-semibold">
              {{ t('settings.modules.doctor.orphans') }}
            </p>
            <ul class="list-disc ps-5 text-subtle">
              <li
                v-for="name in report.orphans"
                :key="`orphan-${name}`"
              >
                {{ name }}
              </li>
            </ul>
          </div>

          <div v-if="report.missing_dependencies.length > 0">
            <p class="font-semibold">
              {{ t('settings.modules.doctor.missingDeps') }}
            </p>
            <ul class="list-disc ps-5 text-subtle">
              <li
                v-for="entry in report.missing_dependencies"
                :key="`miss-${entry.module}-${entry.missing}`"
              >
                <code>{{ entry.module }}</code> → <code>{{ entry.missing }}</code>
              </li>
            </ul>
          </div>

          <div v-if="report.manifest_errors.length > 0">
            <p class="font-semibold">
              {{ t('settings.modules.doctor.manifestErrors') }}
            </p>
            <ul class="list-disc ps-5 text-subtle">
              <li
                v-for="entry in report.manifest_errors"
                :key="`manifest-${entry.module}`"
              >
                <code>{{ entry.module }}</code>: {{ entry.error }}
              </li>
            </ul>
          </div>

          <div v-if="report.errored_modules.length > 0">
            <p class="font-semibold">
              {{ t('settings.modules.doctor.errored') }}
            </p>
            <ul class="list-disc ps-5 text-subtle">
              <li
                v-for="entry in report.errored_modules"
                :key="`err-${entry.module}`"
              >
                <code>{{ entry.module }}</code>: {{ entry.error }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </template>
  </UAlert>
</template>
