"""OptiMapper API: verified candidates, feasible schedules and editable plans."""
import logging
import os
import random
import uuid
from copy import deepcopy

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client

from models.schemas import ItineraryRequest, ItineraryResponse, PlanningOptions, ReplanRequest
from services.claude_service import get_suggestions
from services.geocoding_service import discover_fallback
from services.optimizer_service import Planner, build_plan
from services.places_service import PlacesClient, PlacesError, PlacesQuotaError
from services.storage_service import hydrate_plan, serialize_plan
from services.travel_service import build_travel_times

load_dotenv()
logger = logging.getLogger(__name__)
supabase = None
if os.getenv("SUPABASE_URL", "").strip() and os.getenv("SUPABASE_KEY", "").strip():
    try:
        supabase = create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_KEY"].strip())
    except Exception:
        logger.warning("Supabase could not be initialized; using memory storage.")

app = FastAPI(title="OptiMapper API", description="Itinerarios turísticos con horarios y límites diarios", version="2.0.0")
allowed_origins = [value.strip() for value in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if value.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
itineraries_store: dict[str, dict] = {}


def _travel(pois, options, origin, google, preferred_pairs=None):
    return build_travel_times(pois + ([origin] if origin else []), options.travel_mode, options.pace, use_google=google, preferred_pairs=preferred_pairs)


def _route_pairs(itinerary, pois, origin):
    indices = {poi["place_id"]: i for i, poi in enumerate(pois)}
    pairs = []
    for stops in itinerary.values():
        route = [indices[poi["place_id"]] for poi in stops]
        if origin and route:
            route = [len(pois)] + route + [len(pois)]
        pairs.extend(zip(route, route[1:]))
    return pairs


def _response(city, days, options, pois, origin, google, warnings=None, assignments=None):
    preferred = None
    if google:
        draft = build_plan(pois, days, options, origin=origin, assignments=assignments)
        preferred = _route_pairs(draft["itinerary"], pois, origin)
    travel = _travel(pois, options, origin, google, preferred)
    plan = build_plan(pois, days, options, travel, origin, assignments)
    plan["warnings"] = list(dict.fromkeys((warnings or []) + plan["warnings"]))
    source = "estimated" if not travel.measured else ("mixed" if any(s["travel_estimated"] for s in plan["day_summaries"].values()) else "google")
    return ItineraryResponse(id=str(uuid.uuid4()), city=city, days=days, options=options, origin=origin,
                             places_source="google" if google else "nominatim", travel_times_source=source,
                             day_assignments=assignments or {}, **plan)


def _save(response):
    record = serialize_plan(response)
    if supabase:
        parts = response.city.split(", ", 1)
        supabase.schema("optimapper").table("itineraries").insert({
            "uuid": response.id, "city": parts[0], "country": parts[1] if len(parts) > 1 else None,
            "number_of_days": response.days, "itinerary": record,
        }).execute()
    else:
        itineraries_store[response.id] = record


def _load(identifier):
    if supabase:
        result = supabase.schema("optimapper").table("itineraries").select("*").eq("uuid", identifier).execute()
        if not result.data:
            raise HTTPException(404, "Itinerario no encontrado")
        row = result.data[0]
        record = row["itinerary"]
        if record.get("schema_version") != 2:
            city = f"{row['city']}, {row['country']}" if row.get("country") else row["city"]
            legacy = ItineraryResponse(id=identifier, city=city, days=row.get("number_of_days") or len(record), itinerary=record)
            return legacy.model_dump(mode="json")
    else:
        record = itineraries_store.get(identifier)
        if record is None:
            raise HTTPException(404, "Itinerario no encontrado")
    return hydrate_plan(record)


def _refresh_google(data):
    """Refresh saved order against live hours/routes without caching provider data."""
    if data.get("places_source") != "google":
        return data
    options = PlanningOptions.model_validate(data["options"])
    pois = [poi for key in data["itinerary"] for poi in data["itinerary"][key]]
    travel = _travel(pois, options, data.get("origin"), True, _route_pairs(data["itinerary"], pois, data.get("origin")))
    planner = Planner(pois, data["days"], options, travel, len(pois) if data.get("origin") else None)
    data["day_summaries"] = {}
    offset = 0
    for day in range(data["days"]):
        key = f"day_{day + 1}"
        count = len(data["itinerary"].get(key, []))
        evaluated = planner.evaluate(list(range(offset, offset + count)), day)
        offset += count
        if evaluated is not None:
            data["itinerary"][key], data["day_summaries"][key] = evaluated
        else:
            for item in data["itinerary"][key]:
                item["arrival_time"] = item["departure_time"] = None
            data["warnings"].append(f"El día {day + 1} ya no es viable con los datos actuales. Recalcula para actualizarlo.")
    data["warnings"] += travel.warnings
    missing = [item["site"] for item in data.get("unscheduled", []) if item.get("must_visit")]
    if missing:
        data["warnings"].append("No caben estos imprescindibles: " + ", ".join(missing) + ". Recalcula o amplía el tiempo disponible.")
    data["warnings"].append("Los horarios publicados y las duraciones estimadas deben confirmarse antes del viaje.")
    if not options.start_date:
        data["warnings"].append("Sin fecha de inicio no se comprueban los días de apertura.")
    if any(not p.get("opening_hours") for p in pois):
        data["warnings"].append("Algunos lugares no tienen horarios disponibles; confirma su apertura antes de viajar.")
    if any(s["travel_estimated"] for s in data["day_summaries"].values()):
        data["warnings"].append("Hay traslados estimados por distancia; pueden diferir del recorrido real.")
    data["travel_times_source"] = "estimated" if not travel.measured else ("mixed" if any(s["travel_estimated"] for s in data["day_summaries"].values()) else "google")
    data["warnings"] = list(dict.fromkeys(data["warnings"]))
    return data


def _failure(exc):
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, PlacesQuotaError):
        raise HTTPException(429, str(exc)) from exc
    if isinstance(exc, PlacesError):
        raise HTTPException(503, str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(422, str(exc)) from exc
    logger.error("Itinerary operation failed (%s)", type(exc).__name__)
    raise HTTPException(502, "No se pudo completar el itinerario. Comprueba los servicios configurados e inténtalo de nuevo.") from exc


@app.get("/")
def root():
    return {"message": "OptiMapper API – POST /itinerary para generar un itinerario"}


@app.post("/itinerary", response_model=ItineraryResponse)
def create_itinerary(request: ItineraryRequest):
    try:
        google = bool(os.getenv("GOOGLE_MAPS_API_KEY", "").strip())
        ai_enabled = os.getenv("ENABLE_AI_SUGGESTIONS", "true").strip().lower() in {"1", "true", "yes"}
        warnings, suggestions = [], []
        if not ai_enabled:
            if not google:
                raise ValueError("Las sugerencias de Claude están desactivadas. Configura Google Places para buscar lugares.")
            warnings.append("Las sugerencias de Claude están desactivadas para evitar consumo de Anthropic; se usan duraciones orientativas por categoría.")
        elif os.getenv("ANTHROPIC_API_KEY", "").strip() or not google:
            try:
                suggestions = get_suggestions(request.city, request.days, request.interests)
            except Exception:
                if not google:
                    raise
                warnings.append("Claude no está disponible; se usan lugares verificados de Google y duraciones orientativas por categoría.")
        else:
            warnings.append("Sin clave de Claude se usan duraciones orientativas por categoría.")
        pois, origin, provider_warnings = PlacesClient().discover(request, suggestions) if google else discover_fallback(request, suggestions)
        options = PlanningOptions.model_validate(request.model_dump())
        response = _response(request.city, request.days, options, pois, origin, google, warnings + provider_warnings)
        _save(response)
        return response
    except Exception as exc:
        _failure(exc)


@app.get("/itinerary/{itinerary_id}", response_model=ItineraryResponse)
def get_itinerary(itinerary_id: str):
    try:
        return ItineraryResponse.model_validate(_refresh_google(_load(itinerary_id)))
    except Exception as exc:
        _failure(exc)


@app.post("/itinerary/{itinerary_id}/replan", response_model=ItineraryResponse)
def replan_itinerary(itinerary_id: str, request: ReplanRequest):
    try:
        data = _load(itinerary_id)
        pois = [deepcopy(poi) for values in data["itinerary"].values() for poi in values] + deepcopy(data.get("unscheduled", []))
        # Old itineraries may not yet have stable identifiers.
        for poi in pois:
            if not poi.get("place_id"):
                poi["place_id"] = f"osm:{poi['site'].casefold()}:{poi['coords'][0]:.5f},{poi['coords'][1]:.5f}"
        known = {poi["place_id"] for poi in pois}
        requested = set(request.excluded_ids) | set(request.must_visit_ids) | set(request.day_assignments)
        if requested - known:
            raise ValueError("Algunos lugares no pertenecen a este itinerario. Recarga la página.")
        if any(day < 1 or day > data["days"] for day in request.day_assignments.values()):
            raise ValueError("El día elegido no existe en este viaje.")
        if set(request.excluded_ids) & (set(request.must_visit_ids) | set(request.day_assignments)):
            raise ValueError("Un lugar excluido no puede ser imprescindible ni tener un día asignado.")
        pois = [poi for poi in pois if poi["place_id"] not in request.excluded_ids]
        if not pois:
            raise ValueError("Conserva al menos un lugar para recalcular el itinerario.")
        required_ids = set(request.must_visit_ids) if "must_visit_ids" in request.model_fields_set else {poi["place_id"] for poi in pois if poi.get("must_visit")}
        assignments = request.day_assignments if "day_assignments" in request.model_fields_set else {key: day for key, day in data.get("day_assignments", {}).items() if key not in request.excluded_ids}
        for poi in pois:
            poi["must_visit"] = poi["place_id"] in required_ids or poi["place_id"] in assignments
        options = PlanningOptions.model_validate(data.get("options", {}))
        response = _response(data["city"], data["days"], options, pois, data.get("origin"), data.get("places_source") == "google", assignments=assignments)
        _save(response)
        return response
    except Exception as exc:
        _failure(exc)


@app.get("/itineraries/random")
def get_random_itineraries():
    if supabase:
        try:
            rows = supabase.schema("optimapper").table("itineraries").select("uuid, city, country, number_of_days").order("created_at", desc=True).limit(50).execute().data or []
            return [{"id": row["uuid"], "city": f"{row['city']}, {row['country']}" if row.get("country") else row["city"], "days": row.get("number_of_days") or 3} for row in random.sample(rows, min(3, len(rows)))]
        except Exception:
            return []
    values = list(itineraries_store.values())
    return [{"id": value["plan"]["id"], "city": value["plan"]["city"], "days": value["plan"]["days"]} for value in random.sample(values, min(3, len(values)))]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
