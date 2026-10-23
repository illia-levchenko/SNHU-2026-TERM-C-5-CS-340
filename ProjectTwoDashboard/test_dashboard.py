"""Behavior checks for the rescue dashboard; no MongoDB server is contacted.

Run from this folder with: python -m unittest -v test_dashboard.py
Use the same dependencies as the dashboard (requirements.txt).
"""

import math
import re
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

import dashboard_app as dashboard


def matches_rule(document, query):
    """Evaluate this dashboard's query subset against a fixture."""
    if not query:
        return True
    bounds = query["age_upon_outcome_in_weeks"]
    return (
        document["animal_type"] == query["animal_type"]
        and document["sex_upon_outcome"] == query["sex_upon_outcome"]
        and bounds["$gte"] <= document["age_upon_outcome_in_weeks"] <= bounds["$lte"]
        and re.search(query["breed"]["$regex"], document["breed"], re.I) is not None
    )


class RescueRuleTests(unittest.TestCase):
    def test_all_reads_entire_collection(self):
        self.assertEqual(dashboard.build_query("all"), {})
        with self.assertRaises(ValueError):
            dashboard.build_query("unrecognized")

    def test_inclusive_age_limits_and_required_sex_for_each_category(self):
        cases = [
            ("water", "Labrador Retriever Mix", "Intact Female", 26, 156),
            ("mountain", "German Shepherd", "Intact Male", 26, 156),
            ("disaster", "Doberman Pinscher", "Intact Male", 20, 300),
        ]
        for category, breed, sex, youngest, oldest in cases:
            query = dashboard.build_query(category)
            dog = {"animal_type": "Dog", "breed": breed, "sex_upon_outcome": sex}
            for age, expected in [(youngest - 0.01, False), (youngest, True), (oldest, True), (oldest + 0.01, False)]:
                with self.subTest(category=category, age=age):
                    self.assertEqual(matches_rule(dict(dog, age_upon_outcome_in_weeks=age), query), expected)
            eligible = dict(dog, age_upon_outcome_in_weeks=youngest)
            self.assertFalse(matches_rule(dict(eligible, animal_type="Cat"), query))
            self.assertFalse(matches_rule(dict(eligible, sex_upon_outcome="Neutered Male"), query))

    def test_every_required_breed_and_documented_mix_handling(self):
        breeds = {
            "water": ["Labrador Retriever Mix", "Chesapeake Bay Retriever", "Newfoundland"],
            "mountain": ["German Shepherd", "Alaskan Malamute", "Old English Sheepdog", "Siberian Husky", "Rottweiler"],
            "disaster": ["Doberman Pinscher", "German Shepherd", "Golden Retriever", "Bloodhound", "Rottweiler"],
        }
        for category, expected_breeds in breeds.items():
            query = dashboard.build_query(category)
            for breed in expected_breeds:
                for value in [breed, breed.lower(), breed + "/Beagle"]:
                    with self.subTest(category=category, breed=value):
                        dog = {"animal_type": "Dog", "breed": value, "sex_upon_outcome": query["sex_upon_outcome"], "age_upon_outcome_in_weeks": 52}
                        self.assertTrue(matches_rule(dog, query))
            self.assertIsNone(re.search(query["breed"]["$regex"], "Unrelated Terrier", re.I))
        water = dashboard.build_query("water")
        self.assertIsNone(re.search(water["breed"]["$regex"], "Labrador Retriever", re.I))
        self.assertIsNone(re.search(water["breed"]["$regex"], "Newfoundlandish", re.I))


class DataAndSelectionTests(unittest.TestCase):
    def test_duplicate_animal_ids_remain_distinct_rows(self):
        source = [{"_id": 101, "animal_id": "A1"}, {"_id": 102, "animal_id": "A1"}]
        result = dashboard.normalize_records(source)
        self.assertEqual([row["id"] for row in result], ["101", "102"])
        self.assertEqual(source[0]["_id"], 101)  # Normalization must not mutate source data.
        with self.assertRaises(ValueError):
            dashboard.normalize_records([{"animal_id": "A1"}])

    def test_json_values_are_serializable_and_nonfinite_numbers_are_empty(self):
        result = dashboard.json_value({"day": date(2026, 10, 12), "values": [math.nan, math.inf, -math.inf, 4.5]})
        self.assertEqual(result, {"day": "2026-10-12", "values": [None, None, None, 4.5]})

    def test_selection_survives_sort_and_filters_by_identity(self):
        first = {"id": "first", "animal_id": "A1"}
        second = {"id": "second", "animal_id": "A1"}
        self.assertIs(dashboard.select_record([second, first], ["first"]), first)
        self.assertIs(dashboard.select_record([second], ["first"]), second)
        self.assertIs(dashboard.select_record([first, second], []), first)
        self.assertIsNone(dashboard.select_record([], ["first"]))

    def test_coordinates_are_named_finite_and_in_range(self):
        self.assertEqual(dashboard.valid_coordinates({"unrelated": "value", "location_long": "-97.7", "location_lat": "30.2"}), (30.2, -97.7))
        for latitude, longitude in [(None, -97), ("", -97), (math.nan, -97), (30, math.inf), (91, 0), (0, -181), ("bad", 0)]:
            with self.subTest(latitude=latitude, longitude=longitude):
                self.assertIsNone(dashboard.valid_coordinates({"location_lat": latitude, "location_long": longitude}))
        self.assertEqual(dashboard.valid_coordinates({"location_lat": 0, "location_long": 0}), (0.0, 0.0))

    def test_breed_aggregation_preserves_total_including_unknown_and_other(self):
        records = [{"breed": "Common"}] * 5 + [{"breed": "Breed {:02d}".format(i)} for i in range(12)] + [{"breed": ""}, {}]
        result = dashboard.breed_counts(records)
        self.assertEqual(sum(count for _, count in result), 19)
        self.assertEqual(result[0], ("Common", 5))
        self.assertEqual(dict(result)["Unknown breed"], 2)
        self.assertEqual(result[-1], ("Other breeds", 4))

    def test_figure_uses_all_filtered_rows_not_a_single_table_page(self):
        records = [{"breed": "Labrador Retriever Mix"}] * 17 + [{"breed": "Newfoundland"}] * 3
        figure = dashboard.breed_figure(records)
        self.assertEqual(sum(figure.data[0].values), 20)
        self.assertIn("20", figure.layout.annotations[0].text)
        empty = dashboard.breed_figure([])
        self.assertEqual(len(empty.data), 0)
        self.assertIn("No animals", empty.layout.annotations[0].text)

    def test_missing_location_does_not_create_a_false_marker(self):
        content = dashboard.map_content([{"id": "a", "animal_id": "A1"}], ["a"])
        self.assertIn("no valid location", content.children[0].children)
        self.assertEqual(len(content.children[1].children), 1)  # Tile layer only.
        empty = dashboard.map_content([], [])
        self.assertIn("No animals", empty.children[0].children)

    def test_selected_row_coordinates_drive_map_after_sort(self):
        first = {"id": "first", "location_lat": 30.1, "location_long": -97.1}
        second = {"id": "second", "location_lat": 31.2, "location_long": -98.2}
        content = dashboard.map_content([second, first], ["first"])
        self.assertEqual(content.children[1].center, [30.1, -97.1])
        self.assertEqual(content.children[1].children[1].position, [30.1, -97.1])


class DatabaseBoundaryTests(unittest.TestCase):
    def test_crud_receives_category_query_and_connection_always_closes(self):
        shelter = Mock()
        shelter.read.return_value = [{"_id": "a", "animal_id": "A1"}]
        factory = Mock(return_value=shelter)
        records = dashboard.load_records("water", shelter_factory=factory)
        shelter.read.assert_called_once_with(dashboard.build_query("water"))
        self.assertEqual(records[0]["id"], "a")
        shelter.close.assert_called_once_with()

    def test_empty_results_are_verified_and_read_failures_are_not_hidden(self):
        shelter = Mock()
        shelter.read.return_value = []
        shelter.collection.count_documents.return_value = 0
        self.assertEqual(dashboard.load_records("water", shelter_factory=lambda *a, **k: shelter), [])
        shelter.collection.count_documents.return_value = 2
        with self.assertRaises(RuntimeError):
            dashboard.load_records("water", shelter_factory=lambda *a, **k: shelter)
        shelter.collection.count_documents.side_effect = ConnectionError("offline")
        with self.assertRaises(ConnectionError):
            dashboard.load_records("water", shelter_factory=lambda *a, **k: shelter)
        self.assertEqual(shelter.close.call_count, 3)


class CallbackBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"id": "a", "_id": "a", "animal_id": "A1", "breed": "Breed A", "location_lat": 30.1, "location_long": -97.1},
            {"id": "b", "_id": "b", "animal_id": "A2", "breed": "Breed B", "location_lat": 31.2, "location_long": -98.2},
        ]
        with patch.object(dashboard, "load_records", return_value=self.records), patch.object(dashboard, "logo_source", return_value="data:image/png;base64,"):
            app = dashboard.create_app()
        self.callbacks = {entry["callback"].__wrapped__.__name__: entry["callback"].__wrapped__ for entry in app.callback_map.values()}

    def test_reset_clears_category_column_filters_sort_page_and_selection(self):
        with patch.object(dashboard, "ctx", SimpleNamespace(triggered_id="reset-all")), patch.object(dashboard, "load_records", return_value=self.records) as load:
            values = self.callbacks["change_category"]("water", 1)
        load.assert_called_once_with("all")
        self.assertEqual(values[:6], (self.records, ["a"], [0], 0, "", []))
        self.assertEqual(values[-1], "all")
        self.assertEqual(values[-2], "")

    def test_category_change_replaces_records_and_resets_old_table_state(self):
        filtered = [self.records[1]]
        with patch.object(dashboard, "ctx", SimpleNamespace(triggered_id="rescue-filter")), patch.object(dashboard, "load_records", return_value=filtered) as load:
            values = self.callbacks["change_category"]("mountain", 0)
        load.assert_called_once_with("mountain")
        self.assertEqual(values[:6], (filtered, ["b"], [0], 0, "", []))
        self.assertEqual(values[-1], "mountain")

    def test_native_empty_filter_stays_empty_in_chart_map_and_count(self):
        chart, animal_map, count = self.callbacks["update_visuals"]([], ["a"], self.records, "")
        self.assertEqual(len(chart.data), 0)
        self.assertIn("No animals", animal_map.children[0].children)
        self.assertEqual(count, "0 shown / 2 in category")

    def test_initial_view_and_native_filtered_view_have_correct_chart_totals(self):
        chart, _, count = self.callbacks["update_visuals"](None, ["a"], self.records, "")
        self.assertEqual(sum(chart.data[0].values), 2)
        self.assertEqual(count, "2 shown / 2 in category")
        chart, animal_map, count = self.callbacks["update_visuals"]([self.records[1]], ["b"], self.records, "")
        self.assertEqual(sum(chart.data[0].values), 1)
        self.assertEqual(animal_map.children[1].center, [31.2, -98.2])
        self.assertEqual(count, "1 shown / 2 in category")


if __name__ == "__main__":
    unittest.main(verbosity=2)
