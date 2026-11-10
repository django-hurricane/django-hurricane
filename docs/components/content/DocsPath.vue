<script setup lang="ts">
const items = [
  {
    step: '01',
    title: 'Getting Started',
    description: 'Install Hurricane, add it to INSTALLED_APPS, and launch with manage.py serve.',
    href: '/guides/getting-started',
  },
  {
    step: '02',
    title: 'Guides',
    description: 'Kubernetes, static files, reverse proxies, metrics, and production patterns.',
    href: '/guides/kubernetes-deployment',
  },
  {
    step: '03',
    title: 'Configuration',
    description: 'Every setting, CLI flag, and environment variable in one reference.',
    href: '/configuration/settings',
  },
]
</script>

<template>
  <div class="docs-path">
    <NuxtLink
      v-for="item in items"
      :key="item.href"
      :to="item.href"
      class="docs-path-card"
    >
      <span class="docs-path-step">{{ item.step }}</span>
      <h3 class="docs-path-title">
        {{ item.title }}
      </h3>
      <p class="docs-path-desc">
        {{ item.description }}
      </p>
      <span class="docs-path-cta">Open →</span>
    </NuxtLink>
  </div>
</template>

<style scoped>
.docs-path {
  display: grid;
  gap: 1rem;
  margin: 1.25rem 0 2rem;
}
@media (min-width: 768px) {
  .docs-path {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.docs-path-card {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1.25rem 1.35rem;
  border-radius: 0.875rem;
  border: 1px solid rgba(12, 75, 51, 0.15);
  background: rgba(255, 255, 255, 0.72);
  text-decoration: none;
  transition:
    transform 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}
html.dark .docs-path-card {
  border-color: rgba(68, 183, 139, 0.25);
  background: rgba(9, 46, 32, 0.35);
}
.docs-path-card:hover {
  transform: translateY(-2px);
  border-color: rgba(12, 75, 51, 0.45);
  box-shadow: 0 10px 20px -12px rgba(12, 75, 51, 0.35);
}
html.dark .docs-path-card:hover {
  border-color: rgba(68, 183, 139, 0.55);
  box-shadow: 0 10px 20px -12px rgba(0, 0, 0, 0.55);
}
html.dark .docs-path-step {
  color: #44b78b;
}

.docs-path-step {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #20aa76;
}

.docs-path-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--elements-text-primary-color-static, #111827);
}

.docs-path-desc {
  margin: 0;
  flex: 1;
  font-size: 0.875rem;
  line-height: 1.55;
  color: var(--elements-text-secondary-color-static, #6b7280);
}

.docs-path-cta {
  margin-top: 0.35rem;
  font-size: 0.8rem;
  font-weight: 700;
  color: #0c4b33;
}
html.dark .docs-path-cta {
  color: #44b78b;
}
</style>
