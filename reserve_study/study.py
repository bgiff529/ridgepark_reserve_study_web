from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from .models import Assumptions, Component, OptimizationResult, ReserveProjectionYear, ReserveStudyScenario, ScenarioPaths, StatementMetric
from .schedules import CollectionSchedule, ExpenditureSchedule
from .utils import months_between, normalize_to_month, shift_by_life


@dataclass(frozen=True)
class ReserveProjection:
    years: list[ReserveProjectionYear]

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([row.to_dict() for row in self.years])


@dataclass(frozen=True)
class StudyResult:
    scenario: ReserveStudyScenario
    components: list[Component]
    expenditure_schedule: ExpenditureSchedule
    collection_schedule: CollectionSchedule
    projection: ReserveProjection
    statement_metrics: list[StatementMetric]
    projection_years: int

    def component_details_df(self) -> pd.DataFrame:
        return pd.DataFrame([component.to_detail_row(self.scenario.assumptions) for component in self.components])

    def expenditures_detail_df(self) -> pd.DataFrame:
        return self.expenditure_schedule.detail_df()

    def expenditures_summary_df(self) -> pd.DataFrame:
        return self.expenditure_schedule.summary_df(self.projection_years)

    def expenditures_matrix_df(self) -> pd.DataFrame:
        return self.expenditure_schedule.matrix_df(self.projection_years)

    def reserve_projection_df(self) -> pd.DataFrame:
        return self.projection.to_dataframe()

    def statement_of_position_df(self) -> pd.DataFrame:
        return pd.DataFrame([{"Metric": metric.metric, "Value": metric.value} for metric in self.statement_metrics])

    def statement_of_position_formatted_df(self) -> pd.DataFrame:
        return pd.DataFrame([{"metric": metric.metric, "formatted": metric.formatted()} for metric in self.statement_metrics])

    def write_outputs(self) -> Path:
        from .repository import ScenarioRepository

        ScenarioRepository().write_study_results(self)
        return self.scenario.paths.output_root

    def write_optimization_result(self, optimization_result: OptimizationResult) -> Path:
        from .repository import ScenarioRepository

        ScenarioRepository().write_optimization_results(self.scenario.paths, optimization_result)
        return self.scenario.paths.output_root

    def build_plots(self, output_dir: Path | None = None) -> list[Path]:
        from .plotting import PlotBuilder

        return PlotBuilder(self).build_all(output_dir=output_dir)

    def build_report(self, compile_pdf: bool = False):
        from .reporting import ReportBuilder

        builder = ReportBuilder(self)
        tex_path = builder.build_tex()
        if compile_pdf:
            return builder.build_pdf(tex_path)
        return tex_path


class FundedBalanceCalculator:
    VALID_METHODS = {
        "current_cost_straight_line",
        "future_cost_straight_line",
        "future_cost_time_valued",
    }

    @classmethod
    def calculate(
        cls,
        expenditure_schedule: ExpenditureSchedule,
        assumptions: Assumptions,
        projection_years: int = 30,
        method: str = "current_cost_straight_line",
        funded_date: str = "analysis",
        custom_month: int = 1,
        custom_day: int = 1,
        respect_one_time: bool = True,
        inflate_result: bool = False,
    ) -> pd.Series:
        if method not in cls.VALID_METHODS:
            raise ValueError(f"method must be one of {sorted(cls.VALID_METHODS)}")

        analysis_date = normalize_to_month(assumptions.analysis_date)
        inflation = float(assumptions.inflation)
        investment = float(assumptions.investment)
        years = [analysis_date.year + i for i in range(projection_years + 1)]
        funded_balances: list[float] = []

        for year in years:
            if funded_date == "analysis":
                as_of_date = pd.Timestamp(year=year, month=analysis_date.month, day=analysis_date.day)
            elif funded_date == "beginning":
                as_of_date = pd.Timestamp(year=year, month=1, day=1)
            elif funded_date == "end":
                as_of_date = pd.Timestamp(year=year + 1, month=1, day=1)
            elif funded_date == "custom":
                as_of_date = pd.Timestamp(year=year, month=custom_month, day=custom_day)
            else:
                raise ValueError("funded_date must be one of: analysis, beginning, end, custom")

            as_of_date = normalize_to_month(as_of_date)
            total = 0.0

            for component in expenditure_schedule.components:
                life_months = component.life_months
                next_service_date = component.replacement_date(analysis_date)
                if pd.isna(life_months) or pd.isna(next_service_date):
                    continue

                one_time_mode = respect_one_time and component.is_one_time
                if next_service_date >= as_of_date:
                    future_cost = component.future_cost(analysis_date, inflation)
                else:
                    if one_time_mode:
                        continue
                    next_service_date = pd.Timestamp(next_service_date)
                    while next_service_date < as_of_date:
                        next_service_date = shift_by_life(next_service_date, life_months, direction=1)
                    months_to_next = months_between(analysis_date, next_service_date)
                    future_cost = component.current_cost * (1 + inflation) ** (months_to_next / 12)

                service_date = shift_by_life(next_service_date, life_months, direction=-1)
                age_months = months_between(service_date, as_of_date)
                age_months = max(0, min(age_months, int(life_months)))

                if method == "current_cost_straight_line":
                    funded_value = component.current_cost * (age_months / life_months)
                elif method == "future_cost_straight_line":
                    funded_value = future_cost * (age_months / life_months)
                else:
                    age_years = age_months / 12
                    life_years = life_months / 12
                    if investment == 0:
                        funded_fraction = age_months / life_months
                    else:
                        funded_fraction = (((1 + investment) ** age_years) - 1) / (((1 + investment) ** life_years) - 1)
                    funded_value = future_cost * funded_fraction

                total += funded_value

            if inflate_result:
                inflation_months = months_between(analysis_date, as_of_date)
                total = total * (1 + inflation) ** (inflation_months / 12)
            funded_balances.append(round(total, 2))

        return pd.Series(funded_balances, index=years, name="funded_balance")


class ProjectionEngine:
    @staticmethod
    def project(
        expenditure_schedule: ExpenditureSchedule,
        collection_schedule: CollectionSchedule,
        assumptions: Assumptions,
        start_year: int | None = None,
        projection_years: int = 30,
        starting_balance: float | None = None,
    ) -> ReserveProjection:
        annual_rate = float(assumptions.investment)
        monthly_rate = annual_rate / 12.0
        if start_year is None:
            start_year = assumptions.analysis_year

        current_balance = float(assumptions.begin_balance if starting_balance is None else starting_balance)
        end_year = start_year + projection_years - 1
        contribution_map, special_map = collection_schedule.annual_maps()
        monthly_exp_map = expenditure_schedule.monthly_amounts()

        rows: list[ReserveProjectionYear] = []
        for year in range(start_year, end_year + 1):
            begin_balance = current_balance
            annual_contribution = float(contribution_map.get(year, 0.0))
            annual_special = float(special_map.get(year, 0.0))
            monthly_contribution = annual_contribution / 12.0
            year_expenditures = 0.0
            year_interest = 0.0

            for month in range(1, 13):
                current_balance += monthly_contribution

                interest = current_balance * monthly_rate
                current_balance += interest
                year_interest += interest

                expenditures = float(monthly_exp_map.get((year, month), 0.0))
                if expenditures:
                    current_balance -= expenditures
                    year_expenditures += expenditures

                if month == 1 and annual_special:
                    current_balance += annual_special

            rows.append(
                ReserveProjectionYear(
                    year=year,
                    begin_balance=round(begin_balance, 2),
                    contribution=round(annual_contribution, 2),
                    special_assessment=round(annual_special, 2),
                    expenditures=round(year_expenditures, 2),
                    interest=round(year_interest, 2),
                    end_balance=round(current_balance, 2),
                )
            )

        return ReserveProjection(rows)


class ReserveStudy:
    def __init__(self, scenario: ReserveStudyScenario):
        self.scenario = scenario

    @classmethod
    def from_variant(
        cls,
        variant_name: str,
        scenario_root: Path | str | None = None,
        output_root: Path | str | None = None,
        assets_root: Path | str | None = None,
    ) -> "ReserveStudy":
        from .repository import ScenarioRepository

        paths = ScenarioPaths.for_variant(scenario_root, variant_name, output_root=output_root, assets_root=assets_root)
        return cls(ScenarioRepository().load(paths))

    @classmethod
    def from_directory(
        cls,
        scenario_dir: Path | str,
        output_root: Path | str | None = None,
        assets_root: Path | str | None = None,
    ) -> "ReserveStudy":
        path = Path(scenario_dir).expanduser()
        if (path / "source_data").exists():
            resolved = path.resolve()
            return cls.from_variant(resolved.name, scenario_root=resolved.parent, output_root=output_root, assets_root=assets_root)
        return cls.from_variant(str(scenario_dir), output_root=output_root, assets_root=assets_root)

    @classmethod
    def run_scenario(
        cls,
        scenario_dir: Path | str,
        projection_years: int = 30,
        output_root: Path | str | None = None,
        assets_root: Path | str | None = None,
    ) -> StudyResult:
        return cls.from_directory(scenario_dir, output_root=output_root, assets_root=assets_root).run(projection_years=projection_years)

    def run(self, projection_years: int = 30, extend_for_next_instance: bool = True) -> StudyResult:
        assumptions = self.scenario.assumptions
        analysis_year = assumptions.analysis_year
        components = [replace(component, component_id=index) for index, component in enumerate(self.scenario.components)]
        collection_schedule = self.scenario.collection_schedule
        expenditure_schedule = ExpenditureSchedule.from_components(
            components=components,
            assumptions=assumptions,
            projection_years=projection_years,
            extend_for_next_instance=extend_for_next_instance,
        )

        projection = ProjectionEngine.project(
            expenditure_schedule=expenditure_schedule,
            collection_schedule=collection_schedule,
            assumptions=assumptions,
            start_year=analysis_year,
            projection_years=projection_years,
        )

        funded_end = FundedBalanceCalculator.calculate(
            expenditure_schedule=expenditure_schedule,
            assumptions=assumptions,
            projection_years=projection_years,
            method="current_cost_straight_line",
            funded_date="end",
            respect_one_time=True,
            inflate_result=True,
        )
        for row in projection.years:
            funded_balance = float(funded_end.loc[row.year]) if row.year in funded_end.index else np.nan
            row.funded_balance = funded_balance
            row.percent_funded = round(row.end_balance / funded_balance * 100, 2) if funded_balance > 0 else np.nan

        statement_funded_balance = FundedBalanceCalculator.calculate(
            expenditure_schedule=expenditure_schedule,
            assumptions=assumptions,
            projection_years=projection_years,
            method="current_cost_straight_line",
            funded_date="analysis",
            respect_one_time=True,
            inflate_result=False,
        )
        statement_metrics = self._build_statement_metrics(
            components=components,
            collection_schedule=collection_schedule,
            assumptions=assumptions,
            statement_funded_amount=float(statement_funded_balance.loc[analysis_year]),
        )

        return StudyResult(
            scenario=self.scenario,
            components=components,
            expenditure_schedule=expenditure_schedule,
            collection_schedule=collection_schedule,
            projection=projection,
            statement_metrics=statement_metrics,
            projection_years=projection_years,
        )

    def _build_statement_metrics(
        self,
        components: list[Component],
        collection_schedule: CollectionSchedule,
        assumptions: Assumptions,
        statement_funded_amount: float,
    ) -> list[StatementMetric]:
        analysis_year = assumptions.analysis_year
        current_replacement_cost = float(sum(component.current_cost for component in components))
        future_replacement_cost = float(np.nansum([component.future_cost(assumptions.analysis_date, assumptions.inflation) for component in components]))
        projected_balance_reserves = float(assumptions.begin_balance)
        percent_funded = projected_balance_reserves / statement_funded_amount * 100 if statement_funded_amount else np.nan

        units_raw = self.scenario.association_properties.get("NUM_UNITS", "138")
        try:
            units = int(float(str(units_raw).replace(",", "")))
        except Exception:
            units = 138

        reserve_deficit = statement_funded_amount - projected_balance_reserves
        reserve_deficit_per_unit = reserve_deficit / units if units else np.nan
        first_year_collection = collection_schedule.annual_for_year(analysis_year)
        annual_contribution = float(first_year_collection.contribution)
        special_assessment = float(first_year_collection.special_assessment)
        projected_reserve_contribution = annual_contribution + special_assessment
        average_annual_per_unit = annual_contribution / units if units else np.nan
        monthly_contribution = annual_contribution / 12.0
        average_monthly_per_unit = monthly_contribution / units if units else np.nan

        return [
            StatementMetric("Current Replacement Cost", current_replacement_cost),
            StatementMetric("Future Replacement Cost", future_replacement_cost),
            StatementMetric("Current Reserve Fund Balance", projected_balance_reserves),
            StatementMetric("Fully Funded Reserve Balance", statement_funded_amount),
            StatementMetric("Percent Funded", percent_funded),
            StatementMetric("Reserve Deficit", reserve_deficit),
            StatementMetric("Reserve Deficit per Unit", reserve_deficit_per_unit),
            StatementMetric("Projected Annual Reserve Contribution", projected_reserve_contribution),
            StatementMetric("Average Annual Reserve Contribution per Unit", average_annual_per_unit),
            StatementMetric("Projected Monthly Reserve Contribution", monthly_contribution),
            StatementMetric("Average Monthly Reserve Contribution per Unit", average_monthly_per_unit),
        ]
