from django.test import SimpleTestCase

from planner.optimizer import Candidate, NoFeasiblePlan, StartTank, Strategy, plan_with_strategy


def bought(plan):
    return [(p.candidate.station, round(p.gallons, 6), round(p.cost, 6)) for p in plan.purchases]


class RisingPricesTests(SimpleTestCase):
    """Prices rise along a 1,200-mile trip, so the cheapest plan tops up at C for 2 gallons."""

    stations = [
        Candidate(mile=0.0, price=3.00, station="A"),
        Candidate(mile=400.0, price=3.10, station="B"),
        Candidate(mile=420.0, price=3.20, station="C"),
        Candidate(mile=820.0, price=3.30, station="D"),
    ]

    def plan(self, strategy):
        return plan_with_strategy(self.stations, 1200, strategy=strategy)

    def test_cheapest_makes_the_small_top_up(self):
        plan = self.plan(Strategy.CHEAPEST)
        self.assertEqual(
            bought(plan), [("A", 50, 150), ("B", 40, 124), ("C", 2, 6.4), ("D", 28, 92.4)]
        )
        self.assertAlmostEqual(plan.total_cost, 372.8)

    def test_fewest_stops_skips_it_for_20_cents(self):
        plan = self.plan(Strategy.FEWEST_STOPS)
        self.assertEqual(bought(plan), [("A", 50, 150), ("B", 40, 124), ("D", 30, 99)])
        self.assertAlmostEqual(plan.total_cost, 373.0)


class ExpensiveShortcutTests(SimpleTestCase):
    """X allows a 2-stop plan but costs $5.00. Y and Z cost $3.00 and need one more stop."""

    stations = [
        Candidate(mile=0.0, price=3.00, station="A"),
        Candidate(mile=300.0, price=3.00, station="Y"),
        Candidate(mile=500.0, price=5.00, station="X"),
        Candidate(mile=700.0, price=3.00, station="Z"),
    ]

    def plan(self, strategy, start_tank=StartTank.EMPTY):
        return plan_with_strategy(self.stations, 1000, strategy=strategy, start_tank=start_tank)

    def test_fewest_stops_pays_for_the_shortcut(self):
        plan = self.plan(Strategy.FEWEST_STOPS)
        self.assertEqual(bought(plan), [("A", 50, 150), ("X", 50, 250)])

    def test_balanced_takes_one_more_stop_to_save_100_dollars(self):
        plan = self.plan(Strategy.BALANCED)
        self.assertEqual(bought(plan), [("A", 50, 150), ("Y", 30, 90), ("Z", 20, 60)])
        self.assertAlmostEqual(plan.total_cost, 300)

    def test_full_tank_fewest_stops(self):
        plan = self.plan(Strategy.FEWEST_STOPS, StartTank.FULL)
        self.assertEqual(bought(plan), [("X", 50, 250)])

    def test_full_tank_balanced(self):
        plan = self.plan(Strategy.BALANCED, StartTank.FULL)
        self.assertEqual(bought(plan), [("Y", 30, 90), ("Z", 20, 60)])


class NeverWorseThanCheapestTests(SimpleTestCase):
    """Cases where the stop search alone picks a worse plan than the exact cheapest one."""

    def test_fewest_stops_takes_the_cheaper_plan_with_the_same_stop_count(self):
        # The search prefers A+Y ($200). A+X also needs 2 stops and costs $185.
        stations = [
            Candidate(mile=0.0, price=3.00, station="A"),
            Candidate(mile=100.0, price=3.50, station="X"),
            Candidate(mile=500.0, price=5.00, station="Y"),
        ]
        plan = plan_with_strategy(stations, 600, strategy=Strategy.FEWEST_STOPS)
        self.assertEqual(bought(plan), [("A", 50, 150), ("X", 10, 35)])

    def test_balanced_takes_the_cheapest_plan_when_it_scores_better(self):
        # The search picks Z alone: $200 + $5 = 205. Y+Z costs $160 + $10 = 170.
        stations = [
            Candidate(mile=400.0, price=3.00, station="Y"),
            Candidate(mile=500.0, price=4.00, station="Z"),
        ]
        plan = plan_with_strategy(
            stations, 1000, strategy=Strategy.BALANCED, start_tank=StartTank.FULL
        )
        self.assertEqual(bought(plan), [("Y", 40, 120), ("Z", 10, 40)])


class EdgeTests(SimpleTestCase):
    def test_station_at_the_finish_mile(self):
        stations = [Candidate(mile=8.0, price=3.00, station="A")]
        for strategy in Strategy:
            plan = plan_with_strategy(stations, 8, strategy=strategy)
            self.assertEqual(bought(plan), [("A", 0.8, 2.4)], strategy)

    def test_short_full_tank_trip_needs_no_stop_in_any_strategy(self):
        stations = [Candidate(mile=100.0, price=3.0, station="A")]
        for strategy in Strategy:
            plan = plan_with_strategy(stations, 300, strategy=strategy, start_tank=StartTank.FULL)
            self.assertEqual(plan.purchases, [], strategy)

    def test_gap_longer_than_the_range(self):
        stations = [Candidate(0.0, 3.0, "A"), Candidate(600.0, 3.0, "B")]
        for strategy in (Strategy.BALANCED, Strategy.FEWEST_STOPS):
            with self.assertRaises(NoFeasiblePlan):
                plan_with_strategy(stations, 1000, strategy=strategy)
