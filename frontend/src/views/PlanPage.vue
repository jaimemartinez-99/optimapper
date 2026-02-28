<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { City, Country } from 'country-state-city'

const router = useRouter()
const form = ref(false)
const city = ref('')
const days = ref(3)
const loading = ref(false)
const errorMsg = ref('')

const selectedCityRecord = ref(null)
const cityAlternatives = ref([])

let debounceTimeout = null
watch(city, (newCity) => {
  clearTimeout(debounceTimeout)
  debounceTimeout = setTimeout(() => {
    if (!newCity || newCity.trim().length < 2) {
      selectedCityRecord.value = null
      cityAlternatives.value = []
      return
    }

    const searchStr = newCity.trim().toLowerCase()
    
    // Encuentra coincidencias exactas con el nombre de la ciudad
    const matches = City.getAllCities().filter(
      c => c.name.toLowerCase() === searchStr
    )
    
    if (matches.length > 0) {
      const enrichedMatches = matches.map(c => ({
        ...c,
        countryData: Country.getCountryByCode(c.countryCode)
      })).filter(c => c.countryData)
      
      const uniqueCountries = []
      const seenCodes = new Set()
      
      for (const m of enrichedMatches) {
        if (!seenCodes.has(m.countryCode)) {
          seenCodes.add(m.countryCode)
          uniqueCountries.push(m)
        }
      }
      
      if (uniqueCountries.length > 0) {
        selectedCityRecord.value = uniqueCountries[0]
        cityAlternatives.value = uniqueCountries
      } else {
        selectedCityRecord.value = null
        cityAlternatives.value = []
      }
    } else {
      selectedCityRecord.value = null
      cityAlternatives.value = []
    }
  }, 300)
})

const rules = {
  required: value => !!value || 'El destino es obligatorio.',
}

const submit = async () => {
  if (!form.value) return

  loading.value = true
  errorMsg.value = ''

  try {
    const payloadCity = selectedCityRecord.value 
      ? `${city.value}, ${selectedCityRecord.value.countryData.name}`
      : city.value

    const response = await axios.post('http://localhost:8000/itinerary', {
      city: payloadCity,
      days: days.value
    })

    // Redirigir al mapa con el UUID generado
    if (response.data && response.data.id) {
      router.push(`/map/${response.data.id}`)
    } else {
      throw new Error('El destino no pudo ser cartografiado.')
    }
  } catch (err) {
    console.error(err)
    errorMsg.value = err.response?.data?.detail || err.message || 'La ruta naval está bloqueada en este momento.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <v-container fluid class="fill-height pa-0 m-0 vintage-bg position-relative overflow-hidden">
    <!-- Paper Texture -->
    <div class="paper-texture"></div>

    <v-row no-gutters class="fill-height w-100 justify-center align-center position-relative" style="z-index: 2;">
      <v-col cols="12" sm="10" md="8" lg="6" xl="5" class="pa-4 pa-sm-8">
        
        <v-card width="100%" elevation="0" class="brass-card pa-6 pa-sm-8 vintage-shadow fade-in-up">
          <div class="text-center mb-6">
            <v-icon icon="mdi-map-marker-path" size="50" color="var(--color-accent-leather)" class="mb-2"></v-icon>
            <h2 class="text-display text-h5 text-sm-h4 font-weight-bold cartography-title">
              INSTRUMENTOS DE NAVEGACIÓN
            </h2>
            <div class="divider-ornate mx-auto mt-4 mb-2"></div>
            <div class="text-caption font-italic text-ink-light">Ajuste las coordenadas para planificar su expedición</div>
          </div>

          <v-form v-model="form" @submit.prevent="submit" class="mt-8">
            
            <div class="input-container mb-6">
              <div class="text-subtitle-2 font-weight-bold text-leather mb-1 text-uppercase tracking-wide">DESTINO (CIUDAD/PUERTO)</div>
              <v-text-field
                v-model="city"
                :rules="[rules.required]"
                placeholder="Escriba aquí..."
                prepend-inner-icon="mdi-compass-rose"
                variant="outlined"
                class="vintage-input"
                color="var(--color-accent-leather)"
                bg-color="rgba(255, 255, 255, 0.4)"
                hide-details="auto"
              ></v-text-field>
            </div>

            <v-expand-transition>
              <div v-if="selectedCityRecord" class="mb-6 d-flex align-center country-stamp pa-3">
                <div class="text-h3 mr-4 stamp-flag">{{ selectedCityRecord.countryData.flag }}</div>
                <div>
                  <div class="text-caption text-moss font-weight-bold tracking-widest text-uppercase">SELLO LOCALIZADO</div>
                  <div class="text-h6 font-weight-bold text-ink serif-text">{{ selectedCityRecord.countryData.name }}</div>
                </div>
                <v-spacer></v-spacer>
                <v-menu v-if="cityAlternatives.length > 1" location="bottom end">
                  <template v-slot:activator="{ props }">
                    <v-btn
                      v-bind="props"
                      variant="text"
                      color="var(--color-accent-leather)"
                      size="small"
                      prepend-icon="mdi-swap-horizontal"
                      class="text-none font-weight-bold stamp-btn"
                    >
                      CORREGIR
                    </v-btn>
                  </template>
                  <v-list class="paper-dropdown pa-2 vintage-shadow">
                    <v-list-item
                      v-for="alt in cityAlternatives"
                      :key="alt.countryCode"
                      @click="selectedCityRecord = alt"
                      :active="selectedCityRecord.countryCode === alt.countryCode"
                      color="var(--color-accent-leather)"
                      class="mb-1 dropdown-item"
                    >
                      <template v-slot:prepend>
                        <span class="text-h5 mr-3">{{ alt.countryData.flag }}</span>
                      </template>
                      <v-list-item-title class="font-weight-bold serif-text">{{ alt.countryData.name }}</v-list-item-title>
                    </v-list-item>
                  </v-list>
                </v-menu>
              </div>
            </v-expand-transition>

            <div class="mb-8 mt-6">
              <div class="d-flex justify-space-between mb-2">
                <span class="text-subtitle-2 font-weight-bold text-leather text-uppercase tracking-wide">DURACIÓN (DÍAS DE VIAJE)</span>
                <span class="font-weight-bold text-ink text-h6 serif-text">{{ days }}</span>
              </div>
              <v-slider
                v-model="days"
                min="1"
                max="14"
                step="1"
                color="var(--color-accent-leather)"
                track-color="rgba(139, 90, 43, 0.2)"
                thumb-color="var(--color-accent-rust)"
                class="px-2 vintage-slider"
                hide-details
              ></v-slider>
            </div>

            <v-alert
              v-if="errorMsg"
              type="error"
              variant="flat"
              class="mb-6 alert-worn bg-red-lighten-4 text-red-darken-4 custom-alert"
              closable
              @click:close="errorMsg = ''"
            >
              {{ errorMsg }}
            </v-alert>

            <button type="submit" class="leather-btn w-100" :disabled="!form || loading">
              <span class="leather-btn-content d-flex align-center justify-center w-100 py-3">
                <v-progress-circular v-if="loading" indeterminate size="24" color="#F5EEDA" class="mr-3"></v-progress-circular>
                <v-icon v-else icon="mdi-ferry" class="mr-3" size="small"></v-icon>
                {{ loading ? 'TRAZANDO RUTA...' : 'TRAZAR RUTA' }}
              </span>
            </button>
          </v-form>
      
          <div class="text-center mt-6">
            <v-btn variant="text" color="var(--color-text-ink)" class="vintage-link serif-text" @click="router.push('/')">
              <v-icon start icon="mdi-chevron-left"></v-icon> Volver al Diario
            </v-btn>
          </div>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
.vintage-bg {
  background-color: var(--color-bg-paper);
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

/* Card imitating a notebook or brass instrument panel */
.brass-card {
  background-color: rgba(255, 252, 245, 0.9);
  border: 1px solid rgba(139, 90, 43, 0.4);
  border-radius: 2% 3% 2% 4% / 3% 2% 4% 2%;
  position: relative;
  box-shadow: 
    inset 0 0 40px rgba(139, 90, 43, 0.05),
    0 15px 35px rgba(44, 62, 80, 0.15);
}

.brass-card::before {
  content: '';
  position: absolute;
  top: 10px; bottom: 10px; left: 10px; right: 10px;
  border: 1px dashed rgba(139, 90, 43, 0.3);
  pointer-events: none;
  border-radius: 1%;
}

.cartography-title {
  color: var(--color-text-ink);
  letter-spacing: 0.05em;
  text-shadow: 1px 1px 0px rgba(255,255,255,0.8);
}

.text-ink { color: var(--color-text-ink); }
.text-ink-light { color: #5a6b7c; }
.text-leather { color: var(--color-accent-leather); }
.text-moss { color: var(--color-accent-moss); }
.serif-text { font-family: var(--font-display); }
.tracking-wide { letter-spacing: 0.05em; }
.tracking-widest { letter-spacing: 0.15em; }

.divider-ornate {
  width: 80px;
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

/* Inputs imitating old paper fields */
.vintage-input :deep(.v-field) {
  border-radius: 2px;
  border: 1px solid rgba(139, 90, 43, 0.3);
  font-family: var(--font-body) !important;
  color: var(--color-text-ink);
  background-color: transparent !important;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
}
.vintage-input :deep(.v-field--focused) {
  border-color: var(--color-accent-leather);
  background-color: #fff !important;
}

/* Sliders */
.vintage-slider :deep(.v-slider-thumb) {
  border: 2px solid #FFF;
  box-shadow: 0 2px 5px rgba(0,0,0,0.2);
}

/* Country Selector (Passport Stamp style) */
.country-stamp {
  background-color: #FFF;
  border: 2px solid rgba(74, 93, 67, 0.2);
  border-radius: 4px;
  position: relative;
  overflow: hidden;
}

.country-stamp::before {
  content: '';
  position: absolute;
  top: -10px; right: -10px;
  width: 50px; height: 50px;
  border: 2px dashed rgba(139, 90, 43, 0.1);
  border-radius: 50%;
  transform: rotate(15deg);
}

/* Analog Leather Button */
.leather-btn {
  background: transparent;
  padding: 4px;
  cursor: pointer;
  position: relative;
  transition: all 0.2s ease;
}

.leather-btn-content {
  background: linear-gradient(135deg, var(--color-accent-rust) 0%, #8E3A1A 100%);
  color: #F5EEDA;
  border-radius: 3% 2% 4% 3% / 2% 4% 3% 2%;
  border: 2px solid #5A2B0E;
  font-family: var(--font-body);
  font-weight: 700;
  letter-spacing: 0.1em;
  box-shadow: 
    inset 0 2px 0 rgba(255,255,255,0.2),
    inset 0 -2px 0 rgba(0,0,0,0.3),
    0 4px 6px rgba(0,0,0,0.2);
  transition: all 0.2s ease;
  text-shadow: 1px 1px 2px rgba(0,0,0,0.4);
}

.leather-btn:hover:not(:disabled) .leather-btn-content {
  transform: translateY(-2px);
  box-shadow: 
    inset 0 2px 0 rgba(255,255,255,0.3),
    inset 0 -2px 0 rgba(0,0,0,0.3),
    0 6px 10px rgba(0,0,0,0.25);
  background: linear-gradient(135deg, #D46932 0%, #9A401C 100%);
}

.leather-btn:active:not(:disabled) .leather-btn-content {
  transform: translateY(2px);
  box-shadow: 
    inset 0 2px 5px rgba(0,0,0,0.4),
    0 1px 0px rgba(0,0,0,0.1);
}

.leather-btn:disabled {
  opacity: 0.6;
  filter: grayscale(0.5);
  cursor: not-allowed;
}

/* Dropdowns & Alerts */
.paper-dropdown {
  background-color: #F5EEDA !important;
  border: 1px solid rgba(139, 90, 43, 0.3);
  border-radius: 2px;
}
.dropdown-item:hover {
  background-color: rgba(139, 90, 43, 0.1);
}

.alert-worn {
  border: 1px solid #D32F2F;
  border-radius: 2px;
}

/* Links */
.vintage-link {
  transition: opacity 0.3s ease;
  opacity: 0.7;
}
.vintage-link:hover {
  opacity: 1;
}

.fade-in-up {
  animation: fadeInUp 0.6s cubic-bezier(0.165, 0.84, 0.44, 1) forwards;
  opacity: 0;
  transform: translateY(20px);
}

@keyframes fadeInUp {
  to { opacity: 1; transform: translateY(0); }
}
</style>
