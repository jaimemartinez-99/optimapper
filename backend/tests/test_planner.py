import math
import unittest
from datetime import date

from models.schemas import PlanningOptions
from services.optimizer_service import build_plan, opening_intervals
from services.travel_service import TravelTimes


def poi(name, duration=60, lat=40.4, lng=-3.7, **kwargs):
    return {"site": name, "place_id": name, "coords": [lat, lng], "duration_minutes": duration, "priority": 50, **kwargs}


class PlannerTests(unittest.TestCase):
    def test_long_visits_are_balanced_by_time_not_stop_count(self):
        places = [poi("Museum A", 180), poi("Museum B", 180), poi("Square", 20), poi("Park", 30)]
        plan = build_plan(places, 2)
        museum_days = [key for key, stops in plan["itinerary"].items() if any(p["site"] == "Museum A" for p in stops) or any(p["site"] == "Museum B" for p in stops)]
        self.assertEqual(len(museum_days), 2)
        self.assertFalse(plan["unscheduled"])
        loads = [summary["total_minutes"] for summary in plan["day_summaries"].values()]
        self.assertLessEqual(max(loads) - min(loads), 60)

    def test_no_overflow_and_required_places_get_priority(self):
        places = [poi("Optional", 150, priority=100), poi("Required", 100, must_visit=True, priority=1), poi("Too long", 400, must_visit=True)]
        plan = build_plan(places, 1, PlanningOptions(daily_hours=3))
        self.assertEqual([p["site"] for p in plan["itinerary"]["day_1"]], ["Required"])
        self.assertLessEqual(plan["day_summaries"]["day_1"]["total_minutes"], 180)
        self.assertIn("Too long", " ".join(plan["warnings"]))

    def test_closed_monday_is_scheduled_tuesday_with_wait_until_open(self):
        museum = poi("Museum", 90, opening_hours={"periods": [{"open": {"day": 2, "hour": 10}, "close": {"day": 2, "hour": 13}}]})
        plan = build_plan([museum], 2, PlanningOptions(start_date=date(2026, 10, 26)))
        self.assertEqual(plan["itinerary"]["day_1"], [])
        visit = plan["itinerary"]["day_2"][0]
        self.assertEqual(visit["arrival_time"], "10:00")
        self.assertEqual(visit["waiting_minutes"], 60)
        self.assertEqual(plan["day_summaries"]["day_2"]["total_minutes"], 225)

    def test_visit_must_finish_before_closing(self):
        place = poi("Short opening", 120, opening_hours={"periods": [{"open": {"day": 1, "hour": 9}, "close": {"day": 1, "hour": 10}}]})
        plan = build_plan([place], 1, PlanningOptions(start_date=date(2026, 10, 26)))
        self.assertFalse(plan["itinerary"]["day_1"])
        self.assertEqual(len(plan["unscheduled"]), 1)

    def test_long_first_visit_does_not_schedule_lunch_before_departure(self):
        plan = build_plan([poi("Long museum", 240)], 1)
        self.assertEqual(plan["itinerary"]["day_1"][0]["arrival_time"], "09:00")
        self.assertEqual(plan["day_summaries"]["day_1"]["break_start"], "13:00")

    def test_unknown_hours_are_not_treated_as_closed(self):
        plan = build_plan([poi("Square")], 1, PlanningOptions(start_date=date(2026, 10, 26)))
        self.assertEqual(len(plan["itinerary"]["day_1"]), 1)
        self.assertTrue(any("no tienen horarios" in warning for warning in plan["warnings"]))

    def test_overnight_hours_and_special_closure(self):
        place = poi("Night", opening_hours={"periods": [{"open": {"day": 0, "hour": 20}, "close": {"day": 1, "hour": 2}}]})
        self.assertEqual(opening_intervals(place, date(2026, 10, 26)), [(0, 120)])
        place["current_opening_hours"] = {"specialDays": [{"date": {"year": 2026, "month": 10, "day": 26}}], "periods": []}
        self.assertEqual(opening_intervals(place, date(2026, 10, 26)), [])
        self.assertIsNone(opening_intervals(place, None))

    def test_hotel_return_and_margin_are_part_of_budget(self):
        places, hotel = [poi("Remote", 90)], poi("Hotel")
        travel = TravelTimes(places + [hotel])
        travel.minutes = [[0, 60], [60, 0]]
        plan = build_plan(places, 1, PlanningOptions(daily_hours=3), travel, hotel)
        self.assertEqual(len(plan["unscheduled"]), 1)
        plan = build_plan(places, 1, PlanningOptions(daily_hours=5), travel, hotel)
        summary = plan["day_summaries"]["day_1"]
        self.assertEqual(summary["travel_minutes"], 120)
        self.assertEqual(summary["return_minutes"], 60)
        self.assertEqual(summary["total_minutes"], 285)

    def test_unreachable_route_is_not_fabricated(self):
        places, hotel = [poi("Island")], poi("Hotel")
        travel = TravelTimes(places + [hotel])
        travel.minutes[1][0] = math.inf
        plan = build_plan(places, 1, travel=travel, origin=hotel)
        self.assertEqual(len(plan["unscheduled"]), 1)

    def test_pace_changes_visit_duration_without_compounding_on_replan(self):
        place = poi("Museum", 120)
        options = PlanningOptions(pace="relaxed")
        first = build_plan([place], 1, options)
        visit = first["itinerary"]["day_1"][0]
        self.assertEqual(visit["duration_minutes"], 120)
        self.assertEqual(visit["visit_minutes"], 150)
        again = build_plan([visit], 1, options)
        self.assertEqual(again["itinerary"]["day_1"][0]["visit_minutes"], 150)
        self.assertNotIn("arrival_time", place)

    def test_assignments_duplicates_and_more_days_than_places(self):
        a, b = poi("A"), poi("B")
        plan = build_plan([a, a, b], 4, assignments={"A": 3})
        all_stops = [stop for stops in plan["itinerary"].values() for stop in stops]
        self.assertEqual(len(all_stops), 2)
        self.assertEqual(plan["itinerary"]["day_3"][0]["site"], "A")
        self.assertEqual(len(plan["itinerary"]), 4)

    def test_spatially_separated_groups_do_not_crisscross(self):
        places = [poi("West A", lng=-3.9), poi("East A", lng=-3.5), poi("West B", lng=-3.899), poi("East B", lng=-3.499)]
        plan = build_plan(places, 2)
        self.assertFalse(plan["unscheduled"])
        for stops in plan["itinerary"].values():
            self.assertLess(max(p["coords"][1] for p in stops) - min(p["coords"][1] for p in stops), .01)

    def test_day_accounting_is_consistent(self):
        places = [poi(str(i), 90, lat=40.4 + i * .005) for i in range(20)]
        plan = build_plan(places, 3)
        identifiers = []
        for key, stops in plan["itinerary"].items():
            summary = plan["day_summaries"][key]
            self.assertLessEqual(summary["total_minutes"], summary["available_minutes"])
            self.assertEqual(summary["total_minutes"], sum(summary[field] for field in ["visit_minutes", "travel_minutes", "waiting_minutes", "break_minutes", "buffer_minutes"]))
            identifiers += [p["place_id"] for p in stops]
        identifiers += [p["place_id"] for p in plan["unscheduled"]]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(set(identifiers), {p["place_id"] for p in places})
