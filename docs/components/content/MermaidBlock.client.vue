<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps<{
  code: string
}>()

const svg = ref('')
const error = ref('')

async function renderDiagram() {
  await nextTick()
  const source = props.code?.trim()
  if (!source) {
    return
  }

  try {
    let mermaidInstance: any = null
    try {
      const m = await import('mermaid')
      mermaidInstance = m.default || m
    }
    catch {
      if (typeof window !== 'undefined') {
        const cdnUrl = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs'
        const m = await import(/* @vite-ignore */ cdnUrl)
        mermaidInstance = m.default || m
      }
    }

    if (!mermaidInstance) {
      throw new Error('Mermaid library could not be loaded.')
    }

    const isDark = typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
    mermaidInstance.initialize({
      startOnLoad: false,
      theme: isDark ? 'dark' : 'neutral',
      securityLevel: 'loose',
      fontFamily: 'inherit',
    })

    const cleanId = `mermaid${Math.random().toString(36).replace(/[^a-z0-9]/gi, '').substring(0, 8)}`
    const renderRes = await mermaidInstance.render(cleanId, source)
    svg.value = renderRes.svg
    error.value = ''
  }
  catch (err: any) {
    console.error('Mermaid render error:', err)
    error.value = err?.message || String(err)
  }
}

onMounted(() => {
  renderDiagram()
})

watch(() => props.code, () => {
  renderDiagram()
})
</script>

<template>
  <div
    class="
      mermaid-diagram my-6 flex flex-col items-center overflow-x-auto rounded-xl
      border border-gray-200 bg-white/70 p-4 shadow-sm backdrop-blur-sm
      dark:border-gray-800 dark:bg-gray-900/70
    "
  >
    <div v-if="svg" class="flex w-full justify-center" v-html="svg" />
    <div v-else-if="error" class="w-full">
      <div
        class="
          mb-2 font-mono text-xs text-amber-600
          dark:text-amber-400
        "
      >
        Unable to render interactive diagram:
      </div>
      <pre
        class="
          overflow-x-auto rounded-lg bg-gray-50 p-3 font-mono text-xs
          whitespace-pre text-gray-500
          dark:bg-gray-800/50
        "
      >{{ code }}</pre>
    </div>
    <div v-else class="py-4 font-mono text-sm text-gray-400">
      Rendering diagram...
    </div>
  </div>
</template>
