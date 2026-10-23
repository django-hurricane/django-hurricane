<script setup lang="ts">
import { ref } from 'vue'

const props = withDefaults(
  defineProps<{
    version?: string
    date?: string
    githubUrl?: string
    pypiUrl?: string
    snippetUv?: string
    snippetPip?: string
  }>(),
  {
    version: '2.0.0rc2',
    date: 'October 2026',
    githubUrl: 'https://github.com/django-hurricane/django-hurricane/releases/tag/2.0.0rc2',
    pypiUrl: 'https://pypi.org/project/django-hurricane/2.0.0rc2/',
    snippetUv: 'uv add django-hurricane==2.0.0rc2',
    snippetPip: 'pip install django-hurricane==2.0.0rc2'
  }
)

const activeTab = ref<'uv' | 'pip'>('uv')
const copied = ref(false)

const copyCommand = async () => {
  const text = activeTab.value === 'uv' ? props.snippetUv : props.snippetPip
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      await navigator.clipboard.writeText(text)
      copied.value = true
      setTimeout(() => {
        copied.value = false
      }, 2000)
    }
  } catch (err) {
    // Fallback or ignore
  }
}
</script>

<template>
  <div class="latest-release-card" id="latest-release-card">
    <!-- Header with Badges -->
    <div class="release-header">
      <div class="badge-group">
        <span class="live-badge">
          <span class="pulse-dot"></span>
          LATEST RELEASE
        </span>
        <span class="version-tag">v{{ version }}</span>
        <span v-if="date" class="date-tag">{{ date }}</span>
      </div>

      <div class="release-links">
        <a :href="githubUrl" target="_blank" rel="noopener noreferrer" class="release-btn github-btn">
          <svg class="btn-icon" viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
            <path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
          </svg>
          <span>GitHub Release</span>
        </a>
        <a :href="pypiUrl" target="_blank" rel="noopener noreferrer" class="release-btn pypi-btn">
          <svg class="btn-icon" viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
            <path d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zm-.75 4.5h1.5v4.5h-1.5v-4.5zm0 6h1.5v4.5h-1.5v-4.5zM12 4.5a7.5 7.5 0 110 15 7.5 7.5 0 010-15z" opacity="0.3"/>
            <path d="M11.95 2C6.46 2 2 6.48 2 12s4.46 10 9.95 10c5.55 0 10.05-4.48 10.05-10S17.5 2 11.95 2zm-1.2 3.65h2.5v2.5h-2.5V5.65zm0 4.15h2.5v7.55h-2.5V9.8z"/>
          </svg>
          <span>View on PyPI</span>
        </a>
      </div>
    </div>

    <!-- Main Title & Summary -->
    <div class="release-body">
      <h3 class="release-title">
        Django Hurricane {{ version }}
      </h3>
      <p class="release-desc">
        A major evolution of Django Hurricane featuring an async Rust-powered HTTP engine, instant bot defense, and shared-memory observability designed for high-concurrency cloud deployments.
      </p>

      <!-- Key Improvements Grid -->
      <div class="highlights-grid">
        <div class="highlight-item">
          <div class="highlight-icon">⚡</div>
          <div class="highlight-text">
            <strong>Granian Rust Engine</strong>
            <span>High-throughput HTTP runtime replacing Tornado with native ASGI & WSGI handling.</span>
          </div>
        </div>
        <div class="highlight-item">
          <div class="highlight-icon">🛡️</div>
          <div class="highlight-text">
            <strong>Fast-404 Security Defense</strong>
            <span>Drops automated vulnerability scans (.php, .env) in microseconds before hitting Django.</span>
          </div>
        </div>
        <div class="highlight-item">
          <div class="highlight-icon">⏱️</div>
          <div class="highlight-text">
            <strong>Token-Bucket Rate Limiter</strong>
            <span>Per-IP volumetric throttling with zero log-flooding overhead to prevent log DoS.</span>
          </div>
        </div>
        <div class="highlight-item">
          <div class="highlight-icon">📊</div>
          <div class="highlight-text">
            <strong>Shared-Memory Metrics</strong>
            <span>Lock-free atomic POSIX shared memory buffers aggregating cross-worker Prometheus state.</span>
          </div>
        </div>
      </div>

      <!-- Quick Install Box -->
      <div class="install-box">
        <div class="install-header">
          <span class="install-label">Quick Install:</span>
          <div class="tab-toggle">
            <button
              type="button"
              :class="['tab-btn', { active: activeTab === 'uv' }]"
              @click="activeTab = 'uv'"
            >
              uv
            </button>
            <button
              type="button"
              :class="['tab-btn', { active: activeTab === 'pip' }]"
              @click="activeTab = 'pip'"
            >
              pip
            </button>
          </div>
        </div>
        <div class="install-command">
          <code>{{ activeTab === 'uv' ? snippetUv : snippetPip }}</code>
          <button type="button" class="copy-btn" @click="copyCommand" :title="copied ? 'Copied!' : 'Copy to clipboard'">
            <span v-if="copied" class="copied-indicator">✓ Copied</span>
            <span v-else class="copy-label">Copy</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.latest-release-card {
  position: relative;
  border-radius: 1.25rem;
  border: 1px solid rgba(13, 148, 136, 0.35);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.95) 0%, rgba(240, 253, 250, 0.6) 100%);
  box-shadow: 0 4px 20px -2px rgba(13, 148, 136, 0.08);
  padding: 1.75rem 2rem;
  margin: 2rem 0;
  transition: all 0.25s ease-in-out;
}

html.dark .latest-release-card {
  border-color: rgba(20, 184, 166, 0.3);
  background: linear-gradient(145deg, rgba(15, 23, 42, 0.9) 0%, rgba(13, 148, 136, 0.12) 100%);
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
}

.latest-release-card:hover {
  border-color: rgba(13, 148, 136, 0.6);
  box-shadow: 0 10px 30px -4px rgba(13, 148, 136, 0.16);
}

.release-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid rgba(156, 163, 175, 0.2);
}

html.dark .release-header {
  border-bottom-color: rgba(75, 85, 99, 0.3);
}

.badge-group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.625rem;
}

.live-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.6875rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  padding: 0.25rem 0.625rem;
  border-radius: 9999px;
  background-color: #0d9488;
  color: #ffffff;
  text-transform: uppercase;
}

.pulse-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 9999px;
  background-color: #a7f3d0;
  animation: pulse-animation 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse-animation {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.4;
    transform: scale(1.3);
  }
}

.version-tag {
  font-size: 0.8125rem;
  font-weight: 700;
  font-family: monospace;
  padding: 0.2rem 0.5rem;
  border-radius: 0.375rem;
  background-color: rgba(13, 148, 136, 0.12);
  color: #0d9488;
}

html.dark .version-tag {
  background-color: rgba(45, 212, 191, 0.15);
  color: #2dd4bf;
}

.date-tag {
  font-size: 0.8125rem;
  color: #6b7280;
}

html.dark .date-tag {
  color: #9ca3af;
}

.release-links {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.release-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  padding: 0.45rem 0.875rem;
  border-radius: 0.5rem;
  text-decoration: none;
  transition: all 0.2s ease;
}

.github-btn {
  background-color: #0f172a;
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

html.dark .github-btn {
  background-color: #1e293b;
  color: #f8fafc;
  border: 1px solid rgba(255, 255, 255, 0.15);
}

.github-btn:hover {
  background-color: #0284c7;
  color: #ffffff;
  transform: translateY(-1px);
}

.pypi-btn {
  background-color: rgba(13, 148, 136, 0.12);
  color: #0f766e;
  border: 1px solid rgba(13, 148, 136, 0.3);
}

html.dark .pypi-btn {
  background-color: rgba(45, 212, 191, 0.15);
  color: #5eead4;
  border-color: rgba(45, 212, 191, 0.3);
}

.pypi-btn:hover {
  background-color: #0d9488;
  color: #ffffff;
  transform: translateY(-1px);
}

.release-body {
  padding-top: 1.25rem;
}

.release-title {
  font-size: 1.5rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 0 0 0.5rem 0;
  color: #111827;
}

html.dark .release-title {
  color: #f9fafb;
}

.release-desc {
  font-size: 1rem;
  line-height: 1.6;
  margin: 0 0 1.5rem 0;
  color: #4b5563;
}

html.dark .release-desc {
  color: #9ca3af;
}

.highlights-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  margin-bottom: 1.75rem;
}

@media (min-width: 640px) {
  .highlights-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.highlight-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  border-radius: 0.75rem;
  background-color: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(156, 163, 175, 0.2);
}

html.dark .highlight-item {
  background-color: rgba(17, 24, 39, 0.5);
  border-color: rgba(75, 85, 99, 0.3);
}

.highlight-icon {
  font-size: 1.25rem;
  line-height: 1;
  flex-shrink: 0;
  margin-top: 0.125rem;
}

.highlight-text {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.875rem;
  line-height: 1.4;
}

.highlight-text strong {
  color: #111827;
  font-weight: 700;
}

html.dark .highlight-text strong {
  color: #f3f4f6;
}

.highlight-text span {
  color: #6b7280;
  font-size: 0.8125rem;
}

html.dark .highlight-text span {
  color: #9ca3af;
}

.install-box {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.875rem 1.25rem;
  border-radius: 0.75rem;
  background-color: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

html.dark .install-box {
  background-color: #090d16;
  border-color: rgba(255, 255, 255, 0.08);
}

.install-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.install-label {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
}

.tab-toggle {
  display: flex;
  gap: 0.25rem;
  background-color: rgba(255, 255, 255, 0.1);
  padding: 0.125rem;
  border-radius: 0.375rem;
}

.tab-btn {
  background: transparent;
  border: none;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.5rem;
  border-radius: 0.25rem;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s ease;
}

.tab-btn.active {
  background-color: #0d9488;
  color: #ffffff;
}

.install-command {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.install-command code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.875rem;
  color: #5eead4;
  word-break: break-all;
}

.copy-btn {
  background-color: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #f1f5f9;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.35rem 0.65rem;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.copy-btn:hover {
  background-color: #0d9488;
  border-color: #0d9488;
  color: #ffffff;
}

.copied-indicator {
  color: #34d399;
}
</style>
