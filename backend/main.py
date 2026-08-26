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

# Obtenemos las variables con un string vacío por defecto para que len() no falle
raw_url = os.getenv("SUPABASE_URL", "")
raw_key = os.getenv("SUPABASE_KEY", "")

# OPCIONAL: Limpieza por si acaso hay espacios invisibles
SUPABASE_URL = raw_url.strip()
SUPABASE_KEY = raw_key.strip()

supabase: Client | None = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase client initialized")
    except Exception:
        print("Supabase client initialization failed")


app = FastAPI(
    title="OptiMapper API",
    description="Genera itinerarios turísticos optimizados usando IA",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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
                "number_of_days": request.days,
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

@app.get("/itineraries/random")
def get_random_itineraries():
    """Recupera 3 itinerarios aleatorios de la base de datos."""
    import random
    if supabase:
        try:
            # Obtener los últimos 50 itinerarios para elegir aleatoriamente y no saturar la BD
            result = supabase.schema("optimapper").table("itineraries").select("uuid, city, country, number_of_days").order("created_at", desc=True).limit(50).execute()
            if result.data and len(result.data) > 0:
                pool = result.data
                # Si hay menos de 3, devolver todos
                sample_size = min(3, len(pool))
                random_selection = random.sample(pool, sample_size)
                
                # Mapear la salida
                return [
                    {
                        "id": row.get("uuid"),
                        "city": f"{row.get('city')}, {row.get('country')}" if row.get("country") else row.get("city"),
                        "days": row.get("number_of_days") or 3 # Fallback por si hay filas antiguas
                    }
                    for row in random_selection
                ]
            else:
                return []
        except Exception as e:
            print(f"Error fetching random itineraries: {e}")
            return []
    return []

if __name__ == "__main__":
    import uvicorn
    # Cloud Run inyecta la variable de entorno PORT
    port = int(os.environ.get("PORT", 8080))
    # Importante: host="0.0.0.0" para que sea visible externamente
    uvicorn.run(app, host="0.0.0.0", port=port)
