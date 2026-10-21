<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  setting?: string
  name?: string
  cli?: string
  env?: string
  default?: string
  alsoSupports?: string
}>()

const settingName = computed(() => props.setting || props.name || '')
</script>

<template>
  <div class="config-param-block">
    <div v-if="settingName" class="config-param-header">
      <div class="config-param-title-group">
        <code class="config-param-name">{{ settingName }}</code>
        <span v-if="alsoSupports" class="also-supports-tag">or <code>{{ alsoSupports }}</code></span>
      </div>
      <div class="config-param-meta">
        <span v-if="cli" class="meta-tag meta-cli">CLI: <code>{{ cli }}</code></span>
        <span v-if="env" class="meta-tag meta-env">Env: <code>{{ env }}</code></span>
        <span v-if="default" class="meta-tag meta-default">Default: <code>{{ default }}</code></span>
      </div>
    </div>
    <div v-else class="config-param-meta standalone-meta">
      <span v-if="cli" class="meta-tag meta-cli">CLI: <code>{{ cli }}</code></span>
      <span v-if="env" class="meta-tag meta-env">Env: <code>{{ env }}</code></span>
      <span v-if="default" class="meta-tag meta-default">Default: <code>{{ default }}</code></span>
      <span v-if="alsoSupports" class="meta-tag meta-supports">Also accepts: <code>{{ alsoSupports }}</code></span>
    </div>
    <div class="config-param-body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.config-param-block {
  margin: 0.75rem 0 1.75rem 0;
  padding: 1.25rem 1.5rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(156, 163, 175, 0.25);
  background-color: rgba(255, 255, 255, 0.65);
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.04);
}
html.dark .config-param-block {
  border-color: rgba(75, 85, 99, 0.35);
  background-color: rgba(17, 24, 39, 0.55);
  box-shadow: 0 2px 4px 0 rgba(0, 0, 0, 0.2);
}

.config-param-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.standalone-meta {
  margin-bottom: 0.75rem;
}

.config-param-title-group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.config-param-name {
  font-size: 1.05rem;
  font-weight: 700;
  padding: 0.2rem 0.55rem;
  border-radius: 0.375rem;
  color: #0f766e;
  background-color: rgba(204, 251, 241, 0.5);
  border: 1px solid rgba(153, 246, 228, 0.8);
}
html.dark .config-param-name {
  color: #5eead4;
  background-color: rgba(19, 78, 74, 0.4);
  border-color: rgba(15, 118, 110, 0.6);
}

.also-supports-tag {
  font-size: 0.75rem;
  color: #6b7280;
}
html.dark .also-supports-tag {
  color: #9ca3af;
}
.also-supports-tag code {
  color: inherit;
  font-weight: 600;
}

.config-param-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.meta-tag {
  font-size: 0.75rem;
  padding: 0.15rem 0.5rem;
  border-radius: 0.25rem;
  font-weight: 500;
}

.meta-cli, .meta-env {
  background-color: rgba(243, 244, 246, 0.8);
  color: #4b5563;
  border: 1px solid rgba(229, 231, 235, 0.8);
}
html.dark .meta-cli, html.dark .meta-env {
  background-color: rgba(31, 41, 55, 0.8);
  color: #d1d5db;
  border-color: rgba(55, 65, 81, 0.8);
}

.meta-default {
  background-color: rgba(238, 242, 255, 0.8);
  color: #4338ca;
  border: 1px solid rgba(224, 231, 255, 0.8);
}
html.dark .meta-default {
  background-color: rgba(30, 27, 75, 0.5);
  color: #a5b4fc;
  border-color: rgba(67, 56, 202, 0.6);
}

.meta-supports {
  background-color: rgba(240, 253, 250, 0.8);
  color: #0f766e;
  border: 1px solid rgba(153, 246, 228, 0.8);
}
html.dark .meta-supports {
  background-color: rgba(19, 78, 74, 0.4);
  color: #5eead4;
  border-color: rgba(15, 118, 110, 0.6);
}

.meta-tag code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.75rem;
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
  color: inherit !important;
}

.config-param-body {
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--elements-text-secondary-color-static, #4b5563);
}
.config-param-body :deep(p) {
  margin: 0;
}
</style>
