<script setup lang="ts">
const { config } = useDocus()

interface FooterLink {
  text: string
  href: string
  external?: boolean
}

const contactLinks = computed<FooterLink[]>(() => {
  const fromConfig = (config.value?.footer?.textLinks || [])
    .filter((link: { text?: string, href?: string }) => link?.text && link?.href)
    .map((link: { text: string, href: string, target?: string }) => ({
      text: link.text,
      href: link.href,
      external: Boolean(link.target === '_blank' || link.href.startsWith('mailto:') || link.href.startsWith('http')),
    }))

  return fromConfig.length
    ? fromConfig
    : [
        {
          text: 'GitHub Issues',
          href: 'https://github.com/django-hurricane/django-hurricane/issues',
          external: true,
        },
        {
          text: 'hello@blueshoe.io',
          href: 'mailto:hello@blueshoe.io',
          external: true,
        },
        {
          text: 'Discord',
          href: 'https://discord.gg/8NTPMVPaKy',
          external: true,
        },
        {
          text: 'LinkedIn',
          href: 'https://www.linkedin.com/company/blueshoe/',
          external: true,
        },
        {
          text: 'Legal Notice',
          href: '/legal-notice',
          external: false,
        },
        {
          text: 'Privacy Policy',
          href: '/data-privacy',
          external: false,
        },
      ]
})

const icons = computed(() => config.value?.footer?.iconLinks || [])
</script>

<template>
  <footer class="hurricane-footer">
    <Container
      :fluid="config?.footer?.fluid"
      padded
      class="footer-container"
    >
      <div class="brand">
        <a
          class="blueshoe-link"
          href="https://www.blueshoe.io"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Blueshoe"
        >
          <img
            class="blueshoe-logo light-only"
            src="/brand/blueshoe-logo-horizontal.png"
            alt="Blueshoe"
            width="152"
            height="45"
            decoding="async"
          >
          <img
            class="blueshoe-logo dark-only"
            src="/brand/blueshoe-logo-horizontal-white.png"
            alt="Blueshoe"
            width="152"
            height="45"
            decoding="async"
          >
        </a>
        <p class="brand-copy">
          Maintained by Blueshoe · Made in Munich
        </p>
        <a
          class="django-footer-badge"
          href="https://www.djangoproject.com/"
          target="_blank"
          rel="noopener noreferrer"
          title="Django is a registered trademark of the Django Software Foundation"
        >
          <img
            class="light-only"
            src="/brand/django-logo-positive.svg"
            alt=""
            width="54"
            height="18"
            decoding="async"
          >
          <img
            class="dark-only"
            src="/brand/django-logo-negative.svg"
            alt=""
            width="54"
            height="18"
            decoding="async"
          >
          <span>Built for Django</span>
        </a>
      </div>

      <div class="center">
        <template v-for="link in contactLinks" :key="link.href">
          <a
            v-if="link.external"
            class="text-link"
            :href="link.href"
            :target="link.href.startsWith('mailto:') ? undefined : '_blank'"
            :rel="link.href.startsWith('mailto:') ? undefined : 'noopener noreferrer'"
          >
            {{ link.text }}
          </a>
          <NuxtLink
            v-else
            class="text-link"
            :to="link.href"
          >
            {{ link.text }}
          </NuxtLink>
        </template>
      </div>

      <div class="right">
        <a
          v-for="icon in icons"
          :key="icon.label"
          class="icon-link"
          :aria-label="icon.label"
          :href="icon.href"
          target="_blank"
          :rel="icon?.rel || 'noopener noreferrer'"
        >
          <Icon :name="icon.icon" />
        </a>
        <AppSocialIcons />
      </div>
    </Container>
  </footer>
</template>

<style scoped>
.hurricane-footer {
  display: flex;
  min-height: 5.5rem;
  border-top: 1px solid rgba(156, 163, 175, 0.25);
  padding: 1.25rem 0;
}
html.dark .hurricane-footer {
  border-top-color: rgba(75, 85, 99, 0.4);
}

.footer-container {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  justify-items: center;
  gap: 0.75rem;
  width: 100%;
}
@media (min-width: 640px) {
  .footer-container {
    justify-items: stretch;
  }
}

.brand {
  grid-column: span 12;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.55rem;
  order: 1;
  padding: 0.5rem 0;
}
@media (min-width: 640px) {
  .brand {
    grid-column: span 3;
    align-items: flex-start;
    order: 0;
  }
}

.blueshoe-link {
  display: inline-flex;
  line-height: 0;
  transition: opacity 0.15s ease;
}
.blueshoe-link:hover {
  opacity: 0.85;
}

.blueshoe-logo {
  display: block;
  height: 2.85rem;
  width: auto;
  max-width: 9.5rem;
  object-fit: contain;
  object-position: left center;
}

.brand-copy {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 500;
  color: #6b7280;
}
html.dark .brand-copy {
  color: #9ca3af;
}

.django-footer-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.15rem;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  text-decoration: none;
  color: #0c4b33;
}
html.dark .django-footer-badge {
  color: #89e7c3;
}
.django-footer-badge img {
  height: 0.9rem;
  width: auto;
}

.light-only {
  display: block;
}
.dark-only {
  display: none;
}
html.dark .light-only {
  display: none;
}
html.dark .dark-only {
  display: block;
}

.center {
  grid-column: span 12;
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-wrap: wrap;
}
@media (min-width: 640px) {
  .center {
    grid-column: span 6;
    flex-direction: row;
    justify-content: center;
  }
}

.text-link {
  padding: 0.4rem 0.55rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: #6b7280;
  text-decoration: none;
}
.text-link:hover {
  color: #0c4b33;
}
html.dark .text-link {
  color: #9ca3af;
}
html.dark .text-link:hover {
  color: #e5e7eb;
}

.right {
  grid-column: span 12;
  display: flex;
  align-items: center;
  justify-content: center;
}
@media (min-width: 640px) {
  .right {
    grid-column: span 3;
    justify-content: flex-end;
  }
}

.icon-link {
  display: flex;
  padding: 0.75rem;
  color: #6b7280;
}
.icon-link:hover {
  color: #0c4b33;
}
</style>
