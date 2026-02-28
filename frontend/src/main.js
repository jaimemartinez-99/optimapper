import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import vuetify from './plugins/vuetify'
import 'leaflet/dist/leaflet.css' // Import Leaflet CSS globally

const app = createApp(App)

app.use(router)
app.use(vuetify)

app.mount('#app')
