from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .models import AnnualCollection, Assumptions, CashflowEvent, Component
from .utils import add_months, months_between, shift_by_life


@dataclass(frozen=True)
class ExpenditureSchedule:
    components: list[Component]
    events: list[CashflowEvent]

    @classmethod
    def from_components(
        cls,
        components: list[Component],
        assumptions: Assumptions,
        projection_years: int = 30,
        extend_for_next_instance: bool = True,
    ) -> "ExpenditureSchedule":
        events: list[CashflowEvent] = []
        analysis_date = assumptions.analysis_date
        inflation = assumptions.inflation

        for component in components:
            life_months = component.life_months
            replacement_date = component.replacement_date(analysis_date)
            if pd.isna(life_months) or pd.isna(replacement_date):
                continue

            projection_months = projection_years * 12
            if extend_for_next_instance:
                projection_months += int(life_months)
            projection_end = add_months(analysis_date, projection_months)

            occurrence = 1
            next_date = pd.Timestamp(replacement_date)
            while next_date <= projection_end:
                months_from_analysis = months_between(analysis_date, next_date)
                future_cost = round(component.current_cost * (1 + inflation) ** (months_from_analysis / 12), 2)
                events.append(
                    CashflowEvent(
                        date=next_date,
                        amount=future_cost,
                        event_type="expenditure",
                        component_id=int(component.component_id or 0),
                        occurrence=occurrence,
                        category=component.category,
                        subcategory=component.subcategory,
                        component=component.component,
                        tracking=component.tracking,
                        method=component.normalized_method,
                        life_years=component.life_years,
                        life_months=int(life_months),
                        current_cost=round(component.current_cost, 2),
                        source_page=component.source_page,
                    )
                )
                if component.is_one_time:
                    break
                next_date = shift_by_life(next_date, life_months, direction=1)
                occurrence += 1

        events.sort(key=lambda event: (event.component_id or 0, event.date, event.occurrence or 0))
        return cls(components=components, events=events)

    def events_through_projection(self, projection_years: int) -> list[CashflowEvent]:
        if not self.events:
            return []
        first_year = min(event.year for event in self.events)
        max_year = first_year + projection_years - 1
        return [event for event in self.events if event.year <= max_year]

    def monthly_amounts(self) -> dict[tuple[int, int], float]:
        amounts: dict[tuple[int, int], float] = {}
        for event in self.events:
            key = (event.year, event.month)
            amounts[key] = amounts.get(key, 0.0) + float(event.amount)
        return amounts

    def detail_df(self) -> pd.DataFrame:
        df = pd.DataFrame([event.to_expenditure_row() for event in self.events])
        if df.empty:
            return df
        return df.sort_values(["component_id", "replacement_date", "occurrence"]).reset_index(drop=True)

    def summary_df(self, projection_years: int = 30) -> pd.DataFrame:
        detail = self.detail_df()
        if detail.empty:
            return pd.DataFrame(columns=["replacement_year", "expenditures", "component_count"])
        first_year = int(detail["replacement_year"].min())
        max_year = first_year + projection_years - 1
        out = (
            detail.loc[detail["replacement_year"] <= max_year]
            .groupby("replacement_year", as_index=False)
            .agg(expenditures=("future_cost", "sum"), component_count=("component", "count"))
            .sort_values("replacement_year")
            .reset_index(drop=True)
        )
        out["expenditures"] = out["expenditures"].round(2)
        return out

    def matrix_df(self, projection_years: int = 30) -> pd.DataFrame:
        detail = self.detail_df()
        if detail.empty:
            return pd.DataFrame()
        first_year = int(detail["replacement_year"].min())
        max_year = first_year + projection_years - 1
        out = (
            detail.loc[detail["replacement_year"] <= max_year]
            .pivot_table(index="category", columns="replacement_year", values="future_cost", aggfunc="sum", fill_value=0.0)
            .sort_index()
        )
        return out.round(2)


@dataclass(frozen=True)
class CollectionSchedule:
    annual_collections: list[AnnualCollection]

    @classmethod
    def from_rows(cls, rows: list[AnnualCollection]) -> "CollectionSchedule":
        return cls(annual_collections=sorted(rows, key=lambda row: row.year))

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> "CollectionSchedule":
        rows = []
        for _, row in df.iterrows():
            rows.append(
                AnnualCollection(
                    year=int(row["year"]),
                    contribution=float(row.get("annual_contribution", row.get("contribution", 0.0)) or 0.0),
                    special_assessment=float(row.get("special_assessment", 0.0) or 0.0),
                )
            )
        return cls.from_rows(rows)

    def annual_df(self) -> pd.DataFrame:
        return pd.DataFrame([row.to_dict() for row in self.annual_collections])

    def annual_for_year(self, year: int) -> AnnualCollection:
        match = next((row for row in self.annual_collections if int(row.year) == int(year)), None)
        return match or AnnualCollection(year=int(year), contribution=0.0, special_assessment=0.0)

    def annual_maps(self) -> tuple[dict[int, float], dict[int, float]]:
        contribution_map = {int(row.year): float(row.contribution) for row in self.annual_collections}
        special_map = {int(row.year): float(row.special_assessment) for row in self.annual_collections}
        return contribution_map, special_map

    def dated_events(self, start_year: int, projection_years: int) -> list[CashflowEvent]:
        events: list[CashflowEvent] = []
        for year in range(int(start_year), int(start_year) + int(projection_years)):
            annual = self.annual_for_year(year)
            monthly_contribution = float(annual.contribution) / 12.0
            for month in range(1, 13):
                events.append(
                    CashflowEvent(
                        date=pd.Timestamp(year=year, month=month, day=1),
                        amount=monthly_contribution,
                        event_type="contribution",
                    )
                )
            if annual.special_assessment:
                events.append(
                    CashflowEvent(
                        date=pd.Timestamp(year=year, month=1, day=1),
                        amount=float(annual.special_assessment),
                        event_type="special_assessment",
                    )
                )
        return events

    def with_contributions(self, years, contribution_vector, special_vector=None) -> "CollectionSchedule":
        years = list(years)
        if special_vector is None:
            special_vector = [0.0] * len(years)
        rows = [
            AnnualCollection(year=int(year), contribution=float(contribution), special_assessment=float(special))
            for year, contribution, special in zip(years, contribution_vector, special_vector)
        ]
        return CollectionSchedule.from_rows(rows)
