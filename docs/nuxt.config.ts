export default defineNuxtConfig({
  extends: '@nuxt-themes/docus',
  app: {
    head: {
      htmlAttrs: {
        lang: 'en'
      },
      link: [
        { rel: 'canonical', href: 'https://django-hurricane.io' },
        { rel: 'icon', type: 'image/x-icon', href: '/favicon.ico' }
      ],
      meta: [
        { property: 'og:site_name', content: 'Django Hurricane' },
        { property: 'og:type', content: 'website' },
        { property: 'og:image', content: 'https://django-hurricane.io/logo.png' },
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:image', content: 'https://django-hurricane.io/logo.png' }
      ],
      script: [
        {
          type: 'application/ld+json',
          children: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': 'Django Hurricane',
            'applicationCategory': 'DeveloperApplication',
            'operatingSystem': 'Linux',
            'programmingLanguage': 'Python, Rust',
            'softwareVersion': '2.0.0',
            'license': 'https://opensource.org/licenses/MIT',
            'description': 'The Kubernetes-Native Application Server for Django powered by Granian (Rust Hyper/Tokio).'
          })
        }
      ]
    }
  },
  plugins: [
    '~/plugins/simpleanalytics.client.js'
  ],
  content: {
    highlight: {
      preload: ['python', 'py', 'bash', 'sh', 'yaml', 'json', 'toml', 'dockerfile']
    }
  }
})
