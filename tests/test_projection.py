import unittest

import pandas as pd

from reserve_study import AnnualCollection, Assumptions, CollectionSchedule, Component, ExpenditureSchedule, FundedBalanceCalculator, ProjectionEngine


class ProjectionTests(unittest.TestCase):
    def test_projection_engine_uses_monthly_cash_flow_order(self):
        assumptions = Assumptions(
            analysis_date=pd.Timestamp("2026-01-01"),
            inflation=0.0,
            investment=0.12,
            contribution_factor=1.0,
            begin_balance=1200.0,
        )
        component = Component(
            category="Fence",
            subcategory="Perimeter",
            component="Fence Repair",
            tracking="Reserve",
            method="One Time",
            cost=1200.0,
            cost_units="ea",
            quantity=1,
            quantity_units="ea",
            life_years=1,
            remaining_life="0:01",
            component_id=0,
        )
        expenditure_schedule = ExpenditureSchedule.from_components([component], assumptions, projection_years=1, extend_for_next_instance=False)
        collection_schedule = CollectionSchedule.from_rows([AnnualCollection(year=2026, contribution=1200.0, special_assessment=2400.0)])
        projection = ProjectionEngine.project(
            expenditure_schedule=expenditure_schedule,
            collection_schedule=collection_schedule,
            assumptions=assumptions,
            start_year=2026,
            projection_years=1,
        )
        row = projection.years[0]
        self.assertEqual(row.begin_balance, 1200.0)
        self.assertEqual(row.special_assessment, 2400.0)
        self.assertEqual(row.expenditures, expenditure_schedule.events[0].amount)
        self.assertGreater(row.end_balance, 0)

    def test_funded_balance_respects_one_time_components(self):
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
        expenditure_schedule = ExpenditureSchedule.from_components([component], assumptions, projection_years=5)
        funded = FundedBalanceCalculator.calculate(expenditure_schedule, assumptions, projection_years=5, funded_date="end", respect_one_time=True)
        self.assertGreaterEqual(funded.loc[2026], 0)
        self.assertEqual(funded.loc[2031], 0)


if __name__ == "__main__":
    unittest.main()
