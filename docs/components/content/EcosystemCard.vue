<script setup lang="ts">
withDefaults(
  defineProps<{
    logo: string
    title: string
    tag?: string
    url: string
    linkText?: string
  }>(),
  {
    linkText: 'Learn More →',
  },
)
</script>

<template>
  <a
    :href="url" target="_blank" rel="noopener noreferrer" class="ecosystem-card"
  >
    <div class="ecosystem-card-header">
      <img :src="logo" :alt="title" class="ecosystem-logo">
      <span v-if="tag" class="ecosystem-tag">{{ tag }}</span>
    </div>
    <h3 class="ecosystem-title">{{ title }}</h3>
    <div class="ecosystem-body">
      <slot />
    </div>
    <div class="ecosystem-footer">
      <span class="ecosystem-link">{{ linkText }}</span>
    </div>
  </a>
</template>

<style scoped>
.ecosystem-card {
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  border-radius: 1rem;
  border: 1px solid rgba(156, 163, 175, 0.25);
  background: rgba(255, 255, 255, 0.7);
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
  text-decoration: none;
  color: inherit;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

html.dark .ecosystem-card {
  border-color: rgba(75, 85, 99, 0.35);
  background: rgba(17, 24, 39, 0.65);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.25);
}

.ecosystem-card:hover {
  transform: translateY(-4px);
  border-color: #2271af;
  box-shadow: 0 12px 24px -4px rgba(34, 113, 175, 0.2);
}

.ecosystem-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.ecosystem-logo {
  height: 2.75rem;
  width: auto;
  max-width: 9rem;
  object-fit: contain;
}

.ecosystem-tag {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.25rem 0.6rem;
  border-radius: 9999px;
  background-color: rgba(34, 113, 175, 0.12);
  color: #2271af;
}

html.dark .ecosystem-tag {
  background-color: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
}

.ecosystem-title {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 0 0 0.5rem 0;
  color: #111827;
}

html.dark .ecosystem-title {
  color: #f9fafb;
}

.ecosystem-body {
  font-size: 0.9rem;
  line-height: 1.55;
  color: #4b5563;
  flex: 1 1 auto;
}

html.dark .ecosystem-body {
  color: #9ca3af;
}

.ecosystem-footer {
  margin-top: 1.25rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(156, 163, 175, 0.15);
}

.ecosystem-link {
  font-size: 0.875rem;
  font-weight: 600;
  color: #2271af;
  display: inline-flex;
  align-items: center;
  transition: transform 0.2s ease;
}

html.dark .ecosystem-link {
  color: #38bdf8;
}

.ecosystem-card:hover .ecosystem-link {
  transform: translateX(4px);
}
</style>
