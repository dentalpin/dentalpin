<script setup lang="ts">
/**
 * PlanItemDoctorChip — colored avatar + popover for picking a doctor.
 *
 * Reused in two contexts:
 * - Pending plan items: ``professionalId`` = ``item.assigned_professional_id``,
 *   ``readonly`` = false, picker emits ``change``.
 * - Completed plan items: ``professionalId`` = ``item.completed_by``,
 *   ``readonly`` = true, no picker — purely a "who did it" indicator.
 *
 * Emits ``change`` with the chosen professional id (or ``null`` to clear).
 */

import type { Professional } from '~~/app/types'

const props = defineProps<{
  /** Current doctor id, or ``null`` when no doctor is assigned. */
  professionalId: string | null
  /** Plan-level doctor — drives "override" detection and the reset action. */
  planProfessionalId?: string | null
  /** When true the chip renders as an indicator and the picker stays closed. */
  readonly?: boolean
}>()

const emit = defineEmits<{
  change: [professionalId: string | null]
}>()

const { t } = useI18n()
const {
  professionals,
  fetchProfessionals,
  getProfessionalById,
  getProfessionalColor,
  getProfessionalInitials,
  getProfessionalFullName
} = useProfessionals()

const open = ref(false)
const isMobile = ref(false)

function updateViewport() {
  if (typeof window !== 'undefined') {
    isMobile.value = window.innerWidth < 640
  }
}

onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  // Lazy-load the list — most clinics have <10 professionals.
  if (professionals.value.length === 0) fetchProfessionals()
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', updateViewport)
  }
})

const currentDoctorId = computed(() => props.professionalId ?? null)

const currentDoctor = computed<Professional | undefined>(() => {
  if (!currentDoctorId.value) return undefined
  return getProfessionalById(currentDoctorId.value)
})

const isOverride = computed(() => {
  if (!props.planProfessionalId) return false
  return currentDoctorId.value !== null && currentDoctorId.value !== props.planProfessionalId
})

const tooltip = computed(() => {
  if (!currentDoctor.value) return t('treatmentPlans.items.noProfessional')
  return getProfessionalFullName(currentDoctor.value)
})

function selectDoctor(professionalId: string | null) {
  emit('change', professionalId)
  open.value = false
}

function openPicker() {
  if (props.readonly) return
  open.value = true
}
</script>

<template>
  <UPopover
    v-if="!isMobile"
    v-model:open="open"
    :ui="{ content: 'w-64' }"
  >
    <button
      type="button"
      class="plan-item-doctor-chip"
      :class="{ 'is-override': isOverride, 'is-empty': !currentDoctor, 'is-readonly': readonly }"
      :title="tooltip"
      :aria-label="t('treatmentPlans.items.assignedProfessionalAriaLabel')"
      :style="currentDoctor ? { backgroundColor: getProfessionalColor(currentDoctor.id) } : undefined"
      :disabled="readonly"
      @click.stop="openPicker"
    >
      <span v-if="currentDoctor">{{ getProfessionalInitials(currentDoctor) }}</span>
      <UIcon
        v-else
        name="i-lucide-user-x"
        class="w-3.5 h-3.5"
      />
    </button>

    <template #content>
      <div class="p-2 space-y-1">
        <button
          v-if="isOverride"
          type="button"
          class="picker-row picker-reset"
          @click="selectDoctor(planProfessionalId ?? null)"
        >
          <UIcon
            name="i-lucide-rotate-ccw"
            class="w-4 h-4"
          />
          <span>{{ t('treatmentPlans.items.useUsersPlanDoctor') }}</span>
        </button>

        <button
          v-for="prof in professionals"
          :key="prof.id"
          type="button"
          class="picker-row"
          :class="{ 'is-active': prof.id === currentDoctorId }"
          @click="selectDoctor(prof.id)"
        >
          <span
            class="picker-avatar"
            :style="{ backgroundColor: getProfessionalColor(prof.id) }"
          >
            {{ getProfessionalInitials(prof) }}
          </span>
          <span class="picker-name">{{ getProfessionalFullName(prof) }}</span>
          <UIcon
            v-if="prof.id === currentDoctorId"
            name="i-lucide-check"
            class="w-4 h-4 text-success-accent ms-auto"
          />
        </button>

        <button
          type="button"
          class="picker-row picker-clear"
          @click="selectDoctor(null)"
        >
          <UIcon
            name="i-lucide-user-x"
            class="w-4 h-4"
          />
          <span>{{ t('treatmentPlans.items.noProfessional') }}</span>
        </button>
      </div>
    </template>
  </UPopover>

  <template v-else>
    <button
      type="button"
      class="plan-item-doctor-chip is-mobile"
      :class="{ 'is-override': isOverride, 'is-empty': !currentDoctor, 'is-readonly': readonly }"
      :aria-label="t('treatmentPlans.items.assignedProfessionalAriaLabel')"
      :style="currentDoctor ? { backgroundColor: getProfessionalColor(currentDoctor.id) } : undefined"
      :disabled="readonly"
      @click.stop="openPicker"
    >
      <span v-if="currentDoctor">{{ getProfessionalInitials(currentDoctor) }}</span>
      <UIcon
        v-else
        name="i-lucide-user-x"
        class="w-4 h-4"
      />
    </button>

    <USlideover
      v-model:open="open"
      side="bottom"
      :ui="{ content: 'h-auto max-h-[80vh]' }"
    >
      <template #content>
        <div class="p-4 space-y-2">
          <h3 class="text-h2 mb-2">
            {{ t('treatmentPlans.items.assignedProfessional') }}
          </h3>
          <button
            v-if="isOverride"
            type="button"
            class="picker-row picker-reset"
            @click="selectDoctor(planProfessionalId ?? null)"
          >
            <UIcon
              name="i-lucide-rotate-ccw"
              class="w-4 h-4"
            />
            <span>{{ t('treatmentPlans.items.useUsersPlanDoctor') }}</span>
          </button>
          <button
            v-for="prof in professionals"
            :key="prof.id"
            type="button"
            class="picker-row"
            :class="{ 'is-active': prof.id === currentDoctorId }"
            @click="selectDoctor(prof.id)"
          >
            <span
              class="picker-avatar"
              :style="{ backgroundColor: getProfessionalColor(prof.id) }"
            >
              {{ getProfessionalInitials(prof) }}
            </span>
            <span class="picker-name">{{ getProfessionalFullName(prof) }}</span>
            <UIcon
              v-if="prof.id === currentDoctorId"
              name="i-lucide-check"
              class="w-4 h-4 text-success-accent ms-auto"
            />
          </button>
          <button
            type="button"
            class="picker-row picker-clear"
            @click="selectDoctor(null)"
          >
            <UIcon
              name="i-lucide-user-x"
              class="w-4 h-4"
            />
            <span>{{ t('treatmentPlans.items.noProfessional') }}</span>
          </button>
        </div>
      </template>
    </USlideover>
  </template>
</template>

<style scoped>
.plan-item-doctor-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 9999px;
  color: white;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
  cursor: pointer;
  transition: transform 120ms ease, box-shadow 120ms ease;
  border: 2px solid transparent;
}

.plan-item-doctor-chip:hover:not(.is-readonly) {
  transform: scale(1.08);
  box-shadow: 0 0 0 2px var(--color-surface), 0 0 0 4px rgba(59, 130, 246, 0.35);
}

.plan-item-doctor-chip.is-mobile {
  width: 32px;
  height: 32px;
  font-size: 12px;
}

.plan-item-doctor-chip.is-empty {
  background-color: var(--color-surface-muted, #f3f4f6);
  color: var(--color-warning-accent, #ca8a04);
  border-color: var(--color-warning-accent, #ca8a04);
}

.plan-item-doctor-chip.is-readonly {
  cursor: default;
  opacity: 0.7;
}

.picker-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 8px;
  border-radius: 6px;
  text-align: start;
  font-size: 13px;
  color: var(--color-text-default);
  transition: background-color 120ms ease;
}

.picker-row:hover {
  background-color: var(--color-surface-muted, #f3f4f6);
}

.picker-row.is-active {
  background-color: rgba(59, 130, 246, 0.1);
  font-weight: 500;
}

.picker-row.picker-reset {
  font-weight: 500;
  color: var(--color-primary-accent, #2563eb);
  border-bottom: 1px solid var(--color-border-default, #e5e7eb);
  margin-bottom: 4px;
  padding-bottom: 8px;
}

.picker-row.picker-clear {
  color: var(--color-text-muted);
  border-top: 1px solid var(--color-border-default, #e5e7eb);
  margin-top: 4px;
  padding-top: 8px;
}

.picker-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 9999px;
  color: white;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}

.picker-name {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
