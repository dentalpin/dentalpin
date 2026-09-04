<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold">
        {{ t('procurement.ratings.title') }}
      </h1>
      <p class="text-sm text-muted-foreground">
        {{ t('procurement.ratings.subtitle') }}
      </p>
    </div>

    <div
      v-if="loading"
      class="space-y-4"
    >
      <USkeleton
        v-for="i in 5"
        :key="i"
        class="h-24"
      />
    </div>

    <UAlert
      v-else-if="error"
      color="error"
      :title="t('procurement.common.loadError')"
      :actions="[{ label: t('procurement.common.retry'), onClick: fetchRatings }]"
    />

    <UCard v-else-if="ratings.length === 0">
      <p class="text-sm text-muted-foreground">
        {{ t('procurement.common.empty') }}
      </p>
    </UCard>

    <div
      v-else
      class="space-y-2"
    >
      <UCard
        v-for="rating in ratings"
        :key="rating.supplier_id"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <p class="font-medium">
              {{ rating.supplier_name }}
            </p>
            <div class="mt-1 flex flex-wrap gap-2 text-sm text-muted-foreground">
              <span>{{ t('procurement.ratings.poCount') }}: {{ rating.metrics.po_count }}</span>
              <span>{{ t('procurement.ratings.receivedCount') }}: {{ rating.metrics.received_count }}</span>
              <span>{{ t('procurement.ratings.onTimeRate') }}: {{ formatRate(rating.metrics.on_time_rate) }}</span>
              <span>{{ t('procurement.ratings.rejectRate') }}: {{ formatRate(rating.metrics.reject_rate) }}</span>
            </div>
            <p
              v-if="rating.review"
              class="mt-1 text-sm"
            >
              ★ {{ rating.review.score }}<span v-if="rating.review.comment"> — {{ rating.review.comment }}</span>
            </p>
            <p
              v-else
              class="mt-1 text-sm text-muted-foreground"
            >
              {{ t('procurement.ratings.noData') }}
            </p>
          </div>
          <div
            v-if="can(PERMISSIONS.supplierRatings.write)"
            class="flex shrink-0 gap-2"
          >
            <UButton
              variant="ghost"
              icon="i-lucide-star"
              @click="openReview(rating)"
            >
              {{ rating.review ? t('procurement.ratings.editReview') : t('procurement.ratings.setReview') }}
            </UButton>
            <UButton
              v-if="rating.review"
              variant="ghost"
              color="error"
              icon="i-lucide-trash-2"
              @click="askDelete(rating)"
            >
              {{ t('procurement.ratings.deleteReview') }}
            </UButton>
          </div>
        </div>
      </UCard>

      <div class="flex justify-center pt-2">
        <UPagination
          v-model:page="currentPage"
          :items-per-page="pageSize"
          :total="total"
        />
      </div>
    </div>

    <UModal v-model:open="showForm">
      <template #content>
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ editingId ? t('procurement.ratings.editReview') : t('procurement.ratings.setReview') }}
            </h2>
          </template>
          <div class="space-y-4">
            <UFormField :label="t('procurement.ratings.score')">
              <UInput
                v-model.number="form.score"
                type="number"
                min="1"
                max="5"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('procurement.ratings.comment')">
              <UTextarea
                v-model="form.comment"
                class="w-full"
              />
            </UFormField>
          </div>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                @click="showForm = false"
              >
                {{ t('procurement.common.cancel') }}
              </UButton>
              <UButton
                :loading="saving"
                @click="save"
              >
                {{ t('procurement.common.save') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>

    <UModal v-model:open="showDelete">
      <template #content>
        <UCard>
          <p class="text-sm">
            {{ t('procurement.ratings.deleteConfirm') }}
          </p>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                @click="showDelete = false"
              >
                {{ t('procurement.common.cancel') }}
              </UButton>
              <UButton
                color="error"
                :loading="saving"
                @click="remove"
              >
                {{ t('procurement.common.delete') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>
  </div>
</template>

<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'
import type { SupplierRating } from '../../../composables/useProcurement'

const { t } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const { listSupplierRatings, createSupplierReview, updateSupplierReview, deleteSupplierReview } = useProcurement()

const ratings = ref<SupplierRating[]>([])
const loading = ref(true)
const error = ref(false)
const saving = ref(false)
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)
const showForm = ref(false)
const showDelete = ref(false)
const target = ref<SupplierRating | null>(null)
const editingId = ref<string | null>(null)
const deletingId = ref<string | null>(null)
const form = ref({ score: 5, comment: '' })

function formatRate(rate: string | null): string {
  return rate === null ? '—' : `${Math.round(Number(rate) * 100)}%`
}

async function fetchRatings() {
  loading.value = true
  error.value = false
  try {
    const response = await listSupplierRatings({ page: currentPage.value, page_size: pageSize })
    ratings.value = response.data
    total.value = response.total
  } catch (e) {
    error.value = true
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    loading.value = false
  }
}

function openReview(rating: SupplierRating) {
  target.value = rating
  editingId.value = rating.review ? rating.review.id : null
  form.value = { score: rating.review ? rating.review.score : 5, comment: rating.review?.comment ?? '' }
  showForm.value = true
}

async function save() {
  if (!target.value) return
  saving.value = true
  try {
    if (editingId.value) {
      await updateSupplierReview(editingId.value, {
        score: form.value.score,
        comment: form.value.comment || null
      })
    } else {
      await createSupplierReview({
        supplier_id: target.value.supplier_id,
        score: form.value.score,
        comment: form.value.comment || null
      })
    }
    toast.add({ title: t('procurement.ratings.saved'), color: 'success' })
    showForm.value = false
    await fetchRatings()
  } catch (e) {
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

function askDelete(rating: SupplierRating) {
  if (!rating.review) return
  deletingId.value = rating.review.id
  showDelete.value = true
}

async function remove() {
  if (!deletingId.value) return
  saving.value = true
  try {
    await deleteSupplierReview(deletingId.value)
    toast.add({ title: t('procurement.ratings.deleted'), color: 'success' })
    showDelete.value = false
    await fetchRatings()
  } catch (e) {
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

watch(currentPage, fetchRatings)
onMounted(fetchRatings)
</script>
