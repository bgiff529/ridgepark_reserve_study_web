import unittest

import pandas as pd

from reserve_study import Assumptions, Component, ExpenditureSchedule


class ComponentTests(unittest.TestCase):
    def test_component_cost_and_life_properties(self):
        component = Component(
            category="Roofs",
            subcategory="Main",
            component="Asphalt Roof",
            tracking="Reserve",
            method="fixed",
            cost=100.0,
            cost_units="sf",
            quantity=50,
            quantity_units="sf",
            life_years=10,
            remaining_life="2:06",
        )
        self.assertEqual(component.current_cost, 5000.0)
        self.assertEqual(component.life_months, 120)
        self.assertEqual(component.remaining_life_months, 30)

    def test_component_generates_fixed_schedule(self):
        assumptions = Assumptions(
            analysis_date=pd.Timestamp("2026-01-01"),
            inflation=0.03,
            investment=0.02,
            contribution_factor=1.0,
            begin_balance=1000.0,
        )
        component = Component(
            category="Paint",
            subcategory="Entry",
            component="Exterior Paint",
            tracking="Reserve",
            method="Fixed",
            cost=1000,
            cost_units="ea",
            quantity=1,
            quantity_units="ea",
            life_years=5,
            remaining_life="1:00",
            component_id=1,
        )
        schedule = ExpenditureSchedule.from_components([component], assumptions, projection_years=10)
        events = schedule.events
        self.assertGreaterEqual(len(events), 3)
        self.assertEqual(events[0].date, pd.Timestamp("2027-01-01"))
        self.assertEqual(events[1].date, pd.Timestamp("2032-01-01"))

    def test_one_time_component_only_generates_once(self):
        assumptions = Assumptions(
            analysis_date=pd.Timestamp("2026-01-01"),
            inflation=0.03,
            investment=0.02,
            contribution_factor=1.0,
            begin_balance=1000.0,
        )
        component = Component(
            category="Gate",
            subcategory="Entry",
            component="New Gate",
            tracking="Reserve",
            method="One Time",
            cost=5000,
            cost_units="ea",
            quantity=1,
            quantity_units="ea",
            life_years=20,
            remaining_life="1:00",
            component_id=2,
        )
        schedule = ExpenditureSchedule.from_components([component], assumptions, projection_years=30)
        self.assertEqual(len(schedule.events), 1)


if __name__ == "__main__":
    unittest.main()
