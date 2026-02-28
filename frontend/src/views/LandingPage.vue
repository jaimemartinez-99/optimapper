<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const startPlanning = () => {
  router.push('/plan')
}

const suggestedRoutes = [
  { city: 'Florencia, Italia', days: 5, img: 'https://images.unsplash.com/photo-1542385151-efd9000785a0?q=80&w=800&height=600', span: 2 },
  { city: 'Kyoto, Japón', days: 3, img: 'https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?q=80&w=400&height=300', span: 1 },
  { city: 'Marrakech, Marruecos', days: 4, img: 'https://images.unsplash.com/photo-1539020140153-e479b8c22e70?q=80&w=400&height=300', span: 1 }
]
</script>

<template>
  <v-container fluid class="fill-height pa-0 m-0 vintage-bg position-relative overflow-hidden">
    <!-- Texture overlay -->
    <div class="paper-texture"></div>

    <v-row no-gutters class="fill-height w-100 position-relative" style="z-index: 2;">
      <!-- Hero Section -->
      <v-col cols="12" class="d-flex flex-column justify-center align-center text-center pa-4 pa-sm-8 pa-md-12 min-vh-100">
        
        <!-- Cartographic Map Graphic Behind Content -->
        <div class="antique-map-bg fade-in-map"></div>

        <div class="expedition-card pa-8 pa-md-12 text-center fade-in-up">
          <div class="d-flex justify-center mb-6">
            <div class="compass-icon">
              <v-icon icon="mdi-compass-outline" size="80" color="var(--color-accent-leather)"></v-icon>
            </div>
          </div>
          
          <h1 class="text-display text-h3 text-md-h2 font-weight-bold mb-4 text-ink cartography-title">
            OPTI<span class="text-rust">MAPPER</span>
          </h1>
          
          <div class="divider-ornate mx-auto mb-6"></div>
          
          <p class="text-body-1 text-md-h5 mb-10 max-w-700 mx-auto font-weight-regular text-ink-light line-height-relaxed serif-text">
            Forjamos itinerarios de expedición con precisión matemática y el alma de un explorador clásico. 
            <br><br>
            <span class="text-caption text-uppercase text-moss font-weight-bold tracking-widest">— El mundo aguarda ser trazado —</span>
          </p>
        
          <button class="leather-btn" @click="startPlanning">
            <span class="leather-btn-content d-flex align-center justify-center">
              <v-icon icon="mdi-map-search-outline" class="mr-3" size="small"></v-icon>
              INICIAR EXPEDICIÓN
            </span>
          </button>
        </div>
        
        <!-- Flecha estilo plumilla -->
        <div class="scroll-indicator mt-16 fade-in-up" style="animation-delay: 0.5s;">
          <v-icon icon="mdi-feather" color="var(--color-accent-leather)" size="36" class="bounce"></v-icon>
        </div>
      </v-col>

      <!-- Suggested Itineraries (Vintage Gallery) -->
      <v-col cols="12" class="pa-4 pa-md-12 position-relative" style="z-index: 2; background-color: rgba(245, 238, 218, 0.9);">
        
        <div class="text-center mb-10">
          <v-icon icon="mdi-book-open-page-variant-outline" color="var(--color-accent-moss)" size="40" class="mb-2"></v-icon>
          <h2 class="text-display text-h4 font-weight-bold text-ink mb-2">Expediciones Pasadas</h2>
          <div class="divider-ornate mx-auto"></div>
        </div>
        
        <div class="polaroid-grid">
          <div 
            v-for="(route, i) in suggestedRoutes" 
            :key="i"
            class="polaroid-item cursor-pointer"
            :class="route.span === 2 ? 'span-2' : 'span-1'"
            @click="startPlanning"
          >
            <div class="polaroid-frame">
              <v-img :src="route.img" cover class="polaroid-img"></v-img>
              <div class="polaroid-caption text-center mt-4">
                <h3 class="text-display text-h6 font-weight-bold text-ink mb-1">{{ route.city }}</h3>
                <div class="text-caption text-leather font-weight-bold tracking-widest stamp-text">
                  D. {{ route.days }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
/* Base Theme */
.vintage-bg {
  background-color: var(--color-bg-paper);
}

.min-vh-100 {
  min-height: 100vh;
}

.text-ink { color: var(--color-text-ink); }
.text-ink-light { color: #4A5568; }
.text-rust { color: var(--color-accent-rust); }
.text-moss { color: var(--color-accent-moss); }
.text-leather { color: var(--color-accent-leather); }

/* Texture & Map Background */
.paper-texture {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background-image: url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAyBAMAAADsEZWCAAAAGFBMVEUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/H9bDAAAACHRSTlMAAAAAAAB/f39+YwD5AAAAgElEQVQ4y2NgQAX8DIwgQkxMDGzMDHwMDEwMLAwMTIwMjEwMjEwMTIwMjEAuxMTMwMDMwAAWZWFgZ2AAcxkYWJgZmBkYGBmYGBgZmBkYmJkYGFjYGRoYmBiaGJgZmRgYmZkY2BgYmJkYGBmZGBiYmRkAAkwMDEyMTBxgwMTEwMDAAABkKBgE2oJ1LAAAAABJRU5ErkJggg==");
  background-repeat: repeat;
  opacity: 0.15;
  z-index: 1;
  pointer-events: none;
}

.antique-map-bg {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  width: 90vw;
  height: 90vh;
  max-width: 1200px;
  background-image: url('https://images.unsplash.com/photo-1524661135-423995f22d0b?q=80&w=2000&auto=format&fit=crop');
  background-size: cover;
  background-position: center;
  opacity: 0.15;
  filter: sepia(0.8) contrast(1.2) hue-rotate(-10deg);
  border-radius: 50%;
  mask-image: radial-gradient(circle, black 30%, transparent 70%);
  -webkit-mask-image: radial-gradient(circle, black 30%, transparent 70%);
  z-index: 0;
}

/* Vintage Card/Container */
.expedition-card {
  background-color: rgba(245, 238, 218, 0.95); /* More opaque, no blur */
  border-radius: 2% 4% 3% 5% / 5% 3% 4% 2%;
  border: 1px solid rgba(139, 90, 43, 0.3);
  box-shadow: 0 10px 30px rgba(44, 62, 80, 0.1), inset 0 0 20px rgba(139, 90, 43, 0.05);
  max-width: 800px;
  width: 100%;
  position: relative;
}

/* Typography Tweaks */
.tracking-widest { letter-spacing: 0.15em; }
.line-height-relaxed { line-height: 1.8; }
.max-w-700 { max-width: 700px; padding: 0 1rem; }
.serif-text { font-family: var(--font-display); }

.cartography-title {
  letter-spacing: 0.05em;
  text-shadow: 1px 1px 0px rgba(255,255,255,0.8), 2px 2px 4px rgba(0,0,0,0.1);
}

.divider-ornate {
  width: 100px;
  height: 2px;
  background: var(--color-accent-leather);
  position: relative;
}
.divider-ornate::before, .divider-ornate::after {
  content: '';
  position: absolute;
  top: -3px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-accent-leather);
}
.divider-ornate::before { left: -4px; }
.divider-ornate::after { right: -4px; }

/* Leather/Brass Compass Icon */
.compass-icon {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  border: 4px solid var(--color-accent-leather);
  background: radial-gradient(circle, #E6D5B8 0%, #D4B886 100%);
  box-shadow: 
    inset 0 0 15px rgba(139, 90, 43, 0.5), 
    0 5px 15px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.compass-icon::after {
  content: '';
  position: absolute;
  width: 110px; height: 110px;
  border-radius: 50%;
  border: 1px dashed var(--color-accent-leather);
  opacity: 0.5;
}

/* Analog Leather Button */
.leather-btn {
  background: transparent;
  padding: 6px;
  cursor: pointer;
  position: relative;
  transition: all 0.2s ease;
}

.leather-btn-content {
  background: linear-gradient(135deg, var(--color-accent-rust) 0%, #8E3A1A 100%);
  color: #F5EEDA;
  padding: 16px 48px;
  border-radius: 3% 2% 4% 3% / 2% 4% 3% 2%;
  border: 2px solid #5A2B0E;
  font-family: var(--font-body);
  font-weight: 700;
  letter-spacing: 0.1em;
  box-shadow: 
    inset 0 2px 0 rgba(255,255,255,0.2),
    inset 0 -2px 0 rgba(0,0,0,0.3),
    0 6px 10px rgba(0,0,0,0.2);
  transition: all 0.2s ease;
  text-shadow: 1px 1px 2px rgba(0,0,0,0.4);
}

.leather-btn:hover .leather-btn-content {
  transform: translateY(-2px);
  box-shadow: 
    inset 0 2px 0 rgba(255,255,255,0.3),
    inset 0 -2px 0 rgba(0,0,0,0.3),
    0 8px 15px rgba(0,0,0,0.25);
  background: linear-gradient(135deg, #D46932 0%, #9A401C 100%);
}

.leather-btn:active .leather-btn-content {
  transform: translateY(2px);
  box-shadow: 
    inset 0 2px 5px rgba(0,0,0,0.4),
    0 2px 0px rgba(0,0,0,0.1);
}

/* Polaroid Grid */
.polaroid-grid {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 32px;
  max-width: 1200px;
  margin: 0 auto;
}

.polaroid-item {
  width: 320px;
  margin-bottom: 20px;
  transition: transform 0.3s ease-out;
}

/* Rotaciones orgánicas asimétricas para que parezcan tiradas en la mesa */
.polaroid-item:nth-child(1) { transform: rotate(-3deg); }
.polaroid-item:nth-child(2) { transform: rotate(4deg); margin-top: 20px; }
.polaroid-item:nth-child(3) { transform: rotate(-1deg); margin-top: -10px;}

.polaroid-item:hover {
  transform: rotate(0deg) scale(1.05) translateY(-10px);
  z-index: 10;
}

.polaroid-frame {
  background: #FFF9ED;
  padding: 16px 16px 24px 16px;
  box-shadow: 2px 4px 15px rgba(44, 62, 80, 0.15), 0 10px 30px rgba(0,0,0,0.1);
  border: 1px solid rgba(0,0,0,0.05);
  border-radius: 2px;
  position: relative;
}

/* Vintage tape effect */
.polaroid-frame::before {
  content: '';
  position: absolute;
  top: -10px;
  left: 50%;
  transform: translateX(-50%) rotate(-2deg);
  width: 80px;
  height: 25px;
  background-color: rgba(255, 255, 255, 0.4);
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  border: 1px solid rgba(0,0,0,0.05);
  z-index: 2;
}

.polaroid-img {
  height: 240px;
  width: 100%;
  filter: sepia(0.3) contrast(1.1) opacity(0.9);
  border: 1px solid rgba(0,0,0,0.1);
  border-radius: 2px;
}

.polaroid-item:hover .polaroid-img {
  filter: sepia(0) contrast(1.1) opacity(1);
}

.stamp-text {
  font-family: 'Courier New', Courier, monospace;
  position: relative;
  display: inline-block;
  padding: 4px 8px;
  border: 2px solid var(--color-accent-leather);
  border-radius: 4px;
  transform: rotate(-5deg);
  opacity: 0.8;
}

/* Animations */
.fade-in-up {
  animation: fadeInUp 1s cubic-bezier(0.165, 0.84, 0.44, 1) forwards;
  opacity: 0;
  transform: translateY(30px);
}

.fade-in-map {
  animation: fadeIn 2s ease forwards;
  opacity: 0;
}

@keyframes fadeInUp {
  to { opacity: 1; transform: translateY(0); }
}

@keyframes fadeIn {
  to { opacity: 0.15; }
}

.bounce {
  animation: bounce 2s infinite;
}

@keyframes bounce {
  0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
  40% { transform: translateY(-10px); }
  60% { transform: translateY(-5px); }
}
</style>
