export default defineNuxtConfig({
  extends: '@nuxt-themes/docus',
  content: {
    highlight: {
      preload: ['python', 'py', 'bash', 'sh', 'yaml', 'json', 'toml', 'dockerfile']
    }
  }
})
