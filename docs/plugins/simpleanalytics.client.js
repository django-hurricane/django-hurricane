import SimpleAnalytics from 'simple-analytics-vue'

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.vueApp.use(SimpleAnalytics, {
    skip: import.meta.dev,
  })
})
