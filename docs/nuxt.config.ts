// https://nuxt.com/docs/api/configuration/nuxt-config
import { defineNuxtConfig } from 'nuxt/config'

export default defineNuxtConfig({
  extends: '@nuxt-themes/docus',
  modules: ['@nuxt/eslint', '~/modules/pinceau-type-imports'],
  compatibilityDate: '2026-11-06',

  // Avoid noisy first-run Vite resolve errors for the experimental app manifest
  experimental: {
    appManifest: false,
  },

  eslint: {
    config: {
      standalone: false,
    },
  },

  vite: {
    optimizeDeps: {
      exclude: ['pinceau'],
    },
  },

  app: {
    head: {
      htmlAttrs: {
        lang: 'en',
      },
      link: [
        { rel: 'icon', type: 'image/x-icon', href: '/favicon.ico' },
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Fira+Mono:wght@400;700&family=Roboto:ital,wght@0,300;0,400;0,700;1,400;1,700&display=swap',
        },
      ],
      meta: [
        { property: 'og:site_name', content: 'Django Hurricane' },
        { property: 'og:type', content: 'website' },
        { property: 'og:image', content: 'https://django-hurricane.io/logo.png' },
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:image', content: 'https://django-hurricane.io/logo.png' },
      ],
      style: [
        {
          textContent: `
            :root {
              --font-sans: 'Roboto', system-ui, -apple-system, sans-serif;
              --font-mono: 'Fira Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            }
            html, body, #__nuxt {
              font-family: var(--font-sans);
            }
            code, kbd, pre, .font-mono {
              font-family: var(--font-mono);
            }
            .docs-aside-tree .icon {
              width: 1rem !important;
              height: 1rem !important;
              min-width: 1rem !important;
              min-height: 1rem !important;
              flex-shrink: 0 !important;
              margin-right: 0.625rem !important;
            }
            .docs-aside-tree .link .content,
            .docs-aside-tree .title-collapsible-button .content {
              min-width: 0;
            }
          `,
        },
      ],
      script: [
        {
          type: 'application/ld+json',
          textContent: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': 'Django Hurricane',
            'applicationCategory': 'DeveloperApplication',
            'operatingSystem': 'Linux, macOS, Windows',
            'programmingLanguage': 'Python, Rust',
            'softwareVersion': '2.0.0',
            'license': 'https://opensource.org/licenses/MIT',
            'description': 'The high-performance, Django-native application server with built-in edge defense, native static asset serving, and deep health observability.',
          }),
        },
      ],
    },
  },

  plugins: [
    '~/plugins/simpleanalytics.client.js',
    '~/plugins/canonical.ts',
  ],

  content: {
    highlight: {
      preload: [
        'python',
        'py',
        'bash',
        'sh',
        'yaml',
        'json',
        'toml',
        'dockerfile',
        'nginx',
        'mermaid',
        'ini',
      ],
    },
  },
})
