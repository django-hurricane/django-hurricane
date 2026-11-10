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
        href: 'https://discord.gg/8NTPMVPaKy',
      },
      linkedin: {
        label: 'LinkedIn',
        icon: 'fa-brands:linkedin',
        href: 'https://www.linkedin.com/company/blueshoe/',
      },
    },
    github: {
      dir: 'docs/content',
      branch: 'main',
      repo: 'django-hurricane',
      owner: 'django-hurricane',
      edit: true,
    },
    aside: {
      // Level 1 enables top-level header nav (Guides, Configuration, …)
      level: 1,
      exclude: [],
    },
    header: {
      logo: {
        light: '/logo.png',
        dark: '/logo.png',
      },
      showLinkIcon: true,
      exclude: [],
    },
    footer: {
      credits: {
        text: 'Maintained by Blueshoe',
        href: 'https://www.blueshoe.io',
      },
      textLinks: [
        {
          text: 'GitHub Issues',
          href: 'https://github.com/django-hurricane/django-hurricane/issues',
          target: '_blank',
        },
        {
          text: 'hello@blueshoe.io',
          href: 'mailto:hello@blueshoe.io',
        },
        {
          text: 'Discord',
          href: 'https://discord.gg/8NTPMVPaKy',
          target: '_blank',
        },
        {
          text: 'LinkedIn',
          href: 'https://www.linkedin.com/company/blueshoe/',
          target: '_blank',
        },
        {
          text: 'Legal Notice',
          href: '/legal-notice',
        },
        {
          text: 'Privacy Policy',
          href: '/data-privacy',
        },
      ],
    },
  },
})
