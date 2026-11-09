import { addVitePlugin, defineNuxtModule } from '@nuxt/kit'
import { pinceauTypeImports } from '../vite-plugins/pinceau-type-imports'

/**
 * Registers the Pinceau/Vite type-import fix without polluting nuxt.config
 * with relative imports (keeps config typings/auto-globals cleaner).
 */
export default defineNuxtModule({
  meta: {
    name: 'pinceau-type-imports',
  },
  setup() {
    addVitePlugin(pinceauTypeImports())
  },
})
