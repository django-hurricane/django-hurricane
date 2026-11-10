import { defineNuxtModule } from '@nuxt/kit'

/**
 * @nuxt/content registers `components/content` at default priority 1, same as
 * `@nuxt-themes/elements` landing components. Equal priorities trigger Nuxt's
 * "Two component files resolving to the same name BlockHero" warning.
 *
 * Register the priority bump after other modules so we run last on
 * `components:dirs` and can raise Content's unshifted local dir.
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
          if (dir.path?.includes('/components/content'))
            dir.priority = 10
        }
      })
    })
  },
})
