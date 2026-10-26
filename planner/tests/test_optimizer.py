from django.test import SimpleTestCase

from planner.optimizer import Candidate, NoFeasiblePlan, StartTank, plan_fuel

A = Candidate(mile=0.0, price=4.00, station="A")
B = Candidate(mile=300.0, price=3.00, station="B")
C = Candidate(mile=600.0, price=3.50, station="C")
D = Candidate(mile=900.0, price=5.00, station="D")


def bought(plan):
    return [(p.candidate.station, round(p.gallons, 6), round(p.cost, 6)) for p in plan.purchases]


class LongTripTests(SimpleTestCase):
    """1,000 miles, 500-mile range, 10 mpg: the tank holds 50 gallons."""

    def test_empty_tank_pays_for_every_gallon(self):
        plan = plan_fuel([A, B, C, D], trip_miles=1000, start_tank=StartTank.EMPTY)
        self.assertEqual(bought(plan), [("A", 30, 120), ("B", 50, 150), ("C", 20, 70)])
        self.assertAlmostEqual(plan.total_gallons, 100)
        self.assertAlmostEqual(plan.total_cost, 340)

    def test_full_tank_pays_only_for_fuel_bought_on_the_way(self):
        plan = plan_fuel([A, B, C, D], trip_miles=1000, start_tank=StartTank.FULL)
        self.assertEqual(bought(plan), [("B", 30, 90), ("C", 20, 70)])
        self.assertAlmostEqual(plan.total_gallons, 50)
        self.assertAlmostEqual(plan.total_cost, 160)

    def test_input_order_does_not_matter(self):
        plan = plan_fuel([D, B, A, C], trip_miles=1000)
        self.assertAlmostEqual(plan.total_cost, 340)


class ShortTripTests(SimpleTestCase):
    def test_empty_tank_buys_just_enough(self):
        b = Candidate(mile=200.0, price=3.00, station="B")
        plan = plan_fuel([A, b], trip_miles=300, start_tank=StartTank.EMPTY)
        self.assertEqual(bought(plan), [("A", 20, 80), ("B", 10, 30)])
        self.assertAlmostEqual(plan.total_cost, 110)

    def test_full_tank_needs_no_stop(self):
        b = Candidate(mile=200.0, price=3.00, station="B")
        plan = plan_fuel([A, b], trip_miles=300, start_tank=StartTank.FULL)
        self.assertEqual(plan.purchases, [])
        self.assertEqual(plan.total_cost, 0)

    def test_fuel_to_reach_the_first_station_is_paid_there(self):
        a = Candidate(mile=5.0, price=4.00, station="A")
        b = Candidate(mile=200.0, price=3.00, station="B")
        plan = plan_fuel([a, b], trip_miles=300, start_tank=StartTank.EMPTY)
        self.assertEqual(bought(plan), [("A", 20, 80), ("B", 10, 30)])
        self.assertAlmostEqual(plan.total_gallons, 30)

    def test_empty_tank_starts_at_the_cheapest_station_near_the_start(self):
        near_cheap = Candidate(mile=8.0, price=3.50, station="near cheap")
        plan = plan_fuel([A, near_cheap], trip_miles=100, start_tank=StartTank.EMPTY)
        self.assertEqual(bought(plan), [("near cheap", 10, 35)])


class ChoiceTests(SimpleTestCase):
    def test_fills_up_and_moves_to_the_cheapest_station_in_range(self):
        # No station in range is cheaper than A, so fill at A and go to B, the cheapest of the rest.
        a = Candidate(mile=0.0, price=3.00, station="A")
        b = Candidate(mile=400.0, price=3.20, station="B")
        c = Candidate(mile=450.0, price=3.90, station="C")
        plan = plan_fuel([a, b, c], trip_miles=800)
        self.assertEqual(bought(plan), [("A", 50, 150), ("B", 30, 96)])

    def test_equal_prices_prefer_the_farther_station(self):
        a = Candidate(mile=0.0, price=3.00, station="A")
        b = Candidate(mile=200.0, price=3.50, station="B")
        c = Candidate(mile=450.0, price=3.50, station="C")
        plan = plan_fuel([a, b, c], trip_miles=900)
        self.assertEqual(bought(plan), [("A", 50, 150), ("C", 40, 140)])


class InfeasibleTests(SimpleTestCase):
    def test_gap_longer_than_the_range(self):
        far = Candidate(mile=600.0, price=3.00, station="far")
        with self.assertRaisesMessage(NoFeasiblePlan, "mile 0"):
            plan_fuel([A, far], trip_miles=1000)

    def test_no_station_near_the_start_with_an_empty_tank(self):
        with self.assertRaisesMessage(NoFeasiblePlan, "within 10 miles of the start"):
            plan_fuel([B], trip_miles=400, start_tank=StartTank.EMPTY)
