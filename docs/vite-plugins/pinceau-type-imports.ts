import type { Plugin } from 'vite'

/**
 * Nuxt 3.21 / Vite 7 keeps type-only named imports as runtime imports.
 * Pinceau exports `PinceauTheme` / `PropertyValue` as types only, which crashes
 * the client bundle (`does not provide an export named 'PinceauTheme'`).
 */
export function pinceauTypeImports(): Plugin {
  return {
    name: 'pinceau-type-imports',
    enforce: 'pre',
    transform(code, id) {
      if (!code.includes('PinceauTheme') || !code.includes('pinceau')) {
        return null
      }

      // Skip the pinceau package itself
      if (id.includes('/node_modules/pinceau/')) {
        return null
      }

      const next = code
        .replace(
          /import\s*\{\s*PinceauTheme\s*,\s*PropertyValue\s*\}\s*from\s*(['"])pinceau\1\s*;?/,
          'import type { PinceauTheme, PropertyValue } from \'pinceau\';',
        )
        .replace(
          /import\s*\{\s*PropertyValue\s*,\s*PinceauTheme\s*\}\s*from\s*(['"])pinceau\1\s*;?/,
          'import type { PinceauTheme, PropertyValue } from \'pinceau\';',
        )
        .replace(
          /import\s*\{\s*PinceauTheme\s*\}\s*from\s*(['"])pinceau\1\s*;?/,
          'import type { PinceauTheme } from \'pinceau\';',
        )

      return next === code
        ? null
        : next
    },
  }
}
