<script setup lang="ts">
defineProps<{
  documents: any[]
  loading: boolean
}>()
defineEmits<{ download: [doc: any] }>()

const { t } = useI18n()
</script>

<template>
  <table class="document-table">
    <thead>
      <tr>
        <th>{{ t('documents.table.type') }}</th>
        <th>{{ t('documents.table.title') }}</th>
        <th>{{ t('documents.table.created_at') }}</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      <tr v-if="loading">
        <td colspan="4">{{ t('documents.table.loading') }}</td>
      </tr>
      <tr v-else-if="documents.length === 0">
        <td colspan="4">{{ t('documents.table.empty') }}</td>
      </tr>
      <tr v-for="doc in documents" v-else :key="doc.id">
        <td>{{ t(`documents.types.${doc.document_type}`) }}</td>
        <td>{{ doc.title }}</td>
        <td>{{ new Date(doc.created_at).toLocaleDateString() }}</td>
        <td>
          <button class="btn btn-link" @click="$emit('download', doc)">
            {{ t('documents.table.download') }}
          </button>
        </td>
      </tr>
    </tbody>
  </table>
</template>
