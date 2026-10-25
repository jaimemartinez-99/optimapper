<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'

const props = defineProps({ data: { type: Object, required: true }, day: { type: Number, default: 0 } })
const container = ref(null)
const mapError = ref('')
const colors = ['#8B5A2B', '#4A5D43', '#C05727', '#2C3E50', '#8c2425', '#5c4033']
let map, layers = [], observer, disposed = false, googleApi, advancedMarker, initVersion = 0, previousAuthFailure

async function loadGoogle() {
  if (window.google?.maps?.importLibrary) return window.google
  const key = import.meta.env.VITE_GOOGLE_MAPS_API_KEY
  if (!key) throw new Error('El mapa requiere configurar la clave pública de Google Maps. Puedes consultar las visitas en el diario.')
  await new Promise((resolve, reject) => {
    const script = document.createElement('script')
    const timer = setTimeout(() => { cleanup(); reject(new Error('Google Maps ha tardado demasiado en responder.')) }, 20000)
    function cleanup() { clearTimeout(timer); delete window.__optimapperMapsReady; script.remove() }
    window.__optimapperMapsReady = () => { cleanup(); resolve() }
    script.onerror = () => { cleanup(); reject(new Error('No se pudo cargar Google Maps. Comprueba la conexión y la clave del mapa.')) }
    const params = new URLSearchParams({ key, v: 'weekly', loading: 'async', callback: '__optimapperMapsReady', language: 'es' })
    script.src = `https://maps.googleapis.com/maps/api/js?${params}`
    script.async = true
    document.head.appendChild(script)
  })
  return window.google
}

function clearLayers() {
  layers.forEach(layer => props.data.places_source === 'google' ? (layer.map = null, layer.setMap?.(null)) : layer.remove())
  layers = []
}

function draw() {
  if (!map || disposed) return
  clearLayers()
  const stops = props.data.itinerary[`day_${props.day + 1}`] || []
  const origin = props.data.origin
  const points = [...(origin ? [origin] : []), ...stops]
  if (!points.length) return
  const color = colors[props.day % colors.length]
  if (googleApi) {
    const bounds = new googleApi.maps.LatLngBounds()
    points.forEach((poi, index) => {
      const position = { lat: poi.coords[0], lng: poi.coords[1] }
      bounds.extend(position)
      const content = document.createElement('span')
      content.textContent = origin && index === 0 ? '⌂' : String(index + (origin ? 0 : 1))
      Object.assign(content.style, { background: color, color: '#fff', border: '2px solid white', borderRadius: '50%', padding: '5px 9px', fontWeight: 'bold' })
      layers.push(new advancedMarker({ map, position, content, title: poi.site }))
    })
    if (stops.length > 0) {
      const path = points.map(p => ({ lat: p.coords[0], lng: p.coords[1] }))
      if (origin) path.push(path[0])
      const line = new googleApi.maps.Polyline({ map, path, strokeColor: color, strokeOpacity: 0.65, strokeWeight: 3 })
      layers.push(line)
    }
    map.fitBounds(bounds, 50)
    if (points.length === 1) map.setZoom(15)
  } else {
    points.forEach((poi, index) => {
      const popup = document.createElement('strong')
      popup.textContent = `${origin && index === 0 ? 'Alojamiento' : index + (origin ? 0 : 1)}. ${poi.site}`
      const marker = L.marker(poi.coords, { title: poi.site }).addTo(map).bindPopup(popup)
      layers.push(marker)
    })
    if (stops.length) {
      const path = points.map(p => p.coords)
      if (origin) path.push(origin.coords)
      layers.push(L.polyline(path, { color, weight: 3, dashArray: '8, 8' }).addTo(map))
    }
    map.invalidateSize()
    map.fitBounds(L.latLngBounds(points.map(p => p.coords)), { padding: [35, 35], maxZoom: 16 })
  }
}

async function init() {
  const version = ++initVersion
  try {
    if (props.data.places_source === 'google') {
      previousAuthFailure = window.gm_authFailure
      window.gm_authFailure = () => { mapError.value = 'Google Maps no ha autorizado la clave del mapa. Comprueba las restricciones y Maps JavaScript API.' }
      const api = await loadGoogle()
      const [{ Map }, { AdvancedMarkerElement }] = await Promise.all([api.maps.importLibrary('maps'), api.maps.importLibrary('marker')])
      if (disposed || version !== initVersion) return
      googleApi = api
      advancedMarker = AdvancedMarkerElement
      map = new Map(container.value, { center: { lat: 0, lng: 0 }, zoom: 2, mapId: import.meta.env.VITE_GOOGLE_MAP_ID || 'DEMO_MAP_ID', streetViewControl: false })
    } else {
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: new URL('leaflet/dist/images/marker-icon-2x.png', import.meta.url).href,
        iconUrl: new URL('leaflet/dist/images/marker-icon.png', import.meta.url).href,
        shadowUrl: new URL('leaflet/dist/images/marker-shadow.png', import.meta.url).href,
      })
      map = L.map(container.value).setView([0, 0], 2)
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', maxZoom: 19,
      }).addTo(map)
    }
    draw()
  } catch (error) {
    if (!disposed) mapError.value = error.message
  }
}

onMounted(() => {
  init()
  observer = new ResizeObserver(() => { if (container.value?.clientWidth && container.value?.clientHeight) draw() })
  observer.observe(container.value)
})
watch(() => [props.day, props.data], async () => { await nextTick(); draw() })
onBeforeUnmount(() => {
  disposed = true
  if (props.data.places_source === 'google') window.gm_authFailure = previousAuthFailure
  observer?.disconnect()
  clearLayers()
  if (googleApi && map) googleApi.maps.event.clearInstanceListeners(map)
  else map?.remove()
})
</script>

<template>
  <div class="travel-map">
    <div ref="container" class="map-surface"></div>
    <div v-if="mapError" class="map-message pa-6" role="status">{{ mapError }}</div>
    <div v-else class="map-caption">Conexiones orientativas entre visitas; consulta la navegación para seguir las calles.</div>
  </div>
</template>

<style scoped>
.travel-map { position: relative; width: 100%; height: 100%; min-height: 260px; }
.map-surface { width: 100%; height: 100%; min-height: 260px; }
.map-message { position: absolute; inset: 0; display: grid; place-content: center; background: #f5eeda; color: #2c3e50; }
.map-caption { position: absolute; top: 12px; left: 12px; right: 60px; z-index: 500; max-width: 440px; background: #fffdf3eb; color: #2c3e50; padding: 7px 10px; font-size: 12px; border-radius: 4px; pointer-events: none; }
</style>
