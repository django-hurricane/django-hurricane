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

const alias = computed(() => {
  const value = props.alsoSupports?.trim()
  if (!value)
    return ''
  // Hide only when it duplicates the Env row (setting name already shown as title)
  if (value === props.env)
    return ''
  if (value === settingName.value)
    return ''
  return value
})

const anchor = computed(() =>
  settingName.value
    ? settingName.value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
    : '',
)

const metaRows = computed(() => {
  const rows: Array<{ label: string, value: string, kind: string }> = []
  if (props.cli)
    rows.push({ label: 'CLI', value: props.cli, kind: 'cli' })
  if (props.env)
    rows.push({ label: 'Env', value: props.env, kind: 'env' })
  if (props.default)
    rows.push({ label: 'Default', value: props.default, kind: 'default' })
  if (alias.value)
    rows.push({ label: 'Also', value: alias.value, kind: 'alias' })
  return rows
})
</script>

<template>
  <div
    :id="anchor || undefined"
    class="config-param-block"
  >
    <div v-if="settingName" class="config-param-header">
      <code class="config-param-name">{{ settingName }}</code>
    </div>

    <dl v-if="metaRows.length" class="config-param-meta">
      <div
        v-for="row in metaRows"
        :key="row.label"
        class="meta-cell"
        :class="{
          'meta-cli': row.kind === 'cli',
          'meta-env': row.kind === 'env',
          'meta-default': row.kind === 'default',
          'meta-alias': row.kind === 'alias',
        }"
      >
        <dt>{{ row.label }}</dt>
        <dd><code>{{ row.value }}</code></dd>
      </div>
    </dl>

    <div class="config-param-body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.config-param-block {
  margin: 0.85rem 0 1.5rem;
  padding: 1.1rem 1.25rem 1.2rem;
  border-radius: 0.75rem;
  border: 1px solid rgba(12, 75, 51, 0.14);
  background-color: rgba(255, 255, 255, 0.72);
  scroll-margin-top: 5.5rem;
}
html.dark .config-param-block {
  border-color: rgba(68, 183, 139, 0.22);
  background-color: rgba(17, 24, 39, 0.55);
}

.config-param-header {
  margin-bottom: 0.85rem;
}

.config-param-name {
  display: inline-block;
  font-size: 1rem;
  font-weight: 700;
  padding: 0.2rem 0.55rem;
  border-radius: 0.375rem;
  color: #0c4b33;
  background-color: rgba(147, 215, 183, 0.28);
  border: 1px solid rgba(32, 170, 118, 0.35);
}
html.dark .config-param-name {
  color: #89e7c3;
  background-color: rgba(9, 46, 32, 0.55);
  border-color: rgba(68, 183, 139, 0.4);
}

.config-param-meta {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.5rem;
  margin: 0 0 0.9rem;
}
@media (min-width: 640px) {
  .config-param-meta {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.meta-cell {
  display: grid;
  grid-template-columns: 4.5rem minmax(0, 1fr);
  align-items: start;
  gap: 0.5rem;
  padding: 0.45rem 0.6rem;
  border-radius: 0.4rem;
  background: rgba(243, 244, 246, 0.75);
  border: 1px solid rgba(229, 231, 235, 0.9);
}
html.dark .meta-cell {
  background: rgba(31, 41, 55, 0.65);
  border-color: rgba(55, 65, 81, 0.85);
}

.meta-cell dt {
  margin: 0;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #6b7280;
  padding-top: 0.15rem;
}
html.dark .meta-cell dt {
  color: #9ca3af;
}

.meta-cell dd {
  margin: 0;
  min-width: 0;
}

.meta-cell code {
  display: block;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.78rem;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: break-word;
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
  color: #111827;
}
html.dark .meta-cell code {
  color: #e5e7eb;
}

.meta-default {
  background: rgba(238, 242, 255, 0.7);
  border-color: rgba(199, 210, 254, 0.9);
}
html.dark .meta-default {
  background: rgba(30, 27, 75, 0.4);
  border-color: rgba(67, 56, 202, 0.45);
}

.meta-alias {
  background: rgba(240, 253, 244, 0.75);
  border-color: rgba(167, 243, 208, 0.9);
}
html.dark .meta-alias {
  background: rgba(6, 78, 59, 0.35);
  border-color: rgba(16, 185, 129, 0.35);
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
