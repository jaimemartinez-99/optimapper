import json
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

# El cliente se inicializa dentro de get_pois para evitar errores al arrancar el servidor si falta la API KEY
# client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = (
    "Eres un experto en viajes y turismo. "
    "Cuando el usuario te pida sitios para visitar en una ciudad, "
    "responde ÚNICAMENTE con un JSON válido (sin texto adicional, sin markdown). "
    "El formato debe ser exactamente un array de strings con los nombres de los lugares. "
    "Ejemplo: [\"Museo del Prado\", \"Parque del Retiro\", \"Gran Vía\"]"
)


def get_pois(city: str, num_days: int) -> list[str]:
    """Consulta a Claude para obtener nombres de puntos de interés."""

    num_sites = num_days * 7  # ~7 sitios por día

    user_prompt = (
        f"Dame exactamente {num_sites} sitios turísticos imprescindibles para visitar "
        f"en {city} durante {num_days} días. "
        f"Incluye monumentos, museos, parques, barrios y lugares emblemáticos. "
        f"Responde SOLO con el JSON (array de strings), sin ningún texto adicional."
    )

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("No se ha configurado la variable de entorno ANTHROPIC_API_KEY.")

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",  # USANDO EL ÚLTIMO MODELO DISPONIBLE
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text.strip()

    # Limpiar si Claude envuelve en markdown
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1]).strip()

    names = json.loads(raw_text)

    if not isinstance(names, list) or not names:
        raise ValueError("Claude no devolvió una lista de sitios válida.")

    return [str(name) for name in names]
