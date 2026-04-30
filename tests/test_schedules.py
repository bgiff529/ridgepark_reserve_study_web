import unittest

import pandas as pd

from reserve_study import AnnualCollection, Assumptions, CollectionSchedule, Component, ExpenditureSchedule, ReportBuilder


class ScheduleTests(unittest.TestCase):
    def test_expenditure_schedule_generates_dated_cashflows(self):
        assumptions = Assumptions(
            analysis_date=pd.Timestamp("2030-01-01"),
            inflation=0.0,
            investment=0.02,
            contribution_factor=1.0,
            begin_balance=1000.0,
        )
        component = Component(
            category="Roof",
            subcategory="Main",
            component="Roof Replacement",
            tracking="Reserve",
            method="Fixed",
            cost=10000,
            cost_units="allow",
            quantity=1,
            quantity_units="allow",
            life_years=3,
            remaining_life="1:00",
            component_id=0,
        )

        schedule = ExpenditureSchedule.from_components([component], assumptions, projection_years=6)

        self.assertEqual(schedule.events[0].event_type, "expenditure")
        self.assertEqual(schedule.events[0].date, pd.Timestamp("2031-01-01"))
        self.assertEqual(schedule.events[1].date, pd.Timestamp("2034-01-01"))

    def test_collection_schedule_generates_monthly_and_special_cashflows(self):
        schedule = CollectionSchedule.from_rows([AnnualCollection(year=2030, contribution=1200.0, special_assessment=2400.0)])

        events = schedule.dated_events(start_year=2030, projection_years=1)
        contributions = [event for event in events if event.event_type == "contribution"]
        specials = [event for event in events if event.event_type == "special_assessment"]

        self.assertEqual(len(contributions), 12)
        self.assertEqual(contributions[0].amount, 100.0)
        self.assertEqual(len(specials), 1)
        self.assertEqual(specials[0].date, pd.Timestamp("2030-01-01"))

    def test_pdf_compiler_discovery_reports_missing_tex(self):
        compiler = ReportBuilder.find_pdf_compiler(
            path="/definitely/not/a/real/path",
            mactex_bin="/definitely/not/a/real/texbin",
            include_tinytex=False,
        )

        self.assertIsNone(compiler)


if __name__ == "__main__":
    unittest.main()
