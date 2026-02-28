<script setup>
import { RouterView } from 'vue-router'
</script>

<template>
  <v-app>
    <v-main>
      <RouterView />
    </v-main>
  </v-app>
</template>

<style>
:root {
  --color-bg-paper: #F5EEDA;
  --color-text-ink: #2C3E50;
  --color-accent-moss: #4A5D43;
  --color-accent-leather: #8B5A2B;
  --color-accent-rust: #C05727;
  
  --font-display: 'Playfair Display', serif;
  --font-body: 'Lato', sans-serif;
}

html, body {
  background-color: var(--color-bg-paper);
  background-image: url('data:image/svg+xml,%3Csvg width="100" height="100" xmlns="http://www.w3.org/2000/svg"%3E%3Cfilter id="noise"%3E%3CfeTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="3" stitchTiles="stitch"/%3E%3C/filter%3E%3Crect width="100" height="100" fill="%23f5eeda"/%3E%3Crect width="100" height="100" filter="url(%23noise)" opacity="0.05"/%3E%3C/svg%3E');
  color: var(--color-text-ink);
  font-family: var(--font-body);
  margin: 0;
  padding: 0;
}

#app {
  font-family: var(--font-body);
}

.text-display {
  font-family: var(--font-display) !important;
}

/* Utilería visual global: Sombras suaves y bordes irregulares */
.vintage-shadow {
  box-shadow: 2px 4px 15px rgba(139, 90, 43, 0.15);
}

.vintage-border {
  border-radius: 2% 4% 3% 5% / 5% 3% 4% 2%;
  border: 1px solid rgba(139, 90, 43, 0.2);
}
</style>
