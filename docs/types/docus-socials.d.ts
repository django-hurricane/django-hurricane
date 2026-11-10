/**
 * AppSocialIcons accepts either a string handle/URL or a custom link object.
 * Docus' generated schema only lists a few built-in string networks — widen it
 * so Discord/LinkedIn type-check.
 */
interface DocusSocialLink {
  label: string
  icon: string
  href: string
  rel?: string
}

declare module 'nuxt/schema' {
  interface CustomAppConfig {
    docus?: {
      socials?: {
        discord?: string | DocusSocialLink
        linkedin?: string | DocusSocialLink
      }
    }
  }
}

declare module '@nuxt/schema' {
  interface CustomAppConfig {
    docus?: {
      socials?: {
        discord?: string | DocusSocialLink
        linkedin?: string | DocusSocialLink
      }
    }
  }
}

export {}
