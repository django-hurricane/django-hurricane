export default defineAppConfig({
  docus: {
    title: 'Django Hurricane',
    description: 'The Kubernetes-Native Application Server for Django',
    image: 'https://django-hurricane.io/logo.png',
    url: 'https://django-hurricane.io',
    socials: {
      github: 'django-hurricane/django-hurricane',
      discord: {
        label: 'Discord',
        icon: 'fa-brands:discord',
        href: 'https://discord.gg/8NTPMVPaKy'
      },
      linkedin: {
        label: 'LinkedIn',
        icon: 'fa-brands:linkedin',
        href: 'https://www.linkedin.com/company/blueshoe-gmbh/'
      }
    },
    github: {
      dir: 'docs/content',
      branch: 'main',
      repo: 'django-hurricane',
      owner: 'django-hurricane',
      edit: true
    },
    aside: {
      level: 0,
      exclude: []
    },
    header: {
      logo: true,
      showLinkIcon: true,
      exclude: []
    },
    footer: {
      credits: {
        text: 'The Django Hurricane Community & Blueshoe',
        href: 'https://www.blueshoe.io'
      },
      textLinks: [
        {
          text: 'Discord',
          href: 'https://discord.gg/8NTPMVPaKy'
        },
        {
          text: 'LinkedIn',
          href: 'https://www.linkedin.com/company/blueshoe-gmbh/'
        },
        {
          text: 'Legal Notice',
          href: '/legal-notice'
        },
        {
          text: 'Privacy Policy',
          href: '/data-privacy'
        }
      ]
    }
  }
})
