from django.test import SimpleTestCase

from planner.geo import cumulative_miles, haversine_miles, sample_indices


class HaversineTests(SimpleTestCase):
    def test_one_degree_of_latitude(self):
        self.assertAlmostEqual(haversine_miles((0.0, 0.0), (1.0, 0.0)), 69.093, places=3)

    def test_same_point_is_zero(self):
        self.assertEqual(haversine_miles((41.88, -87.63), (41.88, -87.63)), 0.0)


class CumulativeMilesTests(SimpleTestCase):
    def test_running_total_along_a_meridian(self):
        miles = cumulative_miles([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)])
        self.assertEqual(len(miles), 3)
        self.assertEqual(miles[0], 0.0)
        self.assertAlmostEqual(miles[1], 69.093, places=3)
        self.assertAlmostEqual(miles[2], 138.187, places=3)


class SampleIndicesTests(SimpleTestCase):
    def test_keeps_first_last_and_one_point_per_spacing(self):
        cum = [0.0, 0.3, 0.6, 0.9, 1.2, 1.5, 1.8, 2.1, 2.4]
        self.assertEqual(sample_indices(cum, spacing=1.0), [0, 4, 8])

    def test_short_route_keeps_both_ends(self):
        self.assertEqual(sample_indices([0.0, 0.2], spacing=1.0), [0, 1])
