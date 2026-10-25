"""Google Places discovery and live hydration. Never send provider data to Claude."""
import math
import os
import unicodedata

import httpx

from services.travel_service import haversine

PLACE_FIELDS = "id,displayName,location,types,businessStatus,rating,userRatingCount,regularOpeningHours,currentOpeningHours,googleMapsUri,attributions"
DURATIONS = {"museum": 120, "gallery": 90, "park": 75, "neighborhood": 90, "monument": 45, "landmark": 45}


class PlacesError(RuntimeError):
    pass


class PlacesQuotaError(PlacesError):
    pass


def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c) and c.isalnum())


def category_for(types):
    for place_type, category in [("museum", "museum"), ("art_gallery", "gallery"), ("park", "park"), ("national_park", "park"), ("historical_landmark", "monument"), ("monument", "monument"), ("neighborhood", "neighborhood")]:
        if place_type in types:
            return category
    return "landmark"


def parse_place(raw):
    location = raw.get("location", {})
    if not raw.get("id") or "latitude" not in location or "longitude" not in location:
        return None
    if raw.get("businessStatus") in {"CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"}:
        return None
    category = category_for(raw.get("types", []))
    rating = raw.get("rating", 0)
    count = raw.get("userRatingCount", 0)
    return {
        "place_id": raw["id"], "site": raw.get("displayName", {}).get("text", "Lugar"),
        "coords": [location["latitude"], location["longitude"]],
        "category": category, "duration_minutes": DURATIONS[category], "duration_estimated": True,
        "priority": round(min(95, 25 + 8 * math.log10(1 + count) + rating * 5), 2),
        "rating": raw.get("rating"), "review_count": raw.get("userRatingCount"),
        "google_maps_uri": raw.get("googleMapsUri"), "attributions": raw.get("attributions", []),
        "opening_hours": raw.get("regularOpeningHours"),
        "current_opening_hours": raw.get("currentOpeningHours"), "source": "google",
    }


class PlacesClient:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

    def _request(self, path, fields, payload=None):
        try:
            response = httpx.request(
                "GET" if payload is None else "POST",
                f"https://places.googleapis.com/v1/{path}",
                headers={"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": fields},
                json=payload, timeout=20.0,
            )
            if response.status_code == 429:
                raise PlacesQuotaError("Se ha alcanzado el límite de consultas de Google Places. Prueba más tarde; el límite diario se restablece al día siguiente.")
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Do not expose provider responses or URLs with credentials to API clients.
            raise PlacesError("Google Places no está disponible. Revisa la clave, la facturación y Places API (New).") from exc

    def search(self, query, center=None, radius=20000, full=True):
        payload = {"textQuery": query, "languageCode": "es", "pageSize": 1}
        if center:
            payload["locationBias"] = {"circle": {"center": {"latitude": center[0], "longitude": center[1]}, "radius": radius}}
        fields = PLACE_FIELDS if full else "id,displayName,location,viewport"
        return self._request("places:searchText", ",".join(f"places.{field}" for field in fields.split(",")), payload).get("places", [])

    def details(self, place_id):
        from urllib.parse import quote
        return parse_place(self._request(f"places/{quote(place_id, safe='')}", PLACE_FIELDS))

    def discover(self, request, suggestions):
        cities = self.search(request.city, full=False)
        if not cities:
            raise ValueError("Google Places no encontró el destino. Especifica ciudad y país.")
        city = cities[0]
        center = [city["location"]["latitude"], city["location"]["longitude"]]
        viewport = city.get("viewport", {})
        high = viewport.get("high", city["location"])
        radius = min(50000, max(5000, haversine(center, [high["latitude"], high["longitude"]]) * 1000))
        candidates, warnings = {}, []
        types = ["tourist_attraction", "museum", "park"]
        if "art" in request.interests:
            types.append("art_gallery")
        if "history" in request.interests:
            types.append("historical_landmark")

        def add(raw, editorial=None, required=False):
            item = parse_place(raw)
            if not item or haversine(center, item["coords"]) > radius / 1000:
                return False
            previous = candidates.get(item["place_id"])
            if previous:
                previous["must_visit"] = previous.get("must_visit", False) or required
                if editorial:
                    previous.update({key: editorial[key] for key in ("duration_minutes", "category")})
                    previous["priority"] = max(previous["priority"], editorial["priority"])
                return True
            if editorial:
                item.update({key: editorial[key] for key in ("duration_minutes", "category")})
                item["priority"] = max(item["priority"], editorial["priority"])
            item["must_visit"] = required
            candidates[item["place_id"]] = item
            return True

        for place_type in types:
            payload = {
                "includedTypes": [place_type], "rankPreference": "POPULARITY", "maxResultCount": 20,
                "languageCode": "es", "locationRestriction": {"circle": {
                    "center": {"latitude": center[0], "longitude": center[1]}, "radius": radius,
                }},
            }
            try:
                values = self._request("places:searchNearby", ",".join(f"places.{field}" for field in PLACE_FIELDS.split(",")), payload)
                for raw in values.get("places", []):
                    add(raw)
            except PlacesError:
                warnings.append(f"No se pudo completar la búsqueda de la categoría {place_type}.")

        # Bound extra Text Search calls; Google independently discovers the larger pool.
        queries = [(name, None, True) for name in request.must_visit]
        queries += [(item["site"], item, False) for item in suggestions[:12]]
        for name, editorial, required in queries:
            existing = next((item for item in candidates.values() if normalized(item["site"]) == normalized(name)), None)
            if existing:
                existing["must_visit"] = existing.get("must_visit", False) or required
                if editorial:
                    existing.update({key: editorial[key] for key in ("duration_minutes", "category")})
                    existing["priority"] = max(existing["priority"], editorial["priority"])
                continue
            try:
                values = self.search(f"{name}, {request.city}", center, radius)
                found = bool(values) and add(values[0], editorial, required)
            except PlacesError:
                found = False
            if required and not found:
                warnings.append(f"No se pudo localizar el imprescindible «{name}» dentro del destino.")

        origin = None
        if request.accommodation and request.accommodation.strip():
            values = self.search(f"{request.accommodation}, {request.city}", center, radius)
            origin = parse_place(values[0]) if values else None
            if not origin or haversine(center, origin["coords"]) > radius / 1000:
                raise ValueError("No se encontró el alojamiento dentro del destino. Revisa su nombre o dirección.")
        if not candidates:
            raise PlacesError("No se encontraron atracciones verificadas en Google Places para este destino.")
        selected = sorted(candidates.values(), key=lambda item: (not item.get("must_visit"), -item["priority"], item["place_id"]))
        return selected[:min(80, max(16, request.days * 8))], origin, warnings
