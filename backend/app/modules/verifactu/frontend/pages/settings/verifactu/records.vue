<script setup lang="ts">
const { t } = useI18n()
const { listRecords } = useVerifactu()

const page = ref(1)
const pageSize = ref(50)
const stateFilter = ref<string | undefined>(undefined)
const tipoFilter = ref<string | undefined>(undefined)
const data = ref<Awaited<ReturnType<typeof listRecords>> | null>(null)
const loading = ref(false)

async function refresh() {
  loading.value = true
  try {
    data.value = await listRecords({
      page: page.value,
      page_size: pageSize.value,
      state: stateFilter.value,
      tipo_factura: tipoFilter.value
    })
  } finally {
    loading.value = false
  }
}

watch([page, stateFilter, tipoFilter], refresh)
onMounted(refresh)
</script>

<template>
  <div class="p-4 sm:p-6 max-w-5xl mx-auto space-y-4">
    <header>
      <NuxtLink
        to="/settings/verifactu"
        class="text-sm text-gray-500"
      >← Verifactu</NuxtLink>
      <h1 class="text-2xl font-semibold mt-2">
        {{ t('verifactu.records.title') }}
      </h1>
      <p class="text-sm text-gray-500">
        {{ t('verifactu.records.subtitle') }}
      </p>
    </header>

    <div class="flex flex-wrap gap-2">
      <USelect
        v-model="stateFilter"
        :options="[
          { label: '—', value: undefined },
          { label: t('verifactu.recordState.accepted'), value: 'accepted' },
          { label: t('verifactu.recordState.accepted_with_errors'), value: 'accepted_with_errors' },
          { label: t('verifactu.recordState.rejected'), value: 'rejected' },
          { label: t('verifactu.recordState.pending'), value: 'pending' }
        ]"
        :placeholder="t('verifactu.records.filterState')"
        class="min-w-[140px]"
      />
      <USelect
        v-model="tipoFilter"
        :options="[
          { label: '—', value: undefined },
          { label: 'F1', value: 'F1' },
          { label: 'F2', value: 'F2' },
          { label: 'R1', value: 'R1' }
        ]"
        :placeholder="t('verifactu.records.filterTipo')"
        class="min-w-[120px]"
      />
    </div>

    <div
      v-if="loading"
      class="space-y-2"
    >
      <USkeleton
        v-for="i in 5"
        :key="i"
        class="h-12 w-full"
      />
    </div>
    <div
      v-else-if="data && data.data.length > 0"
      class="overflow-x-auto"
    >
      <table class="min-w-full text-sm">
        <thead class="text-left text-gray-500">
          <tr>
            <th class="py-2 px-2">
              {{ t('verifactu.records.columns.createdAt') }}
            </th>
            <th class="py-2 px-2">
              {{ t('verifactu.records.columns.tipoFactura') }}
            </th>
            <th class="py-2 px-2">
              {{ t('verifactu.records.columns.serieNumero') }}
            </th>
            <th class="py-2 px-2 text-right">
              {{ t('verifactu.records.columns.importe') }}
            </th>
            <th class="py-2 px-2">
              {{ t('verifactu.records.columns.state') }}
            </th>
            <th class="py-2 px-2">
              {{ t('verifactu.records.columns.csv') }}
            </th>
          </tr>
        </thead>
        <tbody class="divide-y">
          <tr
            v-for="r in data.data"
            :key="r.id"
          >
            <td class="py-2 px-2 whitespace-nowrap">
              {{ new Date(r.created_at).toLocaleString() }}
            </td>
            <td class="py-2 px-2">
              <UBadge variant="subtle">
                {{ r.tipo_factura }}
              </UBadge>
            </td>
            <td class="py-2 px-2 font-mono">
              {{ r.serie_numero }}
            </td>
            <td class="py-2 px-2 text-right">
              {{ r.importe_total }}
            </td>
            <td class="py-2 px-2">
              <UBadge
                :color="r.state === 'accepted' ? 'green' : r.state === 'rejected' ? 'red' : 'gray'"
                variant="subtle"
              >
                {{ t(`verifactu.recordState.${r.state}`) }}
              </UBadge>
            </td>
            <td class="py-2 px-2 font-mono">
              {{ r.aeat_csv ?? '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p
      v-else
      class="text-sm text-gray-500"
    >
      —
    </p>

    <div
      v-if="data"
      class="flex justify-between items-center text-sm pt-4"
    >
      <span>{{ data.total }} registros</span>
      <div class="flex gap-2">
        <UButton
          :disabled="page <= 1"
          variant="soft"
          size="sm"
          @click="page--"
        >
          ‹
        </UButton>
        <UButton
          :disabled="(data.page * data.page_size) >= data.total"
          variant="soft"
          size="sm"
          @click="page++"
        >
          ›
        </UButton>
      </div>
    </div>
  </div>
</template>
