import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { defineComponent, h, onMounted } from 'vue'
import PlanPage from './PlanPage.vue'
import MapPage from './MapPage.vue'
import axios from 'axios'
import { handOffItinerary, takeItinerary } from '../services/itinerarySession'

const { router } = vi.hoisted(() => ({ router: { push: vi.fn(), replace: vi.fn() } }))
vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))
vi.mock('vue-router', () => ({ useRouter: () => router, useRoute: () => ({ params: { id: 'original' } }) }))
vi.mock('country-state-city', () => ({ City: { getAllCities: () => [] }, Country: {} }))

const field = defineComponent({
  name: 'VTextField', props: ['modelValue', 'label', 'type', 'placeholder'], emits: ['update:modelValue'],
  setup(props, { emit }) {
    return () => h('input', { 'aria-label': props.label || props.placeholder, value: props.modelValue, type: props.type || 'text', onInput: event => emit('update:modelValue', event.target.value) })
  },
})
const form = defineComponent({
  name: 'VForm', emits: ['update:modelValue', 'submit'],
  setup(_, { emit, slots }) {
    onMounted(() => emit('update:modelValue', true))
    return () => h('form', { onSubmit: event => { event.preventDefault(); emit('submit', event) } }, slots.default?.())
  },
})
const globalOptions = {
  renderStubDefaultSlot: true,
  stubs: {
    ...Object.fromEntries(['VContainer', 'VRow', 'VCol', 'VCard', 'VIcon', 'VBtn', 'VTab', 'VTabs', 'VCheckbox', 'VSelect', 'VTimelineItem', 'VTimeline', 'VAlert', 'VList', 'VProgressCircular', 'VExpandTransition', 'VSpacer', 'VMenu', 'VListItem', 'VListItemTitle', 'VSlider'].map(name => [name, true])),
    VTextField: field, VTextarea: field, VForm: form, TravelMap: true,
  },
}
let wrapper
beforeEach(() => { vi.clearAllMocks(); takeItinerary('clear') })
afterEach(() => { wrapper?.unmount(); wrapper = undefined })

function trip(id = 'original') {
  return { id, city: 'Madrid, Spain', days: 2, places_source: 'nominatim', warnings: ['Horario pendiente de confirmar'],
    itinerary: { day_1: [{ place_id: 'museum', site: 'Museum', coords: [40.4, -3.7], duration_minutes: 90, visit_minutes: 90, arrival_time: '09:00', departure_time: '10:30', must_visit: false }], day_2: [] },
    unscheduled: [{ place_id: 'park', site: 'Park', coords: [40.41, -3.7], duration_minutes: 90, must_visit: false, reason: 'No cabe' }],
    day_summaries: { day_1: { total_minutes: 165, available_minutes: 480, visit_minutes: 90, travel_minutes: 0, break_minutes: 45, buffer_minutes: 30, finish_time: '11:45' } },
  }
}

describe('planning form', () => {
  it('sends dates, preferences and must-visits and hands the result to the map', async () => {
    axios.post.mockResolvedValue({ data: trip('generated') })
    wrapper = shallowMount(PlanPage, { global: globalOptions })
    await flushPromises()
    await wrapper.find('input[aria-label="Escriba aquí..."]').setValue('Madrid')
    await wrapper.find('input[type="date"]').setValue('2026-11-01')
    const mustVisit = wrapper.findAllComponents(field).find(component => component.props('label')?.startsWith('Tus imprescindibles'))
    mustVisit.vm.$emit('update:modelValue', 'Museo del Prado\nRetiro')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(axios.post).toHaveBeenCalledWith(expect.stringContaining('/itinerary'), expect.objectContaining({ city: 'Madrid', start_date: '2026-11-01', must_visit: ['Museo del Prado', 'Retiro'], pace: 'balanced', daily_hours: 8, travel_mode: 'WALK' }))
    expect(router.push).toHaveBeenCalledWith('/map/generated')
    expect(takeItinerary('generated').id).toBe('generated')
  })
  it('renders structured validation failures without losing the form', async () => {
    axios.post.mockRejectedValue({ response: { data: { detail: [{ msg: 'La jornada debe terminar antes de medianoche.' }] } } })
    wrapper = shallowMount(PlanPage, { global: globalOptions })
    await flushPromises()
    await wrapper.find('input[aria-label="Escriba aquí..."]').setValue('Madrid')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('La jornada debe terminar antes de medianoche.')
    expect(router.push).not.toHaveBeenCalled()
  })
})

describe('day-by-day diary', () => {
  it('retains saved day assignments and does not mark them as pending edits', async () => {
    const saved = { ...trip(), day_assignments: { museum: 2 } }
    handOffItinerary(saved)
    axios.post.mockResolvedValue({ data: { ...saved, id: 'updated' } })
    wrapper = shallowMount(MapPage, { global: globalOptions })
    await flushPromises()
    expect(wrapper.text()).not.toContain('cambios pendientes')
    await wrapper.findAllComponents({ name: 'VBtn' }).find(button => button.text() === 'Recalcular itinerario').trigger('click')
    await flushPromises()
    expect(axios.post).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ day_assignments: { museum: 2 } }))
  })
  it('uses the generated hand-off and shows schedule, totals and alternatives', async () => {
    handOffItinerary(trip())
    wrapper = shallowMount(MapPage, { global: globalOptions })
    await flushPromises()
    expect(axios.get).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('09:00–10:30')
    expect(wrapper.text()).toContain('2 h 45 min de 8 h disponibles')
    expect(wrapper.text()).toContain('Alternativas que no han cabido (1)')
    expect(wrapper.text()).toContain('Horario pendiente de confirmar')
  })
  it('excludes a visit, recalculates and updates the URL to a new saved plan', async () => {
    handOffItinerary(trip())
    axios.post.mockResolvedValue({ data: trip('updated') })
    wrapper = shallowMount(MapPage, { global: globalOptions })
    await flushPromises()
    const remove = wrapper.findAllComponents({ name: 'VBtn' }).find(button => button.text() === 'Quitar del plan')
    await remove.trigger('click')
    expect(wrapper.text()).toContain('cambios pendientes')
    const recalculate = wrapper.findAllComponents({ name: 'VBtn' }).find(button => button.text() === 'Recalcular itinerario')
    await recalculate.trigger('click')
    await flushPromises()
    expect(axios.post).toHaveBeenCalledWith(expect.stringContaining('/itinerary/original/replan'), { excluded_ids: ['museum'], must_visit_ids: [], day_assignments: {} })
    expect(router.replace).toHaveBeenCalledWith('/map/updated')
    expect(wrapper.text()).not.toContain('cambios pendientes')
  })
  it('keeps the current itinerary visible when recalculation fails', async () => {
    handOffItinerary(trip())
    axios.post.mockRejectedValue({ response: { data: { detail: 'Google no está disponible' } } })
    wrapper = shallowMount(MapPage, { global: globalOptions })
    await flushPromises()
    const recalculate = wrapper.findAllComponents({ name: 'VBtn' }).find(button => button.text() === 'Recalcular itinerario')
    await recalculate.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Google no está disponible')
    expect(wrapper.text()).toContain('Museum')
    expect(router.replace).not.toHaveBeenCalled()
  })
})
