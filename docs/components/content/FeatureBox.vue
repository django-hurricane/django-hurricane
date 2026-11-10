<script setup lang="ts">
defineProps<{
  tag?: string
  title: string
}>()
</script>

<template>
  <div class="feature-box">
    <div v-if="tag" class="feature-box-tag">
      {{ tag }}
    </div>
    <h3 class="feature-box-title">
      {{ title }}
    </h3>
    <div class="feature-box-content">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.feature-box {
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  border-radius: 0.875rem;
  border: 1px solid rgba(156, 163, 175, 0.25);
  background-color: rgba(255, 255, 255, 0.7);
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
  transition: all 0.2s ease-in-out;
}
html.dark .feature-box {
  border-color: rgba(75, 85, 99, 0.35);
  background-color: rgba(17, 24, 39, 0.6);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
}
.feature-box:hover {
  border-color: rgba(12, 75, 51, 0.55);
  transform: translateY(-2px);
  box-shadow: 0 10px 15px -3px rgba(12, 75, 51, 0.12);
}
.feature-box-tag {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #0c4b33;
  margin-bottom: 0.5rem;
}
html.dark .feature-box-tag {
  color: #44b78b;
}
.feature-box-title {
  font-size: 1.125rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  color: var(--elements-text-primary-color-static, inherit);
}
.feature-box-content {
  font-size: 0.875rem;
  line-height: 1.625;
  color: var(--elements-text-secondary-color-static, #6b7280);
}
</style>
