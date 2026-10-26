from django.test import SimpleTestCase

from planner.management.commands.build_places import clean_place_names
from planner.places import LocationError, place_key, resolve_location


class PlaceKeyTests(SimpleTestCase):
    def test_saint_and_st_match(self):
        self.assertEqual(place_key("St. Louis"), "st louis")
        self.assertEqual(place_key("SAINT LOUIS"), "st louis")

    def test_fort_and_mount_are_shortened(self):
        self.assertEqual(place_key("Fort Worth"), "ft worth")
        self.assertEqual(place_key("FT. WORTH"), "ft worth")
        self.assertEqual(place_key("Mount Vernon"), "mt vernon")

    def test_punctuation_and_spacing(self):
        self.assertEqual(place_key("  Coeur d'Alene "), "coeur dalene")
        self.assertEqual(place_key("Winston-Salem"), "winston salem")


class CleanPlaceNamesTests(SimpleTestCase):
    def test_strips_the_census_suffix(self):
        self.assertEqual(clean_place_names("Abbeville city", "25"), ["Abbeville"])
        self.assertEqual(clean_place_names("Abanda CDP", "57"), ["Abanda"])
        self.assertEqual(clean_place_names("Juneau city and borough", "00"), ["Juneau"])

    def test_balance_and_consolidated_names_get_a_short_alias(self):
        self.assertEqual(clean_place_names("Indianapolis city (balance)", "00"), ["Indianapolis"])
        self.assertEqual(
            clean_place_names("Nashville-Davidson metropolitan government (balance)", "MG"),
            ["Nashville-Davidson", "Nashville"],
        )

    def test_alternate_name_in_parentheses(self):
        self.assertEqual(
            clean_place_names("San Buenaventura (Ventura) city", "25"),
            ["San Buenaventura", "Ventura"],
        )

    def test_hyphenated_city_is_kept_whole(self):
        self.assertEqual(clean_place_names("Winston-Salem city", "25"), ["Winston-Salem"])


class ResolveLocationTests(SimpleTestCase):
    def test_city_and_state_code(self):
        location = resolve_location("Chicago, IL")
        self.assertEqual(location.label, "Chicago, IL")
        self.assertAlmostEqual(location.lat, 41.837, places=2)
        self.assertAlmostEqual(location.lon, -87.685, places=2)

    def test_city_and_full_state_name(self):
        self.assertEqual(resolve_location("chicago, illinois"), resolve_location("Chicago, IL"))

    def test_coordinates(self):
        location = resolve_location("41.8781, -87.6298")
        self.assertEqual((location.lat, location.lon), (41.8781, -87.6298))

    def test_unknown_city(self):
        with self.assertRaisesMessage(LocationError, "Atlantis, IL"):
            resolve_location("Atlantis, IL")

    def test_unknown_state(self):
        with self.assertRaises(LocationError):
            resolve_location("Paris, France")

    def test_coordinates_outside_the_usa(self):
        with self.assertRaises(LocationError):
            resolve_location("48.8566, 2.3522")

    def test_missing_state(self):
        with self.assertRaises(LocationError):
            resolve_location("Chicago")
