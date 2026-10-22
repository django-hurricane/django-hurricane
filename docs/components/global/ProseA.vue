<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps({
  href: {
    type: String,
    default: ''
  },
  target: {
    type: String,
    default: undefined,
    required: false
  }
})

const isExternal = computed(() => {
  return props.href.startsWith('http://') || props.href.startsWith('https://') || props.href.startsWith('//')
})

const linkTarget = computed(() => {
  if (props.target) return props.target
  return isExternal.value ? '_blank' : undefined
})

const linkRel = computed(() => {
  return isExternal.value ? 'noopener noreferrer' : undefined
})
</script>

<template>
  <NuxtLink :to="href" :target="linkTarget" :rel="linkRel">
    <slot />
  </NuxtLink>
</template>

<style lang="ts" scoped>
css({
  a: {
    fontFamily: '{typography.font.body}',
    fontWeight: '{prose.a.fontWeight}',
    textDecoration: '{prose.a.textDecoration}',
    borderBottomWidth: '{prose.a.border.width}',
    borderBottomStyle: '{prose.a.border.style.static}',
    borderBottomColor: '{prose.a.border.color.static}',
    paddingBottom: '{prose.a.border.distance}',
    color: '{prose.a.color.static}',
    '&:hover': {
      color: '{prose.a.color.hover}',
      borderColor: '{prose.a.border.color.hover}',
      borderStyle: '{prose.a.border.style.hover}',
    },
    '&:has(img)': {
      borderWidth: '0'
    },
    '&:has(code)': {
      borderBottom: '{prose.a.hasCode.borderBottom}',
      ':deep(code)': {
        color: '{prose.a.code.color.static}',
        borderWidth: '{prose.a.code.border.width}',
        borderStyle: '{prose.a.code.border.style}',
        borderColor: '{prose.a.code.border.color.static}',
      },
      '&:hover': {
        borderBottom: '{prose.a.hasCode.borderBottom}',
        ':deep(code)': {
          color: '{prose.a.code.color.hover}',
          borderColor: '{prose.a.code.border.color.hover}',
          backgroundColor: '{prose.a.code.background.hover}',
        },
      },
    },
  },
})
</style>
