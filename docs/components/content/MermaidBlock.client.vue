<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'

const props = defineProps<{
  code: string
}>()

const svg = ref('')
const error = ref('')

async function renderDiagram() {
  await nextTick()
  const source = props.code?.trim()
  if (!source) return

  try {
    let mermaidInstance: any = null
    try {
      const m = await import('mermaid')
      mermaidInstance = m.default || m
    } catch (importErr) {
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
      fontFamily: 'inherit'
    })

    const cleanId = `mermaid${Math.random().toString(36).replace(/[^a-z0-9]/gi, '').substring(0, 8)}`
    const renderRes = await mermaidInstance.render(cleanId, source)
    svg.value = renderRes.svg
    error.value = ''
  } catch (err: any) {
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
  <div class="mermaid-diagram my-6 p-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/70 backdrop-blur shadow-sm flex flex-col items-center overflow-x-auto">
    <div v-if="svg" class="w-full flex justify-center" v-html="svg" />
    <div v-else-if="error" class="w-full">
      <div class="text-xs text-amber-600 dark:text-amber-400 mb-2 font-mono">Unable to render interactive diagram:</div>
      <pre class="text-xs font-mono text-gray-500 whitespace-pre p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg overflow-x-auto">{{ code }}</pre>
    </div>
    <div v-else class="text-sm text-gray-400 py-4 font-mono">
      Rendering diagram...
    </div>
  </div>
</template>
