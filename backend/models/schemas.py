from pydantic import BaseModel, Field


class ItineraryRequest(BaseModel):
    city: str = Field(..., min_length=1, description="Nombre de la ciudad a visitar")
    days: int = Field(..., ge=1, le=14, description="Número de días del viaje (1-14)")


class POI(BaseModel):
    site: str
    coords: list[float] = Field(..., min_length=2, max_length=2)


class ItineraryResponse(BaseModel):
    id: str
    city: str
    days: int
    itinerary: dict[str, list[POI]]
