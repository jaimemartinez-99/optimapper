import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

# No credentials, database connections or paid calls in the test suite.
with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_KEY": "", "GOOGLE_MAPS_API_KEY": "", "ANTHROPIC_API_KEY": ""}):
    import main

from services.places_service import PlacesClient, PlacesError
from services.travel_service import TravelTimes


def places():
    return [{"site": name, "place_id": name, "coords": [40.4 + i * .001, -3.7], "duration_minutes": 90, "priority": 90 - i, "source": "nominatim"} for i, name in enumerate(["Museum", "Park", "Palace"])]


class ApiTests(unittest.TestCase):
    def setUp(self):
        main.itineraries_store.clear()
        self.client = TestClient(main.app)
        self.env = patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "", "ANTHROPIC_API_KEY": "test"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.suggestions = patch.object(main, "get_suggestions", return_value=[])
        self.suggestion_mock = self.suggestions.start()
        self.addCleanup(self.suggestions.stop)
        self.discovery = patch.object(main, "discover_fallback", return_value=(places(), None, []))
        self.discovery_mock = self.discovery.start()
        self.addCleanup(self.discovery.stop)

    def test_create_retrieve_replan_without_changing_original(self):
        original = self.client.post("/itinerary", json={"city": "Madrid", "days": 2})
        self.assertEqual(original.status_code, 200, original.text)
        identifier = original.json()["id"]
        self.assertEqual(self.client.get(f"/itinerary/{identifier}").json(), original.json())
        updated = self.client.post(f"/itinerary/{identifier}/replan", json={"excluded_ids": ["Park"], "must_visit_ids": ["Museum"], "day_assignments": {"Museum": 2}})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertNotEqual(updated.json()["id"], identifier)
        self.assertIn("Museum", [p["site"] for p in updated.json()["itinerary"]["day_2"]])
        self.assertNotIn("Park", str(updated.json()["itinerary"]))
        self.assertEqual(updated.json()["day_assignments"], {"Museum": 2})
        repeated = self.client.post(f"/itinerary/{updated.json()['id']}/replan", json={})
        self.assertEqual(repeated.status_code, 200, repeated.text)
        self.assertEqual(repeated.json()["day_assignments"], {"Museum": 2})
        self.assertIn("Museum", [p["site"] for p in repeated.json()["itinerary"]["day_2"]])
        self.assertEqual(self.client.get(f"/itinerary/{identifier}").json(), original.json())

    def test_invalid_inputs_and_unknown_itinerary(self):
        for body in [{"city": " ", "days": 2}, {"city": "Madrid", "days": 0}, {"city": "Madrid", "days": 2, "daily_start": "23:00"}]:
            self.assertEqual(self.client.post("/itinerary", json=body).status_code, 422)
        self.assertEqual(self.client.get("/itinerary/missing").status_code, 404)
        self.assertEqual(self.client.post("/itinerary/missing/replan", json={}).status_code, 404)

    def test_replan_rejects_unknown_places_and_invalid_days(self):
        identifier = self.client.post("/itinerary", json={"city": "Madrid", "days": 2}).json()["id"]
        for body in [{"excluded_ids": ["unknown"]}, {"day_assignments": {"Museum": 3}}, {"excluded_ids": ["Museum"], "must_visit_ids": ["Museum"]}]:
            self.assertEqual(self.client.post(f"/itinerary/{identifier}/replan", json=body).status_code, 422)

    def test_google_only_create_and_live_retrieval(self):
        def travel(pois, options, origin, google, preferred_pairs=None):
            return TravelTimes(pois + ([origin] if origin else []), options.travel_mode, options.pace)
        google_places = [{**poi, "source": "google"} for poi in places()]
        by_id = {p["place_id"]: p for p in google_places}
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test", "ANTHROPIC_API_KEY": ""}), patch.object(PlacesClient, "discover", return_value=(google_places, None, [])), patch.object(PlacesClient, "details", side_effect=lambda identifier: by_id[identifier]), patch.object(main, "_travel", side_effect=travel):
            generated = self.client.post("/itinerary", json={"city": "Madrid", "days": 2})
            self.assertEqual(generated.status_code, 200, generated.text)
            identifier = generated.json()["id"]
            self.assertNotIn("coords", str(main.itineraries_store[identifier]["plan"]["itinerary"]))
            retrieved = self.client.get(f"/itinerary/{identifier}")
            self.assertEqual(retrieved.status_code, 200, retrieved.text)
            self.assertEqual(retrieved.json()["places_source"], "google")
            self.assertEqual(len(retrieved.json()["day_summaries"]), 2)
            recalculated = self.client.post(f"/itinerary/{identifier}/replan", json={"must_visit_ids": ["Museum"]})
            self.assertEqual(recalculated.status_code, 200, recalculated.text)
        self.suggestion_mock.assert_not_called()

    def test_provider_failure_is_actionable_and_not_silently_switched(self):
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test"}), patch.object(PlacesClient, "discover", side_effect=PlacesError("Google no está disponible")):
            result = self.client.post("/itinerary", json={"city": "Madrid", "days": 2})
        self.assertEqual(result.status_code, 503)
        self.discovery_mock.assert_not_called()

    def test_legacy_database_rows_remain_readable(self):
        from unittest.mock import MagicMock
        database = MagicMock()
        database.schema.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"uuid": "legacy", "city": "Madrid", "country": "Spain", "itinerary": {"day_1": [{"site": "Park", "coords": [40.4, -3.7]}]}}
        ]
        with patch.object(main, "supabase", database):
            response = self.client.get("/itinerary/legacy")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["days"], 1)
