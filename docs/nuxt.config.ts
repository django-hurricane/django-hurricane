export default defineNuxtConfig({
  extends: '@nuxt-themes/docus',
  plugins: [
    '~/plugins/simpleanalytics.client.js'
  ],
  content: {
    highlight: {
      preload: ['python', 'py', 'bash', 'sh', 'yaml', 'json', 'toml', 'dockerfile']
    }
  }
})
