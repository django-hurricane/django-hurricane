<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

const reducedMotion = ref(false)

const chips = [
  {
    label: '.php',
    x: 64,
    y: 16,
    blowX: -180,
    blowY: -140,
    spin: -36,
    delay: 0,
  },
  {
    label: '/.env',
    x: 78,
    y: 14,
    blowX: 200,
    blowY: -120,
    spin: 28,
    delay: 0.06,
  },
  {
    label: '/wp-admin/',
    x: 70,
    y: 34,
    blowX: -200,
    blowY: 30,
    spin: -42,
    delay: 0.12,
  },
  {
    label: 'wp-login.php',
    x: 84,
    y: 30,
    blowX: 230,
    blowY: 50,
    spin: 34,
    delay: 0.18,
  },
  {
    label: '/actuator',
    x: 72,
    y: 24,
    blowX: 30,
    blowY: -170,
    spin: 22,
    delay: 0.09,
  },
  {
    label: '/.git/',
    x: 66,
    y: 48,
    blowX: -160,
    blowY: 130,
    spin: -26,
    delay: 0.24,
  },
  {
    label: 'xmlrpc.php',
    x: 86,
    y: 46,
    blowX: 250,
    blowY: 110,
    spin: 40,
    delay: 0.3,
  },
]

// Docus already pulls in @vueuse/nuxt — most reliable scroll source
const { y: scrollY } = useWindowScroll()

/** Full blow-away over ~560px of scroll — slow, readable arc */
const SCROLL_RANGE = 560

const progress = computed(() => {
  if (reducedMotion.value)
    return 0.35
  return Math.min(1, Math.max(0, scrollY.value / SCROLL_RANGE))
})

/** Ease-out cubic: starts gentle, eases into the drift */
function easeOut(t: number) {
  const x = Math.min(1, Math.max(0, t))
  return 1 - (1 - x) ** 3
}

function chipStyle(chip: typeof chips[number]) {
  // Each chip uses most of the scroll range, staggered so they leave one by one
  const local = easeOut((progress.value - chip.delay) / 0.85)
  return {
    left: `${chip.x}%`,
    top: `${chip.y}%`,
    transform: `translate3d(${chip.blowX * local}px, ${chip.blowY * local}px, 0) rotate(${chip.spin * local}deg) scale(${1 - local * 0.25})`,
    opacity: Math.max(0, 1 - local * 0.95),
  }
}

onMounted(() => {
  reducedMotion.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches
})
</script>

<template>
  <div
    class="hurricane-stage"
    :class="{ 'reduce-motion': reducedMotion }"
    aria-hidden="true"
  >
    <div
      class="storm-wash"
      :style="{ opacity: 0.4 + progress * 0.6 }"
    />

    <div
      class="tornado"
      :style="{
        opacity: 0.65 + progress * 0.3,
        transform: `scale(${0.94 + progress * 0.18})`,
      }"
    >
      <svg class="tornado-svg" viewBox="0 0 400 420" fill="none">
        <defs>
          <linearGradient id="twisterStroke" x1="200" y1="20" x2="200" y2="400" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="#e8fff6" stop-opacity="0.95" />
            <stop offset="35%" stop-color="#89e7c3" stop-opacity="0.9" />
            <stop offset="70%" stop-color="#44b78b" stop-opacity="0.75" />
            <stop offset="100%" stop-color="#20aa76" stop-opacity="0.25" />
          </linearGradient>
          <radialGradient id="eyeGlow" cx="50%" cy="22%" r="38%">
            <stop offset="0%" stop-color="#89e7c3" stop-opacity="0.6" />
            <stop offset="55%" stop-color="#44b78b" stop-opacity="0.2" />
            <stop offset="100%" stop-color="#44b78b" stop-opacity="0" />
          </radialGradient>
          <filter id="stormGlow" x="-30%" y="-20%" width="160%" height="140%">
            <feGaussianBlur stdDeviation="5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <g class="swirl-head">
          <ellipse cx="200" cy="95" rx="150" ry="70" fill="url(#eyeGlow)" />
          <ellipse
            cx="200" cy="95" rx="128" ry="58" stroke="#89e7c3" stroke-width="2.5" stroke-dasharray="10 12" fill="none" opacity="0.6" class="
              ring-outer
            "
          />
          <ellipse
            cx="200" cy="95" rx="92" ry="42" stroke="#44b78b" stroke-width="3.5" stroke-dasharray="16 10" fill="rgba(68,183,139,0.12)" class="
              ring-mid
            "
          />
          <ellipse
            cx="200" cy="95" rx="48" ry="22" stroke="#e8fff6" stroke-width="2" fill="rgba(137,231,195,0.3)" class="
              ring-inner
            "
          />
        </g>

        <g class="funnel">
          <path
            d="M70 95 C110 70, 290 70, 330 95 C360 120, 340 155, 280 175 C210 200, 170 220, 145 260 C115 310, 145 350, 175 385 C190 402, 198 412, 200 418"
            stroke="url(#twisterStroke)"
            stroke-width="10"
            stroke-linecap="round"
            filter="url(#stormGlow)"
            class="ribbon-a"
          />
          <path
            d="M100 100 C135 78, 265 80, 300 102 C328 124, 310 155, 255 172 C195 192, 165 215, 145 255 C122 300, 150 340, 180 375"
            stroke="url(#twisterStroke)"
            stroke-width="6"
            stroke-linecap="round"
            opacity="0.85"
            class="ribbon-b"
          />
          <path
            d="M130 108 C158 90, 242 92, 270 110 C292 126, 278 152, 235 166 C188 184, 165 208, 152 248 C138 290, 162 328, 188 362"
            stroke="#e8fff6"
            stroke-width="3"
            stroke-linecap="round"
            opacity="0.55"
            class="ribbon-c"
          />
        </g>
      </svg>
    </div>

    <span
      v-for="chip in chips"
      :key="chip.label"
      class="request-chip"
      :style="chipStyle(chip)"
    >
      {{ chip.label }}
    </span>
  </div>
</template>

<style scoped>
.hurricane-stage {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 1;
}

.storm-wash {
  position: absolute;
  top: -10%;
  right: -5%;
  width: min(70vw, 720px);
  height: min(90vw, 780px);
  background: radial-gradient(
    ellipse at 45% 30%,
    rgba(68, 183, 139, 0.3) 0%,
    rgba(32, 170, 118, 0.12) 42%,
    transparent 72%
  );
  transition: opacity 0.45s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.tornado {
  position: absolute;
  top: -2%;
  left: 48%;
  width: min(55vw, 640px);
  height: min(78vw, 700px);
  transform-origin: 45% 18%;
  filter: drop-shadow(0 0 40px rgba(68, 183, 139, 0.45));
  will-change: transform, opacity;
  transition:
    transform 0.45s cubic-bezier(0.22, 0.61, 0.36, 1),
    opacity 0.45s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.tornado-svg {
  width: 100%;
  height: 100%;
  display: block;
  overflow: visible;
}

.swirl-head {
  transform-origin: 200px 95px;
  animation: head-spin 10s linear infinite;
}
.ring-outer {
  transform-origin: 200px 95px;
  animation: head-spin 14s linear infinite;
}
.ring-mid {
  transform-origin: 200px 95px;
  animation: head-spin-rev 9s linear infinite;
}
.ring-inner {
  transform-origin: 200px 95px;
  animation: head-spin 6s linear infinite;
}
.funnel {
  transform-origin: 200px 95px;
  animation: funnel-sway 4s ease-in-out infinite;
}
.ribbon-a {
  animation: ribbon-glow 2.4s ease-in-out infinite;
}
.ribbon-b {
  animation: ribbon-glow 2.4s ease-in-out infinite 0.35s;
}
.ribbon-c {
  animation: ribbon-glow 2.4s ease-in-out infinite 0.7s;
}

.request-chip {
  position: absolute;
  z-index: 2;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: clamp(0.7rem, 1.1vw, 0.85rem);
  font-weight: 700;
  letter-spacing: 0.02em;
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  color: #fecaca;
  background: rgba(127, 29, 29, 0.85);
  border: 1px solid rgba(248, 113, 113, 0.55);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3);
  white-space: nowrap;
  will-change: transform, opacity;
  /* Smooth between scroll frames so motion feels continuous */
  transition:
    transform 0.35s cubic-bezier(0.22, 0.61, 0.36, 1),
    opacity 0.4s cubic-bezier(0.22, 0.61, 0.36, 1);
}
html:not(.dark) .request-chip {
  color: #6a0e0e;
  background: rgba(255, 228, 230, 0.96);
  border-color: rgba(185, 28, 28, 0.35);
}

@keyframes head-spin {
  to {
    transform: rotate(360deg);
  }
}
@keyframes head-spin-rev {
  to {
    transform: rotate(-360deg);
  }
}
@keyframes funnel-sway {
  0%,
  100% {
    transform: rotate(-3deg) translate(0, 0);
  }
  50% {
    transform: rotate(4deg) translate(8px, 6px);
  }
}
@keyframes ribbon-glow {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 1;
  }
}

.hurricane-stage.reduce-motion .swirl-head,
.hurricane-stage.reduce-motion .ring-outer,
.hurricane-stage.reduce-motion .ring-mid,
.hurricane-stage.reduce-motion .ring-inner,
.hurricane-stage.reduce-motion .funnel,
.hurricane-stage.reduce-motion .ribbon-a,
.hurricane-stage.reduce-motion .ribbon-b,
.hurricane-stage.reduce-motion .ribbon-c {
  animation: none !important;
}

@media (max-width: 1023px) {
  .tornado {
    left: 35%;
    top: 8%;
    width: min(85vw, 420px);
    height: min(95vw, 480px);
    opacity: 0.55;
  }
  .request-chip {
    font-size: 0.65rem;
    opacity: 0.55;
  }
}
</style>
