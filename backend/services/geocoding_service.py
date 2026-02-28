import time

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
REQUEST_DELAY = 1.1  # Respetar límite de 1 req/s de Nominatim


def _geocode(site: str, city: str) -> list[float] | None:
    """Busca las coordenadas de un sitio en Nominatim. Devuelve [lat, lon] o None."""
    query = f"{site}, {city}"
    headers = {"User-Agent": "OptiMapper/1.0 (travel-itinerary-app)"}

    try:
        response = httpx.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1},
            headers=headers,
            timeout=10.0,
        )
        response.raise_for_status()
        results = response.json()

        if results:
            return [float(results[0]["lat"]), float(results[0]["lon"])]
    except Exception:
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

        time.sleep(REQUEST_DELAY)  # Rate limit Nominatim

    if not pois:
        raise ValueError(f"Nominatim no encontró coordenadas para ningún sitio en {city}.")

    return pois
