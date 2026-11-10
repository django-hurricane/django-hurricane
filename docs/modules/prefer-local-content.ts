import { defineNuxtModule } from '@nuxt/kit'

/**
 * Theme layers register Prose and content components at default priority.
 * Equal or lower local priority means Mermaid-aware ProseCode never wins.
 *
 * Bump local content + global dirs after other modules so overrides stick.
 */
export default defineNuxtModule({
  meta: {
    name: 'prefer-local-content',
  },
  setup(_options, nuxt) {
    nuxt.hook('modules:done', () => {
      nuxt.hook('components:dirs', (dirs) => {
        for (const dir of dirs) {
          if (typeof dir === 'string')
            continue
          if (
            dir.path?.includes('/components/content')
            || dir.path?.includes('/components/global')
          ) {
            dir.priority = 10
          }
        }
      })
    })
  },
})
