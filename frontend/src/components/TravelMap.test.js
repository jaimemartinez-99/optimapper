import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import TravelMap from './TravelMap.vue'
import L from 'leaflet'

vi.mock('leaflet', () => ({ default: { map: vi.fn() } }))
let wrapper
afterEach(() => { wrapper?.unmount(); vi.unstubAllGlobals(); vi.unstubAllEnvs() })

it('keeps Google places off OpenStreetMap when the browser key is missing', async () => {
  vi.stubEnv('VITE_GOOGLE_MAPS_API_KEY', '')
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} })
  wrapper = mount(TravelMap, { props: { data: { places_source: 'google', itinerary: { day_1: [] } } } })
  await flushPromises()
  expect(wrapper.text()).toContain('configurar la clave pública de Google Maps')
  expect(L.map).not.toHaveBeenCalled()
})
