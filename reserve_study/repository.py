from __future__ import annotations

from pathlib import Path
import shutil

import pandas as pd

from .models import Assumptions, Component, OptimizationResult, ReserveStudyScenario, ScenarioPaths
from .schedules import CollectionSchedule
from .study import StudyResult


class ScenarioRepository:
    def load(self, paths: ScenarioPaths) -> ReserveStudyScenario:
        assumptions_df = pd.read_csv(paths.source_data_dir / "assumptions.csv")
        assumptions_map = dict(zip(assumptions_df["Parameter"], assumptions_df["Value"]))
        assumptions = Assumptions.from_mapping(assumptions_map)

        component_df = pd.read_csv(paths.source_data_dir / "component_list_v2.csv").copy()
        if "source_page" not in component_df.columns:
            component_df["source_page"] = ""
        components = [
            Component(
                category=row["category"],
                subcategory=row["subcategory"],
                component=row["component"],
                tracking=row["tracking"],
                method=row["method"],
                cost=row["cost"],
                cost_units=row["cost_units"],
                quantity=row["quantity"],
                quantity_units=row["quantity_units"],
                life_years=row["life_years"],
                remaining_life=row["remaining_life"],
                service_date=row.get("service_date"),
                source_page=row.get("source_page", ""),
            )
            for _, row in component_df.iterrows()
        ]

        contribution_df = pd.read_csv(paths.source_data_dir / "assessment_contributions.csv").copy()
        collection_schedule = CollectionSchedule.from_dataframe(contribution_df)

        association_properties = self._load_key_value_csv(paths.assets_root / "association_properties.csv")
        cover_letter = self._read_text(paths.report_sources_dir / "cover_letter.txt")
        preparer_report = self._read_text(paths.report_sources_dir / "preparer_report.txt")

        return ReserveStudyScenario(
            paths=paths,
            assumptions=assumptions,
            components=components,
            collection_schedule=collection_schedule,
            association_properties=association_properties,
            cover_letter=cover_letter,
            preparer_report=preparer_report,
        )

    def write_study_results(self, results: StudyResult) -> None:
        paths = results.scenario.paths
        paths.ensure_output_dirs()
        self.copy_source_data(paths)
        results.component_details_df().to_csv(paths.working_csv_dir / "component_list_detail.csv", index=False)
        results.expenditures_detail_df().to_csv(paths.working_csv_dir / "expenditures_by_year_detail.csv", index=False)
        results.expenditures_summary_df().to_csv(paths.working_csv_dir / "expenditures_by_year_summary.csv", index=False)
        results.expenditures_matrix_df().to_csv(paths.working_csv_dir / "expenditures_matrix.csv")
        results.reserve_projection_df().to_csv(paths.working_csv_dir / "reserve_projection.csv", index=False)
        results.statement_of_position_df().to_csv(paths.working_csv_dir / "statement_of_position.csv", index=False)
        results.statement_of_position_formatted_df().to_csv(paths.working_csv_dir / "statement_of_position_formatted.csv", index=False)

    def write_optimization_results(self, paths: ScenarioPaths, result: OptimizationResult) -> None:
        paths.ensure_output_dirs()
        self.copy_source_data(paths)
        result.assessments_df().rename(columns={"contribution": "annual_contribution"}).to_csv(
            paths.output_source_data_dir / "optimized_assessment_contributions.csv", index=False
        )
        result.projection_df().to_csv(paths.working_csv_dir / "optimized_reserve_projection.csv", index=False)

    def copy_source_data(self, paths: ScenarioPaths) -> None:
        if not paths.source_data_dir.exists():
            return
        paths.output_source_data_dir.mkdir(parents=True, exist_ok=True)
        for source_path in paths.source_data_dir.rglob("*"):
            relative_path = source_path.relative_to(paths.source_data_dir)
            target_path = paths.output_source_data_dir / relative_path
            if source_path.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)

    def _load_key_value_csv(self, path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        df = pd.read_csv(path)
        key_col = df.columns[0]
        val_col = df.columns[1]
        return {str(key).strip(): str(value).strip() for key, value in zip(df[key_col], df[val_col])}

    def _read_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")
