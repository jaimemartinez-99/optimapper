import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from '../views/LandingPage.vue'
import PlanPage from '../views/PlanPage.vue'
import MapPage from '../views/MapPage.vue'

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes: [
        {
            path: '/',
            name: 'home',
            component: LandingPage,
        },
        {
            path: '/plan',
            name: 'plan',
            component: PlanPage,
        },
        {
            path: '/map/:id',
            name: 'map',
            component: MapPage,
        },
    ],
})

export default router
