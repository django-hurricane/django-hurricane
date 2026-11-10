<script setup lang="ts">
import type { PropType } from 'vue'
import HurricaneScrollStage from './HurricaneScrollStage.vue'

defineProps({
  cta: {
    type: Array as PropType<string[]>,
    required: false,
    default: () => [],
  },
  secondary: {
    type: Array as PropType<string[]>,
    required: false,
    default: () => [],
  },
  video: {
    type: String,
    required: false,
    default: '',
  },
  snippet: {
    type: [Array, String] as PropType<string[] | string>,
    required: false,
    default: () => [],
  },
})
</script>

<template>
  <section class="block-hero">
    <div class="hero-bg-stage">
      <div class="hero-bg-overlay" />
    </div>

    <HurricaneScrollStage />

    <div class="layout">
      <div class="content">
        <a
          class="django-badge"
          href="https://www.djangoproject.com/"
          target="_blank"
          rel="noopener noreferrer"
          title="Django is a registered trademark of the Django Software Foundation"
        >
          <img
            class="django-badge-logo light-only"
            src="/brand/django-logo-positive.svg"
            alt="Django"
            width="72"
            height="24"
          >
          <img
            class="django-badge-logo dark-only"
            src="/brand/django-logo-negative.svg"
            alt="Django"
            width="72"
            height="24"
          >
          <span>Built for Django</span>
        </a>

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
            <a
              v-if="secondary && secondary.length"
              :href="(secondary[1] as any)"
              class="secondary"
              target="_blank"
              rel="noopener noreferrer"
            >
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
:global(body) {
  overflow-x: hidden;
}

.block-hero {
  position: relative;
  overflow: hidden;
  width: 100vw;
  margin-left: calc(50% - 50vw);
  margin-right: calc(50% - 50vw);
  margin-top: 0;
  margin-bottom: 2.5rem;
  border-radius: 0;
  border: none;
  border-bottom: 1px solid rgba(156, 163, 175, 0.2);
  box-shadow: none;
}
html.dark .block-hero {
  border-bottom-color: rgba(75, 85, 99, 0.3);
  box-shadow: none;
}

.hero-bg-stage {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-image: url('/bg_clouds1.png');
  background-size: cover;
  background-position: center top;
  background-repeat: no-repeat;
}

.hero-bg-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.78) 0%,
    rgba(255, 255, 255, 0.88) 60%,
    rgba(255, 255, 255, 0.98) 95%,
    rgba(255, 255, 255, 1) 100%
  );
  backdrop-filter: blur(1px);
}
html.dark .hero-bg-overlay {
  background: linear-gradient(
    180deg,
    rgba(12, 60, 38, 0.72) 0%,
    rgba(15, 23, 42, 0.88) 55%,
    rgba(15, 23, 42, 0.98) 95%,
    rgba(15, 23, 42, 1) 100%
  );
  backdrop-filter: blur(1px);
}

.layout {
  position: relative;
  z-index: 4;
  display: grid;
  gap: 2.5rem;
  max-width: 80rem;
  margin: 0 auto;
  padding: 3.5rem 1.5rem 4.5rem 1.5rem;
  box-sizing: border-box;
}
@media (min-width: 640px) {
  .layout {
    padding: 4.5rem 2.5rem 5.5rem 2.5rem;
  }
}
@media (min-width: 1024px) {
  .layout {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 2.5rem;
    padding: 5.5rem 3rem 6.5rem 3rem;
  }
}

.content {
  position: relative;
  z-index: 4;
  display: flex;
  flex-direction: column;
}
@media (min-width: 1024px) {
  .content {
    grid-column: span 2 / span 2;
  }
}

.django-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  width: fit-content;
  margin-bottom: 1rem;
  padding: 0.35rem 0.7rem 0.35rem 0.45rem;
  border-radius: 999px;
  border: 1px solid rgba(12, 75, 51, 0.18);
  background: rgba(255, 255, 255, 0.75);
  color: #0c3c26;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  text-decoration: none;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}
.django-badge:hover {
  border-color: rgba(12, 75, 51, 0.45);
  background: rgba(255, 255, 255, 0.95);
}
html.dark .django-badge {
  border-color: rgba(68, 183, 139, 0.35);
  background: rgba(9, 46, 32, 0.55);
  color: #89e7c3;
}
.django-badge-logo {
  height: 1.1rem;
  width: auto;
  display: block;
}
.light-only {
  display: block;
}
.dark-only {
  display: none;
}
html.dark .light-only {
  display: none;
}
html.dark .dark-only {
  display: block;
}

.announce {
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: #0c4b33;
}
html.dark .announce {
  color: #44b78b;
}
.announce :deep(a) {
  margin-inline-start: 0.35em;
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
.actions :deep(.button-link) {
  margin-inline-end: 0 !important;
  margin-block-end: 0 !important;
}

.secondary {
  display: inline-flex;
  align-items: center;
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1;
  color: var(--elements-text-secondary-color-static, #4b5563);
  text-decoration: none;
  transition: color 0.15s ease-in-out;
}
.secondary:hover {
  color: #0c4b33;
}
html.dark .secondary:hover {
  color: #44b78b;
}

.support {
  position: relative;
  z-index: 4;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
