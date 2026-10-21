<template>
  <div class="feature-boxes-grid">
    <slot />
  </div>
</template>

<style scoped>
.feature-boxes-grid {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}
@media (min-width: 640px) {
  .feature-boxes-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (min-width: 1024px) {
  .feature-boxes-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
