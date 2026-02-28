import math

import numpy as np
from sklearn.cluster import KMeans


def _haversine(coord1: list[float], coord2: list[float]) -> float:
    """Calcula la distancia en km entre dos puntos geográficos usando Haversine."""
    R = 6371  # Radio de la Tierra en km

    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def cluster_pois(pois: list[dict], num_days: int) -> dict[int, list[dict]]:
    """
    Agrupa los POIs en clusters usando K-Means.
    Devuelve un dict {cluster_id: [poi, ...]} con num_days clusters.
    """
    if len(pois) <= num_days:
        # Si hay menos POIs que días, un POI por día
        return {i: [poi] for i, poi in enumerate(pois)}

    coords = np.array([poi["coords"] for poi in pois])

    kmeans = KMeans(n_clusters=num_days, random_state=42, n_init=10)
    labels = kmeans.fit_predict(coords)

    clusters: dict[int, list[dict]] = {}
    for label, poi in zip(labels, pois):
        cluster_id = int(label)
        if cluster_id not in clusters:
            clusters[cluster_id] = []
        clusters[cluster_id].append(poi)

    return clusters


def optimize_route(pois: list[dict]) -> list[dict]:
    """
    Ordena los POIs usando el algoritmo de vecino más cercano (Nearest Neighbor)
    para obtener la ruta más eficiente dentro de un día.
    """
    if len(pois) <= 2:
        return pois

    remaining = list(range(len(pois)))
    route = [remaining.pop(0)]  # Empezar por el primer punto

    while remaining:
        last = route[-1]
        nearest_idx = None
        nearest_dist = float("inf")

        for idx in remaining:
            dist = _haversine(pois[last]["coords"], pois[idx]["coords"])
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_idx = idx

        route.append(nearest_idx)
        remaining.remove(nearest_idx)

    return [pois[i] for i in route]


def build_itinerary(pois: list[dict], num_days: int) -> dict[str, list[dict]]:
    """
    Pipeline completo: agrupa por proximidad y optimiza la ruta de cada día.
    Devuelve {"day_1": [...], "day_2": [...], ...}
    """
    clusters = cluster_pois(pois, num_days)
    itinerary = {}

    for i in range(num_days):
        day_pois = clusters.get(i, [])
        optimized = optimize_route(day_pois)
        itinerary[f"day_{i + 1}"] = optimized

    return itinerary
