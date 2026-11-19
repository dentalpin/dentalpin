<script setup lang="ts">
import AccessLog from './AccessLog.vue'

defineProps<{ ctx: { patientId: string } }>()
</script>

<template>
  <UCard class="mt-4">
    <AccessLog :patient-id="ctx.patientId" />
  </UCard>
</template>
