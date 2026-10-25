from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class PlanningOptions(BaseModel):
    start_date: Date | None = None
    pace: Literal["relaxed", "balanced", "intensive"] = "balanced"
    travel_mode: Literal["WALK", "DRIVE"] = "WALK"
    daily_start: str = Field("09:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    daily_hours: int = Field(8, ge=3, le=12)
    break_minutes: int = Field(45, ge=0, le=120)
    buffer_minutes: int = Field(30, ge=0, le=120)
    accommodation: str | None = Field(None, max_length=250)
    interests: list[Literal["culture", "history", "nature", "art"]] = Field(default_factory=list, max_length=4)
    must_visit: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def same_day(self):
        hour, minute = map(int, self.daily_start.split(":"))
        if hour * 60 + minute + self.daily_hours * 60 > 1440:
            raise ValueError("La jornada debe terminar antes de medianoche.")
        return self

    @field_validator("must_visit")
    @classmethod
    def clean_names(cls, names):
        cleaned = list(dict.fromkeys(name.strip() for name in names if name.strip()))
        if any(len(name) > 150 for name in cleaned):
            raise ValueError("Cada lugar debe tener como máximo 150 caracteres.")
        return cleaned


class ItineraryRequest(PlanningOptions):
    city: str = Field(..., min_length=1, max_length=200)
    days: int = Field(..., ge=1, le=14)

    @field_validator("city")
    @classmethod
    def clean_city(cls, value):
        if not value.strip():
            raise ValueError("El destino es obligatorio.")
        return value.strip()


class POI(BaseModel):
    site: str
    coords: list[float] = Field(..., min_length=2, max_length=2)
    place_id: str | None = None
    category: str = "landmark"
    duration_minutes: int = 60
    visit_minutes: int | None = None
    duration_estimated: bool = True
    priority: float = 50
    must_visit: bool = False
    source: str = "nominatim"
    rating: float | None = None
    review_count: int | None = None
    google_maps_uri: str | None = None
    attributions: list[dict] = Field(default_factory=list)
    arrival_time: str | None = None
    departure_time: str | None = None
    travel_minutes: int = 0
    travel_estimated: bool = True
    waiting_minutes: int = 0
    reason: str | None = None


class DaySummary(BaseModel):
    date: Date | None = None
    visit_minutes: int = 0
    travel_minutes: int = 0
    waiting_minutes: int = 0
    break_minutes: int = 0
    break_start: str | None = None
    buffer_minutes: int = 0
    total_minutes: int = 0
    available_minutes: int = 480
    finish_time: str | None = None
    return_minutes: int = 0
    travel_estimated: bool = True


class ItineraryResponse(BaseModel):
    id: str
    city: str
    days: int
    itinerary: dict[str, list[POI]]
    options: PlanningOptions = Field(default_factory=PlanningOptions)
    day_summaries: dict[str, DaySummary] = Field(default_factory=dict)
    unscheduled: list[POI] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    places_source: str = "nominatim"
    travel_times_source: str = "estimated"
    origin: POI | None = None
    day_assignments: dict[str, int] = Field(default_factory=dict)


class ReplanRequest(BaseModel):
    excluded_ids: list[str] = Field(default_factory=list, max_length=100)
    must_visit_ids: list[str] = Field(default_factory=list, max_length=100)
    day_assignments: dict[str, int] = Field(default_factory=dict, max_length=100)
