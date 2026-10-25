import time
import threading

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
REQUEST_DELAY = 1.1  # Respetar límite de 1 req/s de Nominatim
_request_lock = threading.Lock()
_last_request = 0.0


def _geocode(site: str, city: str) -> list[float] | None:
    """Busca las coordenadas de un sitio en Nominatim. Devuelve [lat, lon] o None."""
    global _last_request
    query = f"{site}, {city}" if city else site
    headers = {"User-Agent": "OptiMapper/1.0 (travel-itinerary-app)"}

    try:
        with _request_lock:
            time.sleep(max(0, REQUEST_DELAY - (time.monotonic() - _last_request)))
            try:
                response = httpx.get(
                    NOMINATIM_URL,
                    params={"q": query, "format": "json", "limit": 1},
                    headers=headers,
                    timeout=10.0,
                )
            finally:
                _last_request = time.monotonic()
        response.raise_for_status()
        results = response.json()

        if results:
            return [float(results[0]["lat"]), float(results[0]["lon"])]
    except (httpx.HTTPError, ValueError, KeyError):
        pass

    return None


def geocode_pois(site_names: list[str], city: str) -> list[dict]:
    """
    Geocodifica una lista de nombres de sitios usando Nominatim.
    Devuelve solo los POIs para los que Nominatim encontró coordenadas.
    Respeta el límite de 1 req/s de Nominatim.
    """
    pois = []

    for name in site_names:
        coords = _geocode(name, city)

        if coords:
            pois.append({"site": name, "coords": coords})

    if not pois:
        raise ValueError(f"Nominatim no encontró coordenadas para ningún sitio en {city}.")

    return pois


def discover_fallback(request, suggestions):
    from services.places_service import normalized
    from services.travel_service import haversine

    center = _geocode(request.city, "")
    if center is None:
        raise ValueError("No se pudo localizar la ciudad en Nominatim.")
    items = {normalized(item["site"]): dict(item) for item in suggestions}
    for name in request.must_visit:
        key = normalized(name)
        items.setdefault(key, {"site": name, "category": "landmark", "duration_minutes": 60, "priority": 100})
        items[key]["must_visit"] = True
    pois, warnings, seen_coords = [], [], set()
    for item in items.values():
        coords = _geocode(item["site"], request.city)
        if coords is None or haversine(center, coords) > 50:
            warnings.append(f"No se pudo verificar «{item['site']}» dentro del destino.")
            continue
        key = tuple(round(value, 5) for value in coords)
        if key in seen_coords:
            # Identical geocoding results usually indicate aliases of the same place.
            existing = next(p for p in pois if tuple(round(value, 5) for value in p["coords"]) == key)
            existing["must_visit"] = existing.get("must_visit", False) or item.get("must_visit", False)
            continue
        seen_coords.add(key)
        pois.append({**item, "coords": coords, "source": "nominatim", "place_id": f"osm:{key[0]},{key[1]}"})
    if not pois:
        raise ValueError("No se pudieron verificar lugares en Nominatim para este destino.")
    origin = None
    if request.accommodation and request.accommodation.strip():
        coords = _geocode(request.accommodation, request.city)
        if coords is None or haversine(center, coords) > 50:
            raise ValueError("No se pudo localizar el alojamiento dentro del destino.")
        origin = {"site": request.accommodation, "coords": coords, "source": "nominatim", "place_id": "origin"}
    warnings.append("Se usa Claude + Nominatim: no hay horarios verificados ni tiempos reales de desplazamiento.")
    return pois, origin, warnings
