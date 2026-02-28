import uuid
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client

from models.schemas import ItineraryRequest, ItineraryResponse
from services.claude_service import get_pois
from services.geocoding_service import geocode_pois
from services.optimizer_service import build_itinerary

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print(f"DEBUG LOAD_DOTENV: URL={SUPABASE_URL is not None}, KEY={SUPABASE_KEY is not None}")

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    print("DEBUG: Initializing Supabase client")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


app = FastAPI(
    title="OptiMapper API",
    description="Genera itinerarios turísticos optimizados usando IA",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Almacén en memoria de respaldo si no hay supabase configurado
itineraries_store: dict[str, ItineraryResponse] = {}


@app.get("/")
def root():
    return {"message": "OptiMapper API – POST /itinerary para generar un itinerario"}


@app.post("/itinerary", response_model=ItineraryResponse)
def create_itinerary(request: ItineraryRequest):
    """
    Genera un itinerario turístico optimizado.

    1. Consulta a Claude para obtener nombres de puntos de interés
    2. Geocodifica todos los sitios con Nominatim (fuente única de coordenadas)
    3. Agrupa los puntos por proximidad geográfica (K-Means)
    4. Optimiza la ruta de cada día (Nearest Neighbor + Haversine)
    """
    try:
        # 1. Obtener nombres de POIs de Claude
        site_names = get_pois(request.city, request.days)

        # 2. Geocodificar con Nominatim
        pois = geocode_pois(site_names, request.city)

        # 3. Agrupar y optimizar
        itinerary = build_itinerary(pois, request.days)

        # 4. Generar UUID y almacenar
        itinerary_id = str(uuid.uuid4())
        
        # Extraer city y country si vienen en formato "City, Country"
        city_parts = request.city.split(", ", 1)
        city_name = city_parts[0]
        country_name = city_parts[1] if len(city_parts) > 1 else None
        
        response = ItineraryResponse(
            id=itinerary_id,
            city=request.city,
            days=request.days,
            itinerary=itinerary,
        )
        
        if supabase:
            data = {
                "uuid": itinerary_id,
                "city": city_name,
                "country": country_name,
                "itinerary": itinerary
            }
            supabase.schema("optimapper").table("itineraries").insert(data).execute()
        else:
            itineraries_store[itinerary_id] = response

        return response

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generando el itinerario: {str(e)}",
        )


@app.get("/itinerary/{itinerary_id}", response_model=ItineraryResponse)
def get_itinerary(itinerary_id: str):
    """Recupera un itinerario previamente generado por su UUID."""
    if supabase:
        try:
            result = supabase.schema("optimapper").table("itineraries").select("*").eq("uuid", itinerary_id).execute()
            if result.data and len(result.data) > 0:
                row = result.data[0]
                city = row.get("city")
                country = row.get("country")
                full_city = f"{city}, {country}" if country else city
                
                return ItineraryResponse(
                    id=row.get("uuid"),
                    city=full_city,
                    days=sum(1 for _ in row.get("itinerary", {}).keys()),
                    itinerary=row.get("itinerary", {})
                )
            else:
                raise HTTPException(status_code=404, detail="Itinerario no encontrado")
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=500, detail=f"Error al leer de Supabase: {str(e)}")
    else:
        if itinerary_id not in itineraries_store:
            raise HTTPException(status_code=404, detail="Itinerario no encontrado")
        return itineraries_store[itinerary_id]
