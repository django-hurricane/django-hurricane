export default defineNuxtPlugin(() => {
  const route = useRoute()
  const siteUrl = 'https://django-hurricane.io'

  useHead(() => {
    const cleanPath = route.path === '/'
      ? ''
      : route.path.replace(/\/$/, '')
    return {
      link: [
        {
          rel: 'canonical',
          href: `${siteUrl}${cleanPath}`,
        },
      ],
    }
  })
})
