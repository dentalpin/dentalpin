<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { useTasks, type AssignableUser, type Task, type TaskPriority, type TaskStatus } from '../../composables/useTasks'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const tasksApi = useTasks()

if (!can(PERMISSIONS.tasks.read)) {
  await navigateTo('/')
}

const canWrite = computed(() => can(PERMISSIONS.tasks.write))

const PRIORITIES: TaskPriority[] = ['low', 'normal', 'high']
const priorityOptions = computed(() => PRIORITIES.map(p => ({ value: p, label: t(`tasks.priorities.${p}`) })))

const items = ref<Task[]>([])
const loading = ref(false)
const filterStatus = ref<TaskStatus>('open')

const staff = ref<AssignableUser[]>([])
const staffOptions = computed(() => staff.value.map(u => ({ value: u.id, label: u.full_name })))

async function loadStaff() {
  const res = await tasksApi.assignableUsers()
  staff.value = res.data
}

async function load() {
  loading.value = true
  try {
    const res = await tasksApi.list({ task_status: filterStatus.value, page: 1, page_size: 100 })
    items.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([load(), loadStaff()])
})
watch(filterStatus, load)

async function toggleDone(task: Task) {
  await tasksApi.update(task.id, { status: task.status === 'done' ? 'open' : 'done' })
  await load()
}

async function remove(id: string) {
  await tasksApi.remove(id)
  await load()
}

// --- Add task modal ---
const showModal = ref(false)
const saving = ref(false)
const form = ref({
  title: '',
  description: '',
  priority: 'normal' as TaskPriority,
  assigned_to: '',
  due_date: ''
})

function openCreate() {
  form.value = { title: '', description: '', priority: 'normal', assigned_to: '', due_date: '' }
  showModal.value = true
}

async function submit() {
  if (!form.value.title.trim()) return
  saving.value = true
  try {
    await tasksApi.create({
      title: form.value.title,
      description: form.value.description || null,
      priority: form.value.priority,
      assigned_to: form.value.assigned_to || null,
      due_date: form.value.due_date || null
    })
    showModal.value = false
    await load()
  } finally {
    saving.value = false
  }
}

const priorityColor: Record<TaskPriority, 'neutral' | 'warning' | 'error'> = {
  low: 'neutral',
  normal: 'neutral',
  high: 'error'
}
</script>

<template>
  <div class="p-4 space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-h2 text-default">
        {{ t('tasks.title') }}
      </h1>
      <UButton
        v-if="canWrite"
        icon="i-lucide-plus"
        @click="openCreate"
      >
        {{ t('tasks.add') }}
      </UButton>
    </div>

    <div class="flex gap-2">
      <UButton
        :variant="filterStatus === 'open' ? 'solid' : 'outline'"
        size="sm"
        @click="filterStatus = 'open'"
      >
        {{ t('tasks.open') }}
      </UButton>
      <UButton
        :variant="filterStatus === 'done' ? 'solid' : 'outline'"
        size="sm"
        @click="filterStatus = 'done'"
      >
        {{ t('tasks.done') }}
      </UButton>
    </div>

    <div v-if="loading" class="text-caption text-subtle">
      {{ t('tasks.loading') }}
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="task in items"
        :key="task.id"
        class="flex items-start gap-3 p-3 rounded-lg border border-default"
      >
        <UButton
          :icon="task.status === 'done' ? 'i-lucide-check-square' : 'i-lucide-square'"
          variant="ghost"
          size="sm"
          :disabled="!canWrite"
          @click="toggleDone(task)"
        />
        <div class="flex-1 space-y-1">
          <div class="flex items-center gap-2 flex-wrap">
            <span :class="task.status === 'done' ? 'line-through text-subtle' : ''">{{ task.title }}</span>
            <UBadge :color="priorityColor[task.priority]" variant="soft" size="sm">
              {{ t(`tasks.priorities.${task.priority}`) }}
            </UBadge>
          </div>
          <p v-if="task.description" class="text-caption text-subtle">
            {{ task.description }}
          </p>
          <div class="text-caption text-subtle flex gap-3 flex-wrap">
            <span v-if="task.assigned_to_name">{{ t('tasks.assignedTo') }}: {{ task.assigned_to_name }}</span>
            <span v-if="task.due_date">{{ t('tasks.due') }}: {{ task.due_date }}</span>
            <span v-if="task.assigned_by_name">{{ t('tasks.createdBy') }}: {{ task.assigned_by_name }}</span>
          </div>
        </div>
        <UButton
          v-if="canWrite"
          icon="i-lucide-trash-2"
          variant="ghost"
          color="error"
          size="xs"
          @click="remove(task.id)"
        />
      </div>
      <p v-if="items.length === 0" class="text-caption text-subtle">
        {{ t('tasks.empty') }}
      </p>
    </div>

    <UModal v-model:open="showModal">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ t('tasks.add') }}
          </h2>
          <UInput v-model="form.title" :placeholder="t('tasks.taskTitle')" />
          <UInput v-model="form.description" :placeholder="t('tasks.description')" />
          <USelect v-model="form.priority" :items="priorityOptions" />
          <USelect v-model="form.assigned_to" :items="staffOptions" :placeholder="t('tasks.assignTo')" />
          <UInput v-model="form.due_date" type="date" />
          <div class="flex justify-end gap-2">
            <UButton variant="ghost" @click="showModal = false">
              {{ t('actions.cancel') }}
            </UButton>
            <UButton :loading="saving" :disabled="!form.title.trim()" @click="submit">
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
