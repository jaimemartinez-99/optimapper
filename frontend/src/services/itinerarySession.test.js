import { describe, expect, it } from 'vitest'
import { apiError, handOffItinerary, safeExternalUrl, takeItinerary } from './itinerarySession'

describe('itinerary navigation and errors', () => {
  it('hands the generated plan to the map only once without persistent storage', () => {
    const itinerary = { id: 'trip', city: 'Madrid' }
    handOffItinerary(itinerary)
    expect(takeItinerary('trip')).toBe(itinerary)
    expect(takeItinerary('trip')).toBeNull()
    expect(localStorage.length).toBe(0)
  })
  it('never returns a plan for another identifier', () => {
    handOffItinerary({ id: 'first' })
    expect(takeItinerary('other')).toBeNull()
  })
  it('formats FastAPI validation arrays and provider errors as readable text', () => {
    expect(apiError({ response: { data: { detail: [{ msg: 'Invalid date' }, { msg: 'Too many places' }] } } })).toBe('Invalid date · Too many places')
    expect(apiError({ response: { data: { detail: 'Places unavailable' } } })).toBe('Places unavailable')
    expect(apiError({}, 'Retry')).toBe('Retry')
  })
  it('only permits web links in provider-supplied URLs', () => {
    expect(safeExternalUrl('javascript:alert(1)')).toBeUndefined()
    expect(safeExternalUrl('data:text/html,test')).toBeUndefined()
    expect(safeExternalUrl(undefined)).toBeUndefined()
    expect(safeExternalUrl('https://maps.google.com/')).toBe('https://maps.google.com/')
  })
})
