import unittest
from pathlib import Path

import pandas as pd

from reserve_study import ReportBuilder, ReserveStudy


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def test_can_read_local_scenario_and_match_projection(self):
        output_root = Path("/tmp/ridge_park_oo_test") / "2026_brendan_plan"
        study = ReserveStudy.from_directory(project_root() / "2026_brendan_plan", output_root=output_root)
        results = study.run(projection_years=30)
        results.write_outputs()

        legacy_root = project_root().parent / "Ridge Park Reserve Study"
        self.assertTrue(legacy_root.exists())
        legacy_projection = pd.read_csv(legacy_root / "2026_brendan_plan" / "working_csv" / "reserve_projection.csv")
        new_projection = results.reserve_projection_df()

        self.assertEqual(len(new_projection), len(legacy_projection))
        pd.testing.assert_series_equal(new_projection["year"], legacy_projection["year"], check_names=False)
        for column in ["contribution", "special_assessment", "expenditures", "interest"]:
            diff = (new_projection[column] - legacy_projection[column]).abs().max()
            self.assertLess(diff, 0.05)

    def test_report_builder_renders_tex_without_placeholders(self):
        output_root = Path("/tmp/ridge_park_oo_report_test") / "2026_brendan_plan"
        study = ReserveStudy.from_directory(project_root() / "2026_brendan_plan", output_root=output_root)
        results = study.run(projection_years=30)
        results.write_outputs()

        tex_path = results.build_report()
        contents = tex_path.read_text(encoding="utf-8")

        self.assertTrue(tex_path.exists())
        self.assertNotIn("{{REPORT_TITLE}}", contents)
        self.assertIn("Reserve Management Plan", contents)
        self.assertIn("Ridge Park", contents)

    def test_report_builder_compiles_pdf_when_tex_is_available(self):
        if ReportBuilder.find_pdf_compiler() is None:
            self.skipTest("latexmk/pdflatex is not available")

        output_root = Path("/tmp/ridge_park_oo_pdf_test") / "2026_brendan_plan"
        study = ReserveStudy.from_directory(project_root() / "2026_brendan_plan", output_root=output_root)
        results = study.run(projection_years=30)
        results.write_outputs()

        pdf_path = results.build_report(compile_pdf=True)

        self.assertTrue(pdf_path.exists())

    def test_plot_builder_writes_plots(self):
        output_root = Path("/tmp/ridge_park_oo_plot_test") / "2026_brendan_plan"
        study = ReserveStudy.from_directory(project_root() / "2026_brendan_plan", output_root=output_root)
        results = study.run(projection_years=30)
        plot_paths = results.build_plots()

        self.assertGreaterEqual(len(plot_paths), 4)
        for plot_path in plot_paths:
            self.assertTrue(plot_path.exists())


if __name__ == "__main__":
    unittest.main()
