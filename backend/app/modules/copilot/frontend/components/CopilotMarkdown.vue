<script setup lang="ts">
// Renders assistant text as sanitized markdown. marked → HTML → DOMPurify.
// isomorphic-dompurify works in both SSR and the browser.
import { marked } from 'marked'
import DOMPurify from 'isomorphic-dompurify'

const props = defineProps<{ text: string }>()

const html = computed(() => {
  const raw = marked.parse(props.text, { async: false, breaks: true, gfm: true }) as string
  return DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } })
})
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div
    class="copilot-md text-sm"
    v-html="html"
  />
</template>

<style scoped>
.copilot-md :deep(p) {
  margin: 0.25rem 0;
}
.copilot-md :deep(p:first-child) {
  margin-top: 0;
}
.copilot-md :deep(p:last-child) {
  margin-bottom: 0;
}
.copilot-md :deep(ul),
.copilot-md :deep(ol) {
  margin: 0.25rem 0;
  padding-inline-start: 1.25rem;
  list-style: revert;
}
.copilot-md :deep(li) {
  margin: 0.125rem 0;
}
.copilot-md :deep(strong) {
  font-weight: 600;
}
.copilot-md :deep(em) {
  font-style: italic;
}
.copilot-md :deep(a) {
  color: var(--ui-primary);
  text-decoration: underline;
}
.copilot-md :deep(code) {
  font-family: ui-monospace, monospace;
  font-size: 0.85em;
  padding: 0.1em 0.3em;
  border-radius: 0.25rem;
  background: var(--ui-bg-elevated);
}
.copilot-md :deep(pre) {
  margin: 0.4rem 0;
  padding: 0.6rem;
  border-radius: 0.375rem;
  overflow-x: auto;
  background: var(--ui-bg-elevated);
}
.copilot-md :deep(pre code) {
  padding: 0;
  background: transparent;
}
.copilot-md :deep(table) {
  border-collapse: collapse;
  margin: 0.4rem 0;
  font-size: 0.9em;
}
.copilot-md :deep(th),
.copilot-md :deep(td) {
  border: 1px solid var(--ui-border);
  padding: 0.25rem 0.5rem;
  text-align: start;
}
.copilot-md :deep(h1),
.copilot-md :deep(h2),
.copilot-md :deep(h3) {
  font-weight: 600;
  margin: 0.5rem 0 0.25rem;
}
.copilot-md :deep(blockquote) {
  border-inline-start: 2px solid var(--ui-border);
  padding-inline-start: 0.6rem;
  margin: 0.4rem 0;
  color: var(--ui-text-muted);
}
</style>
