import antfu from '@antfu/eslint-config'
import eslintPluginBetterTailwindcss from 'eslint-plugin-better-tailwindcss'
// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt(
  antfu({
    formatters: {
      css: true,
      html: true,
    },
    rules: {
      'no-console': 'warn',
    },
    ignores: [
      '**/content/**/*.md',
      '**/public/**/*.html',
    ],
  }),
  eslintPluginBetterTailwindcss.configs.recommended,
  {
    name: 'blueshoe/tailwindcss',
    rules: {
      'better-tailwindcss/no-unknown-classes': 'off',
    },
    settings: {
      'better-tailwindcss': {
        tailwindConfig: 'tailwind.config.ts',
        cwd: './blueshoe-core',
      },
    },
  },
)
