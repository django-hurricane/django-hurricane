<script setup lang="ts">
import type { PinceauTheme } from 'pinceau/types'
import type { PropType } from 'vue'

const props = defineProps({
  blank: {
    type: Boolean,
    required: false,
    default: false,
  },
  color: {
    type: String as PropType<keyof PinceauTheme['color']>,
    default: 'primary',
  },
  href: {
    type: String,
    default: '',
  },
  icon: {
    type: String,
    default: '',
  },
  size: {
    type: String as PropType<'small' | 'medium' | 'large' | 'giant'>,
    default: 'medium',
  },
  transparent: {
    type: Boolean,
    default: false,
  },
})
</script>

<template>
  <NuxtLink
    class="button-link"
    :to="props.href"
    :target="props.blank ? '_blank' : undefined"
    :style="{ marginInlineEnd: '1rem', marginBlockEnd: '0.75rem' }"
  >
    <Icon v-if="props.icon" :name="props.icon" />
    <ContentSlot :use="$slots.default" unwrap="p ul li" />
  </NuxtLink>
</template>

<style lang="ts" scoped>
css({
  '.button-link': {
    '--button-primary': props => `{color.${props.color}.600}`,
    '--button-secondary': props => `{color.${props.color}.500}`,
    'display': 'inline-flex',
    'flex': 'none',
    'alignItems': 'center',
    'borderRadius': '{radii.md}',
    'transition': 'color 100ms ease-in-out',
    'fontWeight': '{fontWeight.bold}',
    'color': '{color.white}',
    'backgroundColor': '{button.primary}',
    'border': '1px solid transparent',
    '&:hover': {
      backgroundColor: '{button.secondary}',
    },
    '&:focus': {
      border: `1px solid {button.primary}`,
    },
    '.icon': {
      marginInlineEnd: '{space.1}',
    },
  },
  'variants': {
    size: {
      small: {
        padding: `{space.2} {space.4}`,
        fontSize: '{text.sm.fontSize}',
        lineHeight: '{text.sm.lineHeight}',
      },
      medium: {
        padding: `{space.rem.625} {space.5}`,
        fontSize: '{text.base.fontSize}',
        lineHeight: '{text.base.lineHeight}',
      },
      large: {
        padding: `{space.3} {space.6}`,
        fontSize: '{text.lg.fontSize}',
        lineHeight: '{text.lg.lineHeight}',
      },
      giant: {
        padding: `{space.4} {space.8}`,
        fontSize: '{text.lg.fontSize}',
        lineHeight: '{text.lg.lineHeight}',
      },
      options: {
        default: 'medium',
      },
    },
    transparent: {
      true: {
        'backgroundColor': 'transparent',
        'border': '1px solid var(--button-primary)',
        'color': 'var(--button-primary)',
        '&:hover': {
          backgroundColor: 'var(--button-primary)',
          color: '{color.white}',
        },
      },
    },
  },
})
</style>
