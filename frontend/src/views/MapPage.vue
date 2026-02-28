<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import L from 'leaflet'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const errorMsg = ref('')
const itineraryData = ref(null)
const selectedDay = ref(0) // Índice del tab (0, 1, 2...)

const mapContainer = ref(null)
let mapInstance = null
let mapMarkers = []
let mapPolyline = null

// Arrays de colores de tierras para distinguir los días
const ROUTE_COLORS = ['#8B5A2B', '#4A5D43', '#C05727', '#2C3E50', '#8c2425', '#5c4033']

const fetchItinerary = async () => {
  try {
    const response = await axios.get(`http://localhost:8000/itinerary/${route.params.id}`)
    itineraryData.value = response.data
    
    loading.value = false // Liberar el DOM render
    
    // Iniciar mapa cuando tenemos datos (en el nextTick para asegurar el ref del contenedor)
    await nextTick()
    setTimeout(() => {
      initMap()
      drawDayLayer(0)
    }, 100)
    
  } catch (err) {
    console.error(err)
    errorMsg.value = err.response?.data?.detail || 'No se pudo cargar el itinerario.'
    loading.value = false
  }
}

const initMap = () => {
  if (!mapContainer.value) return

  // Icono por defecto (fix bug de Leaflet con Webpack/Vite)
  delete L.Icon.Default.prototype._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: new URL('leaflet/dist/images/marker-icon-2x.png', import.meta.url).href,
    iconUrl: new URL('leaflet/dist/images/marker-icon.png', import.meta.url).href,
    shadowUrl: new URL('leaflet/dist/images/marker-shadow.png', import.meta.url).href,
  });

  mapInstance = L.map(mapContainer.value).setView([0, 0], 2)

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
  }).addTo(mapInstance)
}

const drawDayLayer = (dayIndex) => {
  if (!mapInstance || !itineraryData.value) return

  // Limpiar capas anteriores
  mapMarkers.forEach(m => mapInstance.removeLayer(m))
  mapMarkers = []
  if (mapPolyline) mapInstance.removeLayer(mapPolyline)

  const dayKey = `day_${dayIndex + 1}`
  const pois = itineraryData.value.itinerary[dayKey]

  if (!pois || pois.length === 0) return

  const color = ROUTE_COLORS[dayIndex % ROUTE_COLORS.length]
  const latlngs = []

  // Crear markers
  pois.forEach((poi, index) => {
    // Las coordenadas de Claude / Nominatim suelen venir en [lat, lon]
    const latlng = [poi.coords[0], poi.coords[1]]
    latlngs.push(latlng)

    const marker = L.marker(latlng).addTo(mapInstance)
        // Popup bonito
      marker.bindPopup(`<b>${index + 1}. ${poi.site}</b>`)
      mapMarkers.push(marker)
  })

  // Crear Polyline conectando los puntos
  if (latlngs.length > 1) {
    mapPolyline = L.polyline(latlngs, {
      color: color,
      weight: 4,
      opacity: 0.8,
      dashArray: '10, 10'
    }).addTo(mapInstance)
  }

  // Ajustar vista para englobar todos los puntos
  const group = new L.featureGroup(mapMarkers)
  mapInstance.fitBounds(group.getBounds(), { padding: [50, 50] })

  // Forzar redibujado para evitar errores de renderizado de Leaflet en contenedores dinámicos
  setTimeout(() => {
    mapInstance.invalidateSize()
  }, 250)
}

// Cuando cambia el tab, redibujamos
watch(selectedDay, (newVal) => {
  if (!loading.value) {
    drawDayLayer(newVal)
  }
})

onMounted(() => {
  fetchItinerary()
})
</script>

<template>
  <v-container fluid class="fill-height pa-0 vintage-bg" style="position: relative;">
    <div class="paper-texture"></div>

    <!-- Skeleton loader / Error handling -->
    <div v-if="loading" class="d-flex fill-height justify-center align-center w-100 position-relative overflow-hidden" style="z-index: 2;">
      <div class="text-center">
        <v-icon icon="mdi-compass-outline" class="mb-6 spin-slow" size="80" color="var(--color-accent-leather)"></v-icon>
        <h3 class="text-display text-h5 text-ink tracking-widest serif-text cartography-title">DESENROLLANDO PERGAMINOS...</h3>
      </div>
    </div>
    
    <div v-else-if="errorMsg" class="d-flex fill-height justify-center align-center w-100" style="z-index: 2;">
      <v-card class="pa-8 text-center paper-card border-error" max-width="500">
        <v-icon icon="mdi-alert-octagon-outline" color="#C05727" size="64" class="mb-4"></v-icon>
        <h3 class="text-display text-h5 text-rust mb-2 tracking-widest serif-text">Ruta Extraviada</h3>
        <p class="mb-8 text-ink-light font-italic">{{ errorMsg }}</p>
        <v-btn color="var(--color-accent-leather)" variant="outlined" class="vintage-btn" @click="router.push('/plan')">Reorientar Brújula</v-btn>
      </v-card>
    </div>

    <!-- Main View -->
    <v-row no-gutters class="fill-height map-page-layout" v-else style="z-index: 2;">
      
      <!-- Diario de Viaje (Sidebar) -->
      <v-col cols="12" md="4" class="d-flex flex-column h-100 paper-sidebar sidebar-col order-2 order-md-1 position-relative">
        
        <!-- Header -->
        <div class="pa-6 border-b-vintage position-relative">
          <div class="d-flex align-center justify-space-between mb-6">
            <div>
              <div class="text-caption text-moss tracking-widest font-weight-bold mb-1 text-uppercase">DIARIO DE EXPEDICIÓN</div>
              <h2 class="text-display text-h4 font-weight-bold text-ink text-uppercase cartography-title">{{ itineraryData.city.split(',')[0] }}</h2>
              <span class="text-body-2 text-ink-light tracking-wide font-italic">Estimación: {{ itineraryData.days }} Jornadas</span>
            </div>
            <v-btn icon="mdi-book-arrow-left-outline" variant="text" color="var(--color-accent-leather)" @click="router.push('/')" title="Cerrar Diario"></v-btn>
          </div>
          
          <v-tabs v-model="selectedDay" bg-color="transparent" color="var(--color-accent-rust)" slider-color="var(--color-accent-rust)" grow class="vintage-tabs text-display">
            <v-tab v-for="n in itineraryData.days" :key="n" :value="n - 1" class="font-weight-bold tracking-widest serif-text">
              D.{{ n }}
            </v-tab>
          </v-tabs>
        </div>

        <!-- Lista de lugares -->
        <v-list class="flex-grow-1 overflow-y-auto pa-4 bg-transparent position-relative">
          <v-timeline density="compact" align="start" truncate-line="both" line-color="rgba(139, 90, 43, 0.4)">
            <v-timeline-item
              v-for="(poi, index) in itineraryData.itinerary['day_' + (selectedDay + 1)]"
              :key="index"
              :dot-color="ROUTE_COLORS[selectedDay % ROUTE_COLORS.length]"
              size="small"
              icon="mdi-map-marker"
              icon-color="#F5EEDA"
              fill-dot
            >
              <template v-slot:opposite>
                <div class="text-caption font-weight-bold text-leather tracking-widest">
                  Nº {{ index + 1 }}
                </div>
              </template>
              <div class="mb-6 pb-2 border-b-dashed">
                <div class="text-display font-weight-bold text-h6 text-ink mb-1 cartography-title">{{ poi.site }}</div>
                <div class="text-caption text-ink-light font-italic tracking-wide">
                  Coord: {{ poi.coords[0].toFixed(4) }}°N, {{ poi.coords[1].toFixed(4) }}°E
                </div>
              </div>
            </v-timeline-item>
          </v-timeline>
          
          <div v-if="!itineraryData.itinerary['day_' + (selectedDay + 1)]?.length" class="text-center pa-8 text-ink-light tracking-widest text-caption border-dashed mt-4 font-italic">
            [ Páginas en blanco en esta jornada ]
          </div>
        </v-list>
      </v-col>

      <!-- Mapa -->
      <v-col cols="12" md="8" class="h-100 d-flex flex-column position-relative pa-0 map-col order-1 order-md-2">
        <div ref="mapContainer" class="w-100 flex-grow-1 map-container vintage-map-filter"></div>
        <!-- Torn Edges Effect overlay -->
        <div class="map-overlay-edges"></div>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
.vintage-bg {
  background-color: var(--color-bg-paper) !important;
}

.paper-texture {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background-image: url('data:image/svg+xml,%3Csvg width="200" height="200" xmlns="http://www.w3.org/2000/svg"%3E%3Cfilter id="noise"%3E%3CfeTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves="3" stitchTiles="stitch"/%3E%3C/filter%3E%3Crect width="200" height="200" fill="transparent"/%3E%3Crect width="200" height="200" filter="url(%23noise)" opacity="0.08"/%3E%3C/svg%3E');
  z-index: 1;
  pointer-events: none;
}

.map-page-layout {
  flex-direction: column;
}

@media (min-width: 960px) {
  .map-page-layout {
    flex-direction: row;
    flex-wrap: nowrap;
  }
}

.map-container {
  width: 100%;
  height: 100%;
  z-index: 1; 
}

/* Vintage Map CSS Filter */
.vintage-map-filter {
  filter: sepia(0.6) hue-rotate(-15deg) contrast(0.9) brightness(0.95);
}

/* Sidebar imitating a travel journal */
.paper-sidebar {
  background-color: rgba(245, 238, 218, 0.95) !important;
  border-right: 2px solid rgba(139, 90, 43, 0.3);
  box-shadow: 10px 0 30px rgba(44, 62, 80, 0.15);
}

.paper-card {
  background-color: rgba(245, 238, 218, 0.95);
  border: 1px solid rgba(139, 90, 43, 0.4);
  box-shadow: 0 10px 30px rgba(44, 62, 80, 0.2);
}

.border-b-vintage {
  border-bottom: 2px solid rgba(139, 90, 43, 0.2);
  background: linear-gradient(to bottom, transparent 95%, rgba(139, 90, 43, 0.05) 100%);
}

.border-b-dashed {
  border-bottom: 1px dashed rgba(139, 90, 43, 0.3);
}
.border-dashed {
  border: 1px dashed rgba(139, 90, 43, 0.4);
}

.text-ink { color: var(--color-text-ink); }
.text-ink-light { color: #5a6b7c; }
.text-leather { color: var(--color-accent-leather); }
.text-moss { color: var(--color-accent-moss); }
.text-rust { color: var(--color-accent-rust); }

.serif-text { font-family: var(--font-display); }

.cartography-title {
  letter-spacing: 0.05em;
  text-shadow: 1px 1px 0px rgba(255,255,255,0.8);
}

.tracking-widest { letter-spacing: 0.15em; }
.tracking-wide { letter-spacing: 0.05em; }

/* Tabs */
.vintage-tabs {
  border-bottom: 1px solid rgba(139, 90, 43, 0.2);
}

.spin-slow { animation: spin 4s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

/* Map Col */
.map-col {
  height: 50vh !important;
  min-height: 50vh;
  background-color: #E6D5B8; /* Fallback map background */
}

/* Torn edges map overlay (inner shadow) */
.map-overlay-edges {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  box-shadow: inset 0 0 50px rgba(139, 90, 43, 0.4);
  pointer-events: none;
  z-index: 400;
}

@media (min-width: 960px) {
  .map-col {
    height: 100vh !important;
    min-height: 100vh;
  }
}

/* Leaflet Popup overrides for Vintage theme */
:deep(.leaflet-popup-content-wrapper), :deep(.leaflet-popup-tip) {
  background: #F5EEDA !important;
  color: var(--color-text-ink) !important;
  border: 1px solid rgba(139, 90, 43, 0.5) !important;
  box-shadow: 4px 4px 15px rgba(44, 62, 80, 0.2) !important;
  border-radius: 2px !important;
}

:deep(.leaflet-popup-content) {
  font-family: var(--font-display) !important;
  font-weight: 700;
  font-size: 1.1em;
  text-align: center;
}

/* Scrollbar Vintage */
.overflow-y-auto::-webkit-scrollbar { width: 6px; }
.overflow-y-auto::-webkit-scrollbar-track { background: transparent; }
.overflow-y-auto::-webkit-scrollbar-thumb { 
  background: rgba(139, 90, 43, 0.4); 
  border-radius: 3px; 
}
.overflow-y-auto::-webkit-scrollbar-thumb:hover { background: rgba(139, 90, 43, 0.6); }
</style>
