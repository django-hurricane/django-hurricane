<script setup lang="ts">
import { upperFirst } from 'scule'

const { prev, next, navigation } = useContent()
const { navDirFromPath } = useContentHelpers()

function directory(path: string) {
  if (!path)
    return ''

  const nav = navDirFromPath(path, navigation.value || [])
  if (nav?.[0]?.title)
    return nav[0].title

  const dirs = path.split('/').filter(Boolean)
  const segment = dirs.length > 1
    ? dirs[dirs.length - 2]
    : (dirs[0] || '')
  return segment.split('-').map(upperFirst).join(' ')
}
</script>

<template>
  <div
    v-if="prev || next"
    class="docs-prev-next"
  >
    <NuxtLink
      v-if="prev && prev._path"
      :to="prev._path"
      class="prev"
    >
      <Icon
        name="heroicons-outline:arrow-sm-left"
        class="icon"
      />
      <div class="wrapper">
        <span
          v-if="directory(prev._path)"
          class="directory"
        >
          {{ directory(prev._path) }}
        </span>
        <span class="title">{{ prev.title }}</span>
      </div>
    </NuxtLink>

    <span
      v-else
      class="spacer"
    />

    <NuxtLink
      v-if="next && next._path"
      :to="next._path"
      class="next"
    >
      <div class="wrapper">
        <span
          v-if="directory(next._path)"
          class="directory"
        >
          {{ directory(next._path) }}
        </span>
        <span class="title">{{ next.title }}</span>
      </div>
      <Icon
        name="heroicons-outline:arrow-sm-right"
        class="icon"
      />
    </NuxtLink>
  </div>
</template>

<style scoped>
.docs-prev-next {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.75rem;
}
@media (min-width: 640px) {
  .docs-prev-next {
    flex-direction: row;
    align-items: stretch;
  }
}

.docs-prev-next > a,
.docs-prev-next > .spacer {
  flex: 1 1 0;
  min-width: 0;
  max-width: 100%;
}

.docs-prev-next > a {
  position: relative;
  display: flex;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid rgba(156, 163, 175, 0.35);
  border-radius: 0.375rem;
  text-decoration: none;
  color: inherit;
}
html.dark .docs-prev-next > a {
  border-color: rgba(75, 85, 99, 0.55);
}
.docs-prev-next > a:hover {
  color: #0c4b33;
  background-color: rgba(12, 75, 51, 0.06);
  border-color: rgba(12, 75, 51, 0.25);
}
html.dark .docs-prev-next > a:hover {
  color: #44b78b;
  background-color: rgba(17, 24, 39, 0.9);
  border-color: rgba(68, 183, 139, 0.35);
}

.prev {
  text-align: left;
}
.next {
  text-align: right;
  justify-content: flex-end;
}

.wrapper {
  display: flex;
  flex: 1 1 0;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.directory {
  display: block;
  margin-bottom: 0.25rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.75rem;
  line-height: 1.25rem;
  font-weight: 500;
  color: #6b7280;
}
html.dark .directory {
  color: #9ca3af;
}

.title {
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  font-weight: 500;
  line-height: 1.25rem;
}

.icon {
  align-self: flex-end;
  flex-shrink: 0;
  width: 1.25rem;
  height: 1.25rem;
}
</style>
