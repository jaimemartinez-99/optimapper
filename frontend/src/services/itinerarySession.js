// One navigation hand-off in memory: avoids fetching Places again immediately
// after generation. Provider content is never written to localStorage.
let pending = null

export function handOffItinerary(itinerary) {
  pending = itinerary
}

export function takeItinerary(id) {
  const result = pending?.id === id ? pending : null
  pending = null
  return result
}

export function apiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(item => item.msg).join(' · ')
  return fallback
}

export function safeExternalUrl(value) {
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) ? url.href : undefined
  } catch {
    return undefined
  }
}
