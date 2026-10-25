"""Versioned persistence; Google provider content is re-fetched by place ID."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from services.places_service import PlacesClient, PlacesError

# Editorial/user choices and the user's generated schedule, not a Places cache.
PLAN_FIELDS = {"place_id", "duration_minutes", "duration_estimated", "must_visit", "arrival_time", "departure_time",
               "visit_minutes", "waiting_minutes", "reason"}


def serialize_plan(response):
    data = response.model_dump(mode="json") if hasattr(response, "model_dump") else deepcopy(response)
    if data["places_source"] == "google":
        for key in data["itinerary"]:
            data["itinerary"][key] = [{k: v for k, v in item.items() if k in PLAN_FIELDS} for item in data["itinerary"][key]]
        data["unscheduled"] = [{k: v for k, v in item.items() if k in PLAN_FIELDS} for item in data["unscheduled"]]
        if data.get("origin"):
            data["origin"] = {"place_id": data["origin"]["place_id"]}
        # Provider travel durations and derived route summaries are request-scoped.
        data["day_summaries"] = {}
        data["warnings"] = [w for w in data["warnings"] if not w.startswith("No caben estos imprescindibles:")]
    return {"schema_version": 2, "plan": data}


def hydrate_plan(record):
    data = deepcopy(record["plan"])
    if data.get("places_source") != "google":
        return data
    client = PlacesClient()
    if not client.api_key:
        raise PlacesError("Configura GOOGLE_MAPS_API_KEY para recuperar este itinerario de Google Places.")
    items = [item for values in data["itinerary"].values() for item in values] + data.get("unscheduled", [])
    if data.get("origin"):
        items.append(data["origin"])
    identifiers = sorted({item["place_id"] for item in items})
    with ThreadPoolExecutor(max_workers=4) as executor:
        details = dict(zip(identifiers, executor.map(client.details, identifiers)))
    missing = []

    def hydrate(item):
        live = details[item["place_id"]]
        if live is None:
            missing.append(item["place_id"])
            return None
        # Live opening hours remain available internally when replanning.
        return {**live, **item}

    for key, values in data["itinerary"].items():
        data["itinerary"][key] = [value for item in values if (value := hydrate(item)) is not None]
    data["unscheduled"] = [value for item in data.get("unscheduled", []) if (value := hydrate(item)) is not None]
    if data.get("origin"):
        data["origin"] = hydrate(data["origin"])
    if missing:
        data["warnings"].append("Google ya no devuelve algunos lugares o están cerrados. Recalcula el itinerario para actualizarlo.")
    return data
