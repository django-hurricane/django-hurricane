<template>
  <div class="ecosystem-cards-grid">
    <slot />
  </div>
</template>

<style scoped>
.ecosystem-cards-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.5rem;
  margin: 2rem 0;
}
@media (min-width: 768px) {
  .ecosystem-cards-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
