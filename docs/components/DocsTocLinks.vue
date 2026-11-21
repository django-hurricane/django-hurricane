<script setup lang="ts">
import type { PropType } from 'vue'

interface TocLink {
  id: string
  text: string
  depth: number
  children?: TocLink[]
}

defineProps({
  links: {
    type: Array as PropType<TocLink[]>,
    default: () => [],
  },
})

const emit = defineEmits(['move'])

const depthClass: Record<number, string> = {
  3: 'depth-3',
  4: 'depth-4',
}

const router = useRouter()

const { activeHeadings, updateHeadings } = useScrollspy()

if (import.meta.client) {
  setTimeout(() => {
    updateHeadings([
      ...document.querySelectorAll('.document-driven-page h1, .docus-content h1'),
      ...document.querySelectorAll('.document-driven-page h2, .docus-content h2'),
      ...document.querySelectorAll('.document-driven-page h3, .docus-content h3'),
      ...document.querySelectorAll('.document-driven-page h4, .docus-content h4'),
    ])
  }, 300)
}

function scrollToHeading(id: string) {
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    history.replaceState(null, '', `#${id}`)
  }
  else {
    router.push({ hash: `#${id}` })
  }
  emit('move', id)
}

function childMove(id: string) {
  emit('move', id)
}
</script>

<template>
  <ul class="docs-toc-links">
    <li
      v-for="link in links"
      :key="link.id"
      :class="depthClass[link.depth]"
    >
      <a
        :href="`#${link.id}`"
        :class="[activeHeadings.includes(link.id) && 'active']"
        @click.prevent="scrollToHeading(link.id)"
      >
        {{ link.text }}
      </a>
      <DocsTocLinks
        v-if="link.children"
        :links="link.children"
        @move="childMove($event)"
      />
    </li>
  </ul>
</template>

<style scoped>
.docs-toc-links {
  min-width: 0;
  list-style: none;
  margin: 0;
  padding: 0;
}

.depth-3 {
  padding-left: 0.75rem;
}
.depth-4 {
  padding-left: 1.5rem;
}

.docs-toc-links a {
  display: block;
  min-width: 0;
  padding: 0.25rem 0;
  overflow-wrap: anywhere;
  white-space: normal;
  font-size: 0.875rem;
  line-height: 1.35;
  color: #6b7280;
  text-decoration: none;
}
@media (min-width: 1024px) {
  .docs-toc-links a {
    padding-right: 0.75rem;
  }
}
html.dark .docs-toc-links a {
  color: #9ca3af;
}
.docs-toc-links a:not(.active):hover {
  color: #111827;
}
html.dark .docs-toc-links a:not(.active):hover {
  color: #e5e7eb;
}
.docs-toc-links a.active {
  color: #0c4b33;
}
html.dark .docs-toc-links a.active {
  color: #44b78b;
}
</style>
