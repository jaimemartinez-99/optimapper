<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import TravelMap from '../components/TravelMap.vue'
import { apiError, safeExternalUrl, takeItinerary } from '../services/itinerarySession'

const route = useRoute()
const router = useRouter()
const loading = ref(true)
const errorMsg = ref('')
const editError = ref('')
const recalculating = ref(false)
const itineraryData = ref(null)
const selectedDay = ref(0)
const mobileView = ref('diary')
const excluded = ref([])
const required = ref([])
const assignments = ref({})
const ROUTE_COLORS = ['#8B5A2B', '#4A5D43', '#C05727', '#2C3E50', '#8c2425', '#5c4033']
const dayKey = computed(() => `day_${selectedDay.value + 1}`)
const summary = computed(() => itineraryData.value?.day_summaries?.[dayKey.value])
const dayOptions = computed(() => [
  { title: 'Elegir automáticamente', value: 0 },
  ...Array.from({ length: itineraryData.value?.days || 0 }, (_, i) => ({ title: `Día ${i + 1}`, value: i + 1 })),
])
const allPlaces = computed(() => [...Object.values(itineraryData.value?.itinerary || {}).flat(), ...(itineraryData.value?.unscheduled || [])])
const hasChanges = computed(() => {
  const saved = itineraryData.value?.day_assignments || {}
  const changedDay = Object.keys({ ...saved, ...assignments.value }).some(id => saved[id] !== assignments.value[id])
  return excluded.value.length || changedDay || allPlaces.value.some(poi => required.value.includes(poiId(poi)) !== Boolean(poi.must_visit))
})
const attributionLinks = computed(() => {
  const links = new Map()
  allPlaces.value.forEach(poi => (poi.attributions || []).forEach(item => links.set(item.provider, item.providerUri)))
  return [...links].map(([name, url]) => ({ name, url: safeExternalUrl(url) }))
})

function poiId(poi) {
  return poi.place_id || `osm:${poi.site.toLowerCase()}:${poi.coords[0].toFixed(5)},${poi.coords[1].toFixed(5)}`
}
function resetChoices() {
  excluded.value = []
  assignments.value = { ...(itineraryData.value?.day_assignments || {}) }
  required.value = allPlaces.value.filter(poi => poi.must_visit).map(poiId)
}
function assignDay(poi, value) {
  if (value) assignments.value[poiId(poi)] = value
  else delete assignments.value[poiId(poi)]
}
function toggleExcluded(poi) {
  const id = poiId(poi)
  if (excluded.value.includes(id)) excluded.value = excluded.value.filter(value => value !== id)
  else {
    excluded.value.push(id)
    required.value = required.value.filter(value => value !== id)
    delete assignments.value[id]
  }
}
const fetchItinerary = async () => {
  try {
    const pending = takeItinerary(route.params.id)
    itineraryData.value = pending || (await axios.get(`${import.meta.env.VITE_API_URL}/itinerary/${route.params.id}`)).data
    resetChoices()
  } catch (error) {
    errorMsg.value = apiError(error, 'No se pudo cargar el itinerario.')
  } finally {
    loading.value = false
  }
}
const replan = async () => {
  recalculating.value = true
  editError.value = ''
  try {
    const response = await axios.post(`${import.meta.env.VITE_API_URL}/itinerary/${itineraryData.value.id}/replan`, {
      excluded_ids: excluded.value,
      must_visit_ids: required.value,
      day_assignments: assignments.value,
    })
    itineraryData.value = response.data
    resetChoices()
    await router.replace(`/map/${response.data.id}`)
  } catch (error) {
    editError.value = apiError(error, 'No se pudo recalcular el itinerario.')
  } finally {
    recalculating.value = false
  }
}
onMounted(fetchItinerary)
</script>

<template>
  <v-container fluid class="map-page-root pa-0 vintage-bg" style="position: relative;">
    <div class="paper-texture"></div>

    <!-- Skeleton loader / Error handling -->
    <div v-if="loading" class="d-flex flex-grow-1 justify-center align-center w-100 position-relative overflow-hidden" style="z-index: 2; height: 100%;">
      <div class="text-center">
        <v-icon icon="mdi-compass-outline" class="mb-6 spin-slow" size="80" color="var(--color-accent-leather)"></v-icon>
        <h3 class="text-display text-h5 text-ink tracking-widest serif-text cartography-title">DESENROLLANDO PERGAMINOS...</h3>
      </div>
    </div>
    
    <div v-else-if="errorMsg" class="d-flex flex-grow-1 justify-center align-center w-100" style="z-index: 2; height: 100%;">
      <v-card class="pa-8 text-center paper-card border-error" max-width="500">
        <v-icon icon="mdi-alert-octagon-outline" color="#C05727" size="64" class="mb-4"></v-icon>
        <h3 class="text-display text-h5 text-rust mb-2 tracking-widest serif-text">Ruta Extraviada</h3>
        <p class="mb-8 text-ink-light font-italic">{{ errorMsg }}</p>
        <v-btn color="var(--color-accent-leather)" variant="outlined" class="vintage-btn" @click="router.push('/plan')">Reorientar Brújula</v-btn>
      </v-card>
    </div>

    <!-- Main View -->
    <v-row no-gutters class="flex-grow-1 map-page-layout" v-else style="z-index: 2; height: 100%;">
      
      <!-- Diario de Viaje (Sidebar) -->
      <v-col 
        cols="12" md="4" 
        class="flex-column paper-sidebar sidebar-col order-2 order-md-1 position-relative"
        :class="mobileView === 'diary' ? 'd-flex h-100 flex-grow-1' : 'd-none d-md-flex h-100 flex-grow-1'"
      >
        
        <!-- Header -->
        <div class="pa-6 border-b-vintage position-relative">
          <div class="d-flex align-center justify-space-between mb-6">
            <div>
              <div class="text-caption text-moss tracking-widest font-weight-bold mb-1 text-uppercase">DIARIO DE EXPEDICIÓN</div>
              <h2 class="text-display text-h4 font-weight-bold text-ink text-uppercase cartography-title">{{ itineraryData.city.split(',')[0] }}</h2>
              <span class="text-body-2 text-ink-light font-italic">Visitas y horarios orientativos en la hora local del destino</span>
            </div>
            <v-btn icon="mdi-book-arrow-left-outline" variant="text" color="var(--color-accent-leather)" @click="router.push('/')" title="Cerrar Diario"></v-btn>
          </div>
          
          <v-tabs v-model="selectedDay" bg-color="transparent" color="var(--color-accent-rust)" slider-color="var(--color-accent-rust)" grow class="vintage-tabs text-display">
            <v-tab v-for="n in itineraryData.days" :key="n" :value="n - 1" class="font-weight-bold tracking-widest serif-text">
              D.{{ n }}
            </v-tab>
          </v-tabs>
          <div v-if="summary" class="mt-3 text-body-2 text-ink" aria-live="polite">
            <strong v-if="summary.date">{{ summary.date }} · </strong>
            {{ Math.floor(summary.total_minutes / 60) }} h {{ summary.total_minutes % 60 }} min de {{ summary.available_minutes / 60 }} h disponibles
            <div class="text-caption mt-1">
              {{ summary.visit_minutes }} min de visitas · {{ summary.travel_minutes }} min de traslados{{ summary.travel_estimated ? ' (con estimaciones)' : '' }}
            </div>
            <div v-if="summary.total_minutes" class="text-caption">
              Descanso: {{ summary.break_minutes }} min<span v-if="summary.break_start && summary.break_minutes"> desde {{ summary.break_start }}</span> · Margen: {{ summary.buffer_minutes }} min
              <span v-if="summary.waiting_minutes"> · Esperas: {{ summary.waiting_minutes }} min</span>
              <span v-if="summary.finish_time"> · Fin previsto: {{ summary.finish_time }}</span>
            </div>
            <div v-if="itineraryData.origin && summary.total_minutes" class="text-caption">Salida y regreso: {{ itineraryData.origin.site }} · Regreso: {{ summary.return_minutes }} min</div>
          </div>
        </div>

        <!-- Lista de lugares -->
        <v-list class="flex-grow-1 overflow-y-auto pa-4 bg-transparent position-relative">
          <details v-if="itineraryData.warnings?.length" class="mb-4 pa-3 border-dashed text-body-2">
            <summary class="cursor-pointer">Notas del plan ({{ itineraryData.warnings.length }})</summary>
            <ul class="mt-2 pl-5"><li v-for="warning in itineraryData.warnings" :key="warning" class="mb-2">{{ warning }}</li></ul>
          </details>
          <p v-if="itineraryData.places_source === 'google'" class="text-caption mb-3">Datos de lugares: Google Maps. La popularidad y las reseñas no representan un recuento de visitantes.</p>
          <p v-if="attributionLinks.length" class="text-caption mb-3">
            Fuentes: <span v-for="item in attributionLinks" :key="item.name"><a v-if="item.url" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.name }}</a><span v-else>{{ item.name }}</span> </span>
          </p>
          <p class="text-caption mb-4">Las duraciones de visita son estimaciones. Ajusta tus preferencias y pulsa Recalcular para comprobar los cambios.</p>
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
              <div class="mb-6 pb-2 border-b-dashed" :class="{ 'excluded-place': excluded.includes(poiId(poi)) }">
                <div class="text-display font-weight-bold text-h6 text-ink mb-1 cartography-title">{{ poi.site }}</div>
                <div v-if="poi.arrival_time" class="text-body-2 font-weight-bold">{{ poi.arrival_time }}–{{ poi.departure_time }} · {{ poi.visit_minutes || poi.duration_minutes }} min</div>
                <div v-if="poi.travel_minutes" class="text-caption">Traslado previo: {{ poi.travel_minutes }} min{{ poi.travel_estimated ? ' (estimado)' : '' }}</div>
                <div v-if="poi.waiting_minutes" class="text-caption">Espera hasta la apertura: {{ poi.waiting_minutes }} min</div>
                <div v-if="poi.rating" class="text-caption">★ {{ poi.rating }} · {{ poi.review_count?.toLocaleString('es-ES') }} reseñas</div>
                <div class="text-caption text-ink-light font-italic tracking-wide">
                  {{ poi.coords[0].toFixed(4) }}, {{ poi.coords[1].toFixed(4) }}
                </div>
                <a v-if="safeExternalUrl(poi.google_maps_uri)" :href="safeExternalUrl(poi.google_maps_uri)" target="_blank" rel="noopener noreferrer" class="text-caption">Ver en Google Maps</a>
                <v-checkbox v-model="required" :value="poiId(poi)" label="Imprescindible" density="compact" hide-details :disabled="excluded.includes(poiId(poi)) || recalculating" />
                <v-select :model-value="assignments[poiId(poi)] || 0" @update:model-value="assignDay(poi, $event)" :items="dayOptions" label="Fijar a un día" density="compact" variant="outlined" hide-details :disabled="excluded.includes(poiId(poi)) || recalculating" class="my-2" />
                <v-btn size="small" variant="text" :disabled="recalculating" @click="toggleExcluded(poi)">{{ excluded.includes(poiId(poi)) ? 'Conservar visita' : 'Quitar del plan' }}</v-btn>
              </div>
            </v-timeline-item>
          </v-timeline>
          
          <div v-if="!itineraryData.itinerary['day_' + (selectedDay + 1)]?.length" class="text-center pa-8 text-ink-light tracking-widest text-caption border-dashed mt-4 font-italic">
            [ Páginas en blanco en esta jornada ]
          </div>
          <details v-if="itineraryData.unscheduled?.length" class="pa-3 mt-3 border-dashed">
            <summary>Alternativas que no han cabido ({{ itineraryData.unscheduled.length }})</summary>
            <div v-for="poi in itineraryData.unscheduled" :key="poiId(poi)" class="mt-4 pb-3 border-b-dashed text-body-2">
              <strong>{{ poi.site }}</strong> · {{ poi.duration_minutes }} min estimados
              <p class="text-caption">{{ poi.reason }}</p>
              <v-checkbox v-model="required" :value="poiId(poi)" label="Priorizar al recalcular" density="compact" hide-details :disabled="recalculating" />
              <v-select :model-value="assignments[poiId(poi)] || 0" @update:model-value="assignDay(poi, $event)" :items="dayOptions" label="Fijar a un día" density="compact" variant="outlined" hide-details class="mt-2" :disabled="recalculating" />
            </div>
          </details>
          <v-alert v-if="editError" type="error" variant="tonal" class="mt-3">{{ editError }}</v-alert>
        </v-list>
        <div class="pa-4 border-b-vintage">
          <p v-if="hasChanges" class="text-caption mb-2" role="status">Tienes cambios pendientes de recalcular.</p>
          <v-btn block color="var(--color-accent-leather)" :loading="recalculating" @click="replan">Recalcular itinerario</v-btn>
        </div>
      </v-col>

      <v-col 
        cols="12" md="8" 
        class="flex-column position-relative pa-0 map-col order-1 order-md-2"
        :class="mobileView === 'map' ? 'd-flex h-100 flex-grow-1' : 'd-none d-md-flex h-100 flex-grow-1'"
      >
        <TravelMap :data="itineraryData" :day="selectedDay" />
      </v-col>
    </v-row>

    <!-- Botón flotante para móvil -->
    <v-btn
      v-if="!loading && !errorMsg"
      elevation="8"
      icon
      size="x-large"
      class="d-md-none mobile-fab"
      color="var(--color-accent-leather)"
      @click="mobileView = mobileView === 'diary' ? 'map' : 'diary'"
    >
      <v-icon :icon="mobileView === 'diary' ? 'mdi-map-legend' : 'mdi-book-open-page-variant-outline'" color="#F5EEDA"></v-icon>
    </v-btn>
  </v-container>
</template>

<style scoped>
.map-page-root {
  height: 100vh;
  height: 100dvh; /* For mobile safari */
  max-height: 100vh;
  max-height: 100dvh;
  overflow: hidden;
  display: flex !important;
  flex-direction: column;
}

.sidebar-col { min-height: 0; }
.excluded-place { opacity: 0.5; }

.vintage-bg {
  background-color: var(--color-bg-paper) !important;
}

.paper-texture {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background-image: url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAyBAMAAADsEZWCAAAAGFBMVEUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/H9bDAAAACHRSTlMAAAAAAAB/f39+YwD5AAAAgElEQVQ4y2NgQAX8DIwgQkxMDGzMDHwMDEwMLAwMTIwMjEwMjEwMTIwMjEAuxMTMwMDMwAAWZWFgZ2AAcxkYWJgZmBkYGBmYGBgZmBkYmJkYGFjYGRoYmBiaGJgZmRgYmZkY2BgYmJkYGBmZGBiYmRkAAkwMDEyMTBxgwMTEwMDAAABkKBgE2oJ1LAAAAABJRU5ErkJggg==");
  background-repeat: repeat;
  opacity: 0.15;
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
  height: 100% !important;
  min-height: 100%;
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

.mobile-fab {
  position: absolute;
  bottom: 24px;
  right: 24px;
  z-index: 1000;
  border: 2px solid #5A2B0E;
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
