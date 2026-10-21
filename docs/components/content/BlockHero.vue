<script setup lang="ts">
import type { PropType } from 'vue'

defineProps({
  cta: {
    type: Array as PropType<string[]>,
    required: false,
    default: () => []
  },
  secondary: {
    type: Array as PropType<string[]>,
    required: false,
    default: () => []
  },
  video: {
    type: String,
    required: false,
    default: ''
  },
  snippet: {
    type: [Array, String] as PropType<string[] | string>,
    required: false,
    default: () => []
  }
})
</script>

<template>
  <section class="block-hero">
    <!-- Background Cloud Stage Layer -->
    <div class="hero-bg-stage">
      <div class="hero-bg-overlay" />
    </div>

    <div class="layout">
      <div class="content">
        <p v-if="$slots.announce" class="announce">
          <ContentSlot :use="$slots.announce" unwrap="p" />
        </p>

        <h1 class="title">
          <ContentSlot :use="$slots.title" unwrap="p">
            Hero Title
          </ContentSlot>
        </h1>

        <p class="description">
          <ContentSlot :use="$slots.description" unwrap="p">
            Hero default description.
          </ContentSlot>
        </p>

        <div v-if="$slots.extra" class="extra">
          <ContentSlot :use="$slots.extra" unwrap="p" />
        </div>

        <div class="actions">
          <ContentSlot v-if="$slots.actions" :use="$slots.actions" unwrap="p" />
          <template v-else>
            <ButtonLink v-if="cta && cta.length" class="cta" bold size="medium" :href="(cta[1] as any)">
              {{ cta[0] }}
            </ButtonLink>
            <a v-if="secondary && secondary.length" :href="(secondary[1] as any)" class="secondary" target="_blank" rel="noopener noreferrer">
              {{ secondary[0] }}
            </a>
          </template>
        </div>
      </div>

      <div class="support">
        <slot name="support">
          <Terminal v-if="snippet" :content="snippet" />
          <VideoPlayer v-else-if="video" :src="video" />
        </slot>
      </div>
    </div>
  </section>
</template>

<style scoped>
.block-hero {
  position: relative;
  overflow: hidden;
  border-radius: 1.5rem;
  margin: 1.5rem 0 3rem 0;
  border: 1px solid rgba(156, 163, 175, 0.25);
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.08);
}
html.dark .block-hero {
  border-color: rgba(75, 85, 99, 0.35);
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.35);
}

.hero-bg-stage {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-image: url('/bg_clouds1.png');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

.hero-bg-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.94) 0%, rgba(255, 255, 255, 0.88) 50%, rgba(255, 255, 255, 0.82) 100%);
  backdrop-filter: blur(2px);
}
html.dark .hero-bg-overlay {
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.94) 0%, rgba(15, 23, 42, 0.88) 50%, rgba(15, 23, 42, 0.82) 100%);
  backdrop-filter: blur(2px);
}

.layout {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 2.5rem;
  padding: 3rem 2rem;
}
@media (min-width: 640px) {
  .layout {
    padding: 4rem 3rem;
  }
}
@media (min-width: 1024px) {
  .layout {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 2rem;
    padding: 4.5rem 3.5rem;
  }
}

.content {
  display: flex;
  flex-direction: column;
}
@media (min-width: 1024px) {
  .content {
    grid-column: span 2 / span 2;
  }
}

.announce {
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: #0d9488;
}

.title {
  font-size: 2.25rem;
  line-height: 1.2;
  font-weight: 800;
  letter-spacing: -0.025em;
  margin-bottom: 1.25rem;
  color: var(--elements-text-primary-color-static, #111827);
}
@media (min-width: 640px) {
  .title {
    font-size: 3rem;
  }
}

.description {
  font-size: 1.125rem;
  line-height: 1.6;
  margin-bottom: 2rem;
  color: var(--elements-text-secondary-color-static, #4b5563);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1.25rem;
}

.secondary {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--elements-text-secondary-color-static, #4b5563);
  text-decoration: none;
  transition: color 0.15s ease-in-out;
}
.secondary:hover {
  color: #0d9488;
}

.support {
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
