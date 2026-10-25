"""Time-budgeted insertion and local search with opening-hour constraints.

Each proposed move is rescheduled in full, including waits, breaks and hotel
return. No infeasible route is accepted. This is a bounded heuristic, not a
promise of a globally optimal solution.
"""
import math
from datetime import date, timedelta

from models.schemas import PlanningOptions
from services.travel_service import TravelTimes, haversine


def _haversine(a, b):
    return haversine(a, b)


def clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _point_date(point):
    value = point.get("date")
    return date(value["year"], value["month"], value["day"]) if value else None


def opening_intervals(poi, target):
    """None means unknown. [] means known closed. Times are destination-local."""
    if target is None:
        return None
    current = poi.get("current_opening_hours") or {}
    special = {date(v["date"]["year"], v["date"]["month"], v["date"]["day"]) for v in current.get("specialDays", []) if v.get("date")}
    if target in special:
        intervals = []
        for period in current.get("periods", []):
            start, end = period.get("open", {}), period.get("close", {})
            start_date, end_date = _point_date(start), _point_date(end)
            if not start_date:
                continue
            lo = (start_date - target).days * 1440 + start.get("hour", 0) * 60 + start.get("minute", 0)
            hi = ((end_date - target).days * 1440 + end.get("hour", 0) * 60 + end.get("minute", 0)) if end_date else lo + 1440
            if hi > 0 and lo < 1440:
                intervals.append((max(0, lo), min(1440, hi)))
        return sorted(intervals)
    hours = poi.get("opening_hours")
    if hours is None or "periods" not in hours:
        return None
    weekday = (target.weekday() + 1) % 7  # Google: Sunday = 0.
    intervals = []
    for period in hours["periods"]:
        start, end = period.get("open", {}), period.get("close")
        if not end:
            return [(0, 1440)]  # Google's 24/7 representation.
        lo = start.get("day", 0) * 1440 + start.get("hour", 0) * 60 + start.get("minute", 0)
        hi = end.get("day", 0) * 1440 + end.get("hour", 0) * 60 + end.get("minute", 0)
        if hi <= lo:
            hi += 7 * 1440
        for shift in (-7 * 1440, 0, 7 * 1440):
            left, right = lo + shift - weekday * 1440, hi + shift - weekday * 1440
            if right > 0 and left < 1440:
                intervals.append((max(0, left), min(1440, right)))
    return sorted(intervals)


class Planner:
    def __init__(self, pois, days, options, travel, origin_index=None, assignments=None):
        self.pois, self.days, self.options, self.travel = pois, days, options, travel
        self.origin = origin_index
        self.assignments = assignments or {}
        hour, minute = map(int, options.daily_start.split(":"))
        self.start = hour * 60 + minute
        self.capacity = options.daily_hours * 60
        self.deadline = min(1440, self.start + self.capacity)
        self.dates = [options.start_date + timedelta(days=i) if options.start_date else None for i in range(days)]
        self.windows = [[opening_intervals(poi, day) for poi in pois] for day in self.dates]
        self.duration = [math.ceil(poi.get("duration_minutes", 60) * {"relaxed": 1.25, "balanced": 1, "intensive": 0.85}[options.pace]) for poi in pois]
        self.neighborhood_support = [sum(haversine(poi["coords"], other["coords"]) <= 2 for other in pois) for poi in pois]

    def evaluate(self, route, day):
        summary = {"date": self.dates[day], "visit_minutes": 0, "travel_minutes": 0, "waiting_minutes": 0,
                   "break_minutes": 0, "break_start": None, "buffer_minutes": 0, "total_minutes": 0,
                   "available_minutes": self.capacity, "finish_time": None, "return_minutes": 0, "travel_estimated": False}
        if not route:
            return [], summary
        now, previous, stops = self.start, self.origin, []
        break_at = self.start + min(180, self.capacity // 2)
        rested = False
        for index in route:
            poi = self.pois[index]
            assigned = self.assignments.get(poi["place_id"])
            if assigned is not None and assigned != day + 1:
                return None
            duration = self.duration[index]
            travel, estimated = self.travel.leg(previous, index)
            if not math.isfinite(travel):
                return None
            # Do not put lunch at the start merely because the first museum is
            # long. A long uninterrupted visit can move the break a little later.
            earliest_break = self.start + min(120, self.capacity // 3)
            if not rested and now >= earliest_break and now + travel + duration > break_at:
                summary["break_start"] = clock(now)
                now += self.options.break_minutes
                rested = True
            arrival = now + travel
            windows = self.windows[day][index]
            if windows is not None:
                slots = [max(arrival, lo) for lo, hi in windows if max(arrival, lo) + duration <= hi]
                if not slots:
                    return None
                visit_start = min(slots)
            else:
                visit_start = arrival
            waiting = visit_start - arrival
            now = visit_start + duration
            if now + self.options.buffer_minutes > self.deadline:
                return None
            stops.append({**poi, "arrival_time": clock(visit_start), "departure_time": clock(now),
                          "visit_minutes": duration, "travel_minutes": travel, "travel_estimated": estimated,
                          "waiting_minutes": waiting, "reason": None})
            summary["visit_minutes"] += duration
            summary["travel_minutes"] += travel
            summary["waiting_minutes"] += waiting
            summary["travel_estimated"] |= estimated
            previous = index
        return_time, estimated = self.travel.leg(previous, self.origin)
        if not math.isfinite(return_time):
            return None
        if not rested:
            summary["break_start"] = clock(now)
            now += self.options.break_minutes
        now += return_time + self.options.buffer_minutes
        if now > self.deadline:
            return None
        summary.update({"travel_minutes": summary["travel_minutes"] + return_time, "return_minutes": return_time,
                        "break_minutes": self.options.break_minutes, "buffer_minutes": self.options.buffer_minutes,
                        "total_minutes": now - self.start, "finish_time": clock(now),
                        "travel_estimated": summary["travel_estimated"] or estimated})
        return stops, summary

    @staticmethod
    def objective(summaries):
        loads = [s["total_minutes"] for s in summaries]
        mean = sum(loads) / len(loads)
        imbalance = sum((load - mean) ** 2 for load in loads) / max(1, mean)
        return sum(s["travel_minutes"] + s["waiting_minutes"] for s in summaries) + 0.4 * imbalance

    def solve(self):
        routes = [[] for _ in range(self.days)]
        summaries = [self.evaluate([], day)[1] for day in range(self.days)]
        order = sorted(range(len(self.pois)), key=lambda i: (not self.pois[i].get("must_visit", False), -self.pois[i].get("priority", 50), self.pois[i]["place_id"]))
        # Seed geographically distinct days. Without this, two free starts can
        # consume both days in one neighborhood and strand an entire other area.
        seeds = []
        for day in range(self.days):
            feasible = [i for i in order if i not in seeds and self.evaluate([i], day) is not None]
            if not feasible:
                continue
            def seed_score(index):
                separation = min((haversine(self.pois[index]["coords"], self.pois[other]["coords"]) for other in seeds), default=0)
                # Prefer a neighborhood with several visits over a lone distant
                # attraction; a large distance alone should not consume a day.
                geographic_score = min(5, separation) * math.sqrt(self.neighborhood_support[index])
                return (bool(self.pois[index].get("must_visit")), self.neighborhood_support[index] > 1,
                        geographic_score * math.sqrt(self.pois[index].get("priority", 50) / 100), self.pois[index].get("priority", 50))
            index = max(feasible, key=seed_score)
            routes[day] = [index]
            summaries[day] = self.evaluate([index], day)[1]
            seeds.append(index)
        remaining = []
        for index in order:
            if index in seeds:
                continue
            best = None
            for day, route in enumerate(routes):
                for position in range(len(route) + 1):
                    trial = route[:position] + [index] + route[position:]
                    evaluated = self.evaluate(trial, day)
                    if evaluated is None:
                        continue
                    updated = list(summaries)
                    updated[day] = evaluated[1]
                    cost = self.objective(updated)
                    if best is None or cost < best[0]:
                        best = cost, day, trial, evaluated[1]
            if best is None:
                remaining.append(index)
            else:
                _, day, routes[day], summaries[day] = best

        # Relocate both within and between days; every move preserves feasibility.
        for _ in range(3):
            improved = False
            for source in range(self.days):
                for index in list(routes[source]):
                    original = routes[source]
                    reduced = [i for i in original if i != index]
                    source_eval = self.evaluate(reduced, source)
                    if source_eval is None:
                        continue
                    best = None
                    baseline = self.objective(summaries)
                    for destination in range(self.days):
                        target = reduced if destination == source else routes[destination]
                        for position in range(len(target) + 1):
                            trial = target[:position] + [index] + target[position:]
                            evaluated = self.evaluate(trial, destination)
                            if evaluated is None:
                                continue
                            updated = list(summaries)
                            updated[source] = source_eval[1]
                            updated[destination] = evaluated[1]
                            cost = self.objective(updated)
                            if cost + 0.01 < baseline and (best is None or cost < best[0]):
                                best = cost, destination, trial, updated
                    if best:
                        _, destination, trial, summaries = best
                        routes[source] = reduced
                        routes[destination] = trial
                        improved = True
            if not improved:
                break

        # Local search can free enough time to insert previously rejected places.
        for index in remaining[:]:
            best = None
            for day, route in enumerate(routes):
                for position in range(len(route) + 1):
                    trial = route[:position] + [index] + route[position:]
                    evaluated = self.evaluate(trial, day)
                    if evaluated:
                        updated = list(summaries)
                        updated[day] = evaluated[1]
                        cost = self.objective(updated)
                        if best is None or cost < best[0]:
                            best = cost, day, trial, evaluated[1]
            if best:
                _, day, routes[day], summaries[day] = best
                remaining.remove(index)
        return routes, remaining


def build_plan(pois, num_days, options=None, travel=None, origin=None, assignments=None):
    options = options or PlanningOptions()
    # Copy records: recalculation must never mutate a previously saved plan.
    candidates, seen = [], set()
    for poi in pois:
        item = dict(poi)
        if not item.get("place_id"):
            item["place_id"] = f"osm:{item['site'].casefold()}:{item['coords'][0]:.5f},{item['coords'][1]:.5f}"
        if item["place_id"] in seen:
            continue
        seen.add(item["place_id"])
        candidates.append(item)
    points = candidates + ([origin] if origin else [])
    travel = travel or TravelTimes(points, options.travel_mode, options.pace)
    planner = Planner(candidates, num_days, options, travel, len(candidates) if origin else None, assignments)
    routes, remaining = planner.solve()
    itinerary, summaries = {}, {}
    for day, indices in enumerate(routes):
        itinerary[f"day_{day + 1}"], summaries[f"day_{day + 1}"] = planner.evaluate(indices, day)
    unscheduled = [{**candidates[i], "reason": "No cabe en los días disponibles respetando horarios, traslados y descansos."} for i in remaining]
    warnings = list(travel.warnings)
    if origin is None:
        warnings.append("Sin alojamiento, la jornada empieza en la primera visita y termina en la última; no se incluyen los traslados al hotel.")
    if not options.start_date:
        warnings.append("Sin fecha de inicio no se comprueban los días de apertura.")
    if any(not item.get("opening_hours") for item in candidates):
        warnings.append("Algunos lugares no tienen horarios disponibles; confirma su apertura antes de viajar.")
    if options.start_date and any(item.get("opening_hours") for item in candidates):
        warnings.append("Se usan horarios publicados; los festivos, reservas y cambios futuros pueden requerir ajustes.")
    missing = [item["site"] for item in unscheduled if item.get("must_visit")]
    if missing:
        warnings.append("No caben estos imprescindibles: " + ", ".join(missing) + ". Amplía el tiempo o elimina otras visitas.")
    if any(value["travel_estimated"] for value in summaries.values()):
        warnings.append("Los traslados marcados como estimados se calculan por distancia y pueden diferir del recorrido real.")
    return {"itinerary": itinerary, "day_summaries": summaries, "unscheduled": unscheduled, "warnings": warnings}


def build_itinerary(pois, num_days):
    """Compatibility entry point using the same feasible scheduler."""
    return build_plan(pois, num_days)["itinerary"]
