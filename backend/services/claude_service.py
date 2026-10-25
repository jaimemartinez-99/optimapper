"""Editorial suggestions; coordinates and opening hours come from providers."""
import json
import os

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()
CATEGORIES = {"museum", "monument", "park", "neighborhood", "landmark", "gallery"}


class Suggestion(BaseModel):
    site: str = Field(min_length=1, max_length=200)
    category: str = "landmark"
    duration_minutes: int = Field(60, ge=15, le=360)
    priority: int = Field(50, ge=1, le=100)


def get_suggestions(city: str, num_days: int, interests: list[str] | None = None) -> list[dict]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Configura ANTHROPIC_API_KEY o GOOGLE_MAPS_API_KEY para buscar lugares.")
    count = min(80, max(12, num_days * 8))
    prompt = (
        f"Propón hasta {count} lugares turísticos reales y distintos en {city}. "
        f"Son candidatos para un viaje de {num_days} días; no es obligatorio visitarlos todos. "
        f"Intereses: {', '.join(interests or []) or 'variados'}. "
        "Ordena primero los imprescindibles. Evita duplicar un recinto y sus partes. "
        "Estima duración de visita (sin traslados) y prioridad turística de 1 a 100. "
        "Devuelve un array JSON de objetos con site, category, duration_minutes y priority. "
        "category debe ser museum, monument, park, neighborhood, gallery o landmark. "
        "No incluyas coordenadas ni horarios. No inventes lugares para llenar la lista."
    )
    with anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=1) as client:
        response = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            max_tokens=10000,
            system="Eres un asesor turístico. Responde únicamente con JSON válido, sin markdown.",
            messages=[{"role": "user", "content": prompt}],
        )
    if response.stop_reason == "max_tokens":
        raise ValueError("La lista de lugares quedó incompleta. Intenta de nuevo con menos días.")
    raw = "".join(block.text for block in response.content if block.type == "text").strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:-1])
    values = json.loads(raw)
    if not isinstance(values, list) or not values:
        raise ValueError("Claude no devolvió una lista de lugares válida.")
    result, seen = [], set()
    for value in values[:count]:
        item = Suggestion.model_validate(value).model_dump()
        item["site"] = item["site"].strip()
        key = item["site"].casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        if item["category"] not in CATEGORIES:
            item["category"] = "landmark"
        result.append(item)
    if not result:
        raise ValueError("Claude no devolvió nombres de lugares válidos.")
    return result


def get_pois(city: str, num_days: int) -> list[str]:
    return [item["site"] for item in get_suggestions(city, num_days)]
