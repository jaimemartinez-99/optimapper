import math
import os
import unittest
from unittest.mock import patch

import httpx

from models.schemas import ItineraryRequest, ItineraryResponse
from services.places_service import PlacesClient, PlacesQuotaError, parse_place
from services.storage_service import hydrate_plan, serialize_plan
from services.travel_service import build_travel_times


def raw_place(identifier="prado", name="Museo del Prado", lat=40.4):
    return {"id": identifier, "displayName": {"text": name}, "location": {"latitude": lat, "longitude": -3.7},
            "types": ["museum"], "rating": 4.8, "userRatingCount": 50000,
            "regularOpeningHours": {"periods": []}, "googleMapsUri": "https://maps.google.com/"}


class PlacesTests(unittest.TestCase):
    def test_city_viewport_excludes_a_neighboring_municipality_inside_radius(self):
        center = raw_place("city", "Madrid")
        center["viewport"] = {"low": {"latitude": 40.2, "longitude": -3.8}, "high": {"latitude": 40.6, "longitude": -3.6}}
        neighbor = raw_place("neighbor", "Outside city", 40.4)
        neighbor["location"]["longitude"] = -3.5
        with patch.object(PlacesClient, "search", return_value=[center]), patch.object(PlacesClient, "_request", return_value={"places": [raw_place(), neighbor]}):
            result, _, _ = PlacesClient().discover(ItineraryRequest(city="Madrid", days=2), [])
        self.assertEqual([item["place_id"] for item in result], ["prado"])

    def test_provider_quota_error_is_preserved(self):
        response = httpx.Response(429, request=httpx.Request("POST", "https://places.googleapis.com"))
        with patch("services.places_service.httpx.request", return_value=response):
            with self.assertRaises(PlacesQuotaError):
                PlacesClient().search("Madrid")

    def test_parsing_excludes_closed_places(self):
        value = raw_place()
        self.assertEqual(parse_place(value)["duration_minutes"], 120)
        value["businessStatus"] = "CLOSED_PERMANENTLY"
        self.assertIsNone(parse_place(value))

    @patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test"})
    def test_discovery_deduplicates_preserves_required_and_rejects_outside_city(self):
        def response(path, fields, payload=None):
            if payload.get("textQuery") == "Madrid, Spain":
                return {"places": [raw_place("city", "Madrid")]}
            if path.endswith("searchNearby"):
                return {"places": [raw_place(), raw_place("far", "Elsewhere", 45)]}
            if "Unknown" in payload.get("textQuery", ""):
                return {"places": []}
            return {"places": [raw_place()]}
        request = ItineraryRequest(city="Madrid, Spain", days=3, must_visit=["Museo del Prado", "Unknown"])
        with patch.object(PlacesClient, "_request", side_effect=response):
            places, origin, warnings = PlacesClient().discover(request, [])
        self.assertEqual(len(places), 1)
        self.assertTrue(places[0]["must_visit"])
        self.assertIsNone(origin)
        self.assertTrue(any("Unknown" in warning for warning in warnings))

    @patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test"})
    def test_google_content_is_not_persisted_and_is_hydrated_live(self):
        place = parse_place(raw_place())
        place["arrival_time"] = "10:00"
        plan = ItineraryResponse(id="id", city="Madrid", days=1, itinerary={"day_1": [place]}, places_source="google", origin=place)
        stored = serialize_plan(plan)
        reference = stored["plan"]["itinerary"]["day_1"][0]
        for field in ["coords", "site", "rating", "review_count", "opening_hours", "google_maps_uri"]:
            self.assertNotIn(field, reference)
        live = parse_place(raw_place(name="Updated name"))
        with patch.object(PlacesClient, "details", return_value=live) as lookup:
            restored = hydrate_plan(stored)
        self.assertEqual(lookup.call_count, 1)
        self.assertEqual(restored["itinerary"]["day_1"][0]["site"], "Updated name")
        self.assertEqual(restored["itinerary"]["day_1"][0]["arrival_time"], "10:00")
        self.assertNotIn("site", stored["plan"]["itinerary"]["day_1"][0])


class RoutesTests(unittest.TestCase):
    @patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test", "GOOGLE_ROUTES_MAX_ELEMENTS": "1"})
    def test_selected_itinerary_edges_take_priority_with_tiny_budget(self):
        points = [{"coords": [40.4 + i * .001, -3.7]} for i in range(4)]
        with patch("services.travel_service.httpx.Client.post", return_value=httpx.Response(200, request=httpx.Request("POST", "https://routes.googleapis.com"), json=[{"condition": "ROUTE_EXISTS", "duration": "600s"}])) as post:
            result = build_travel_times(points, use_google=True, preferred_pairs=[(3, 0), (2, 0)])
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result.leg(3, 0), (10, False))
        self.assertTrue(result.leg(2, 0)[1])

    @patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test", "GOOGLE_ROUTES_MAX_ELEMENTS": "12"})
    def test_bounded_directed_matrix_and_partial_errors(self):
        points = [{"coords": [40.4 + i * .001, -3.7]} for i in range(4)]
        calls = []

        def post(url, json, headers):
            calls.append(json)
            return httpx.Response(200, request=httpx.Request("POST", url), json=[
                {"originIndex": 0, "destinationIndex": 0, "condition": "ROUTE_EXISTS", "duration": "121s", "status": {}},
                {"destinationIndex": 1, "condition": "ROUTE_NOT_FOUND", "status": {"code": 5}},
                {"destinationIndex": 2, "status": {"code": 13}},
            ])
        with patch("services.travel_service.httpx.Client.post", side_effect=post):
            result = build_travel_times(points, use_google=True)
        self.assertLessEqual(sum(len(call["origins"]) * len(call["destinations"]) for call in calls), 12)
        self.assertTrue(any(value == math.inf for row in result.minutes for value in row))
        self.assertTrue(any(value == 3 for row in result.minutes for value in row))
        self.assertTrue(result.warnings)
        self.assertEqual(len(result.measured), 8)

    @patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test", "GOOGLE_ROUTES_MAX_ELEMENTS": "0"})
    def test_zero_budget_never_calls_google(self):
        points = [{"coords": [40.4, -3.7]}, {"coords": [40.41, -3.7]}]
        with patch("services.travel_service.httpx.Client") as client:
            result = build_travel_times(points, use_google=True)
        client.assert_not_called()
        self.assertTrue(result.leg(0, 1)[1])

    @patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test"})
    def test_outage_falls_back_with_explicit_estimates(self):
        points = [{"coords": [40.4, -3.7]}, {"coords": [40.41, -3.7]}]
        with patch("services.travel_service.httpx.Client.post", side_effect=httpx.ConnectError("offline")):
            result = build_travel_times(points, use_google=True)
        self.assertFalse(result.measured)
        self.assertTrue(result.leg(0, 1)[1])
        self.assertGreater(result.leg(0, 1)[0], 0)
