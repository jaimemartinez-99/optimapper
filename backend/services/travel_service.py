"""Bounded Google Route Matrix requests, with explicit per-leg estimates."""
import math
import os
from concurrent.futures import ThreadPoolExecutor

import httpx


def haversine(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, [*a, *b])
    value = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(1, max(0, value))))


class TravelTimes:
    def __init__(self, points: list[dict], mode="WALK", pace="balanced"):
        self.points = points
        speed = (3.5 if pace == "relaxed" else 4.5) if mode == "WALK" else 25
        self.minutes = [
            [0 if i == j else max(1, math.ceil(haversine(a["coords"], b["coords"]) * 1.35 / speed * 60 + (8 if mode == "DRIVE" else 0)))
             for j, b in enumerate(points)]
            for i, a in enumerate(points)
        ]
        self.measured: set[tuple[int, int]] = set()
        self.warnings: list[str] = []

    def leg(self, origin: int | None, destination: int | None):
        if origin is None or destination is None or origin == destination:
            return 0, False
        return self.minutes[origin][destination], (origin, destination) not in self.measured


def build_travel_times(points: list[dict], mode="WALK", pace="balanced", use_google=False, preferred_pairs=None) -> TravelTimes:
    result = TravelTimes(points, mode, pace)
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not use_google or not api_key or len(points) < 2:
        return result
    try:
        budget = max(0, min(2500, int(os.getenv("GOOGLE_ROUTES_MAX_ELEMENTS", "20"))))
    except ValueError:
        budget = 20
    count = len(points)
    if not budget:
        result.warnings.append("No se consultó Routes por el límite de coste configurado; los traslados son estimados.")
        return result

    # The quota counts origin/destination elements, not HTTP requests. Query only
    # the proposed route's directed legs; keep alternatives as explicit estimates.
    targets = {i: [] for i in range(count)}
    selected = set()

    def select(origin, destination):
        if (len(selected) < budget and origin != destination and
                0 <= origin < count and 0 <= destination < count and (origin, destination) not in selected):
            selected.add((origin, destination))
            targets[origin].append(destination)

    for origin, destination in preferred_pairs or []:
        select(origin, destination)
    if not selected:
        return result

    def waypoint(index):
        lat, lng = points[index]["coords"]
        return {"waypoint": {"location": {"latLng": {"latitude": lat, "longitude": lng}}}}

    def fetch(origin):
        destinations = targets[origin]
        try:
            response = client.post(
                "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix",
                json={"origins": [waypoint(origin)], "destinations": [waypoint(j) for j in destinations], "travelMode": mode},
                headers={"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": "originIndex,destinationIndex,duration,status,condition"},
            )
            response.raise_for_status()
            values = response.json()
            if not isinstance(values, list):
                return []
            entries = []
            for value in values:
                index = value.get("destinationIndex", 0)
                if not 0 <= index < len(destinations):
                    continue
                if value.get("condition") == "ROUTE_NOT_FOUND":
                    entries.append((origin, destinations[index], math.inf))
                elif not value.get("status", {}).get("code", 0) and value.get("condition") == "ROUTE_EXISTS" and "duration" in value:
                    seconds = float(value["duration"].removesuffix("s"))
                    if math.isfinite(seconds) and seconds >= 0:
                        entries.append((origin, destinations[index], max(1, math.ceil(seconds / 60))))
            return entries
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            return []

    with httpx.Client(timeout=20.0) as client, ThreadPoolExecutor(max_workers=4) as executor:
        for entries in executor.map(fetch, [i for i in range(count) if targets[i]]):
            for i, j, duration in entries:
                result.minutes[i][j] = duration
                result.measured.add((i, j))
    if len(result.measured) < count * (count - 1):
        result.warnings.append("Parte de los traslados son estimaciones: se limita el coste de Routes o faltan rutas del proveedor.")
    return result
