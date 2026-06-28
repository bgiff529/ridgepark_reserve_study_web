from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from .utils import add_months, months_to_ym, normalize_to_month, parse_remaining_life_to_months, years_to_months


@dataclass(frozen=True)
class Assumptions:
    analysis_date: pd.Timestamp
    inflation: float
    investment: float
    contribution_factor: float
    begin_balance: float

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "Assumptions":
        return cls(
            analysis_date=normalize_to_month(pd.to_datetime(values["Analysis Date"])),
            inflation=float(values["Inflation"]),
            investment=float(values["Investment"]),
            contribution_factor=float(values["Contribution Factor"]),
            begin_balance=float(values["Begin Balance"]),
        )

    @property
    def analysis_year(self) -> int:
        return int(pd.Timestamp(self.analysis_date).year)


@dataclass
class Component:
    category: str
    subcategory: str
    component: str
    method: str
    cost: float
    cost_units: str
    quantity: float
    quantity_units: str
    useful_life: float
    remaining_useful_life: str
    notes: str = ""
    b6_category: str = ""
    component_id: int | None = None

    def __post_init__(self) -> None:
        self.category = str(self.category).strip()
        self.subcategory = str(self.subcategory).strip()
        self.component = str(self.component).strip()
        self.method = "One Time" if str(self.method).strip().lower() == "one time" else "Repeating"
        self.cost_units = str(self.cost_units).strip()
        self.quantity_units = str(self.quantity_units).strip()
        self.b6_category = "" if pd.isna(self.b6_category) else str(self.b6_category).strip()
        remaining_months = parse_remaining_life_to_months(self.remaining_useful_life)
        self.remaining_useful_life = "0:00" if pd.isna(remaining_months) else months_to_ym(remaining_months)
        self.notes = "" if pd.isna(self.notes) else str(self.notes).strip()
        self.cost = float(self.cost)
        self.quantity = float(self.quantity)
        self.useful_life = float(self.useful_life)

    @property
    def normalized_method(self) -> str:
        return "One Time" if self.method.strip().lower() == "one time" else "Repeating"

    @property
    def is_one_time(self) -> bool:
        return self.normalized_method.lower() == "one time"

    @property
    def life_years(self) -> float:
        return self.useful_life

    @property
    def life_months(self) -> float:
        return years_to_months(self.useful_life)

    @property
    def remaining_life(self) -> str:
        return self.remaining_useful_life

    @property
    def remaining_life_months(self) -> float:
        return parse_remaining_life_to_months(self.remaining_useful_life)

    @property
    def current_cost(self) -> float:
        return float(self.cost) * float(self.quantity)

    def replacement_date(self, analysis_date: pd.Timestamp) -> pd.Timestamp:
        if pd.isna(self.remaining_life_months):
            return pd.NaT
        return add_months(analysis_date, self.remaining_life_months)

    def future_cost(self, analysis_date: pd.Timestamp, inflation: float, months_from_analysis: int | None = None) -> float:
        if months_from_analysis is None:
            months_from_analysis = self.remaining_life_months
        if pd.isna(months_from_analysis):
            return np.nan
        return round(self.current_cost * (1 + float(inflation)) ** (float(months_from_analysis) / 12), 2)

    def to_detail_row(self, assumptions: Assumptions) -> dict[str, object]:
        return {
            "component_id": self.component_id,
            "category": self.category,
            "subcategory": self.subcategory,
            "component": self.component,
            "method": self.normalized_method,
            "cost": self.cost,
            "cost_units": self.cost_units,
            "quantity": self.quantity,
            "quantity_units": self.quantity_units,
            "useful_life": self.useful_life,
            "life_months": self.life_months,
            "life_display": months_to_ym(self.life_months),
            "remaining_useful_life": self.remaining_useful_life,
            "remaining_life_months": self.remaining_life_months,
            "remaining_life_display": months_to_ym(self.remaining_life_months),
            "current_cost": round(self.current_cost, 2),
            "replacement_date": self.replacement_date(assumptions.analysis_date),
            "future_cost": self.future_cost(assumptions.analysis_date, assumptions.inflation),
            "notes": self.notes,
            "B6_category": self.b6_category,
        }


@dataclass(frozen=True)
class CashflowEvent:
    date: pd.Timestamp
    amount: float
    event_type: str
    component_id: int | None = None
    occurrence: int | None = None
    category: str = ""
    subcategory: str = ""
    component: str = ""
    method: str = ""
    useful_life: float | None = None
    life_months: int | None = None
    current_cost: float | None = None
    notes: str = ""
    b6_category: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "date", normalize_to_month(pd.Timestamp(self.date)))
        object.__setattr__(self, "amount", float(self.amount))
        object.__setattr__(self, "event_type", str(self.event_type).strip())

    @property
    def year(self) -> int:
        return int(pd.Timestamp(self.date).year)

    @property
    def month(self) -> int:
        return int(pd.Timestamp(self.date).month)

    def to_expenditure_row(self) -> dict[str, object]:
        return {
            "component_id": self.component_id,
            "replacement_date": self.date,
            "occurrence": self.occurrence,
            "category": self.category,
            "subcategory": self.subcategory,
            "component": self.component,
            "method": self.method,
            "useful_life": self.useful_life,
            "life_months": self.life_months,
            "current_cost": None if self.current_cost is None else round(float(self.current_cost), 2),
            "future_cost": round(float(self.amount), 2),
            "notes": self.notes,
            "B6_category": self.b6_category,
            "replacement_year": self.year,
        }


@dataclass(frozen=True)
class AnnualCollection:
    year: int
    contribution: float
    special_assessment: float = 0.0
    additional_income: float = 0.0

    def to_dict(self) -> dict[str, float | int]:
        return {
            "year": int(self.year),
            "contribution": round(float(self.contribution), 2),
            "special_assessment": round(float(self.special_assessment), 2),
            "additional_income": round(float(self.additional_income), 2),
        }


@dataclass
class ReserveProjectionYear:
    year: int
    begin_balance: float
    contribution: float
    special_assessment: float
    additional_income: float
    expenditures: float
    interest: float
    end_balance: float
    funded_balance: float | None = None
    percent_funded: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "year": int(self.year),
            "begin_balance": round(self.begin_balance, 2),
            "contribution": round(self.contribution, 2),
            "special_assessment": round(self.special_assessment, 2),
            "additional_income": round(self.additional_income, 2),
            "expenditures": round(self.expenditures, 2),
            "interest": round(self.interest, 2),
            "end_balance": round(self.end_balance, 2),
            "funded_balance": None if self.funded_balance is None else round(self.funded_balance, 2),
            "percent_funded": None if self.percent_funded is None else round(self.percent_funded, 2),
        }


@dataclass(frozen=True)
class StatementMetric:
    metric: str
    value: float | str

    def formatted(self) -> str:
        money_metrics = {
            "Current Replacement Cost",
            "Future Replacement Cost",
            "Current Reserve Fund Balance",
            "Fully Funded Reserve Balance",
            "Reserve Deficit",
            "Reserve Deficit per Unit",
            "Projected Annual Reserve Contribution",
            "Average Annual Reserve Contribution per Unit",
            "Projected Monthly Reserve Contribution",
            "Average Monthly Reserve Contribution per Unit",
        }
        percent_metrics = {
            "Percent Funded",
            "Projected Inflation Rate",
            "Projected Interest Rate",
        }
        if self.metric in money_metrics:
            return f"${float(self.value):,.0f}"
        if self.metric in percent_metrics:
            return f"{float(self.value):.2f} %"
        return str(self.value)


@dataclass(frozen=True)
class ReportMetadata:
    report_title: str = "Reserve Management Plan"
    report_type: str = "Type 1"
    report_subtitle: str = "Reserve Study with Data-Driven Analysis"
    signer_name: str = "Brendan J. Gifford"
    signer_title: str = "Ridge Park Treasurer"
    report_file_stem: str = "ridge_park_reserve_report_latex"


@dataclass(frozen=True)
class ScenarioPaths:
    legacy_root: Path
    variant_name: str
    output_root: Path
    assets_root: Path

    @classmethod
    def for_variant(
        cls,
        legacy_root: Path | str | None,
        variant_name: str,
        output_root: Path | str | None = None,
        assets_root: Path | str | None = None,
    ) -> "ScenarioPaths":
        project_root = Path(__file__).resolve().parents[1]
        if legacy_root is None:
            legacy_root = project_root
        legacy_root = Path(legacy_root).expanduser().resolve()
        if output_root is None:
            output_root = project_root / "runs" / variant_name
        if assets_root is None:
            assets_root = project_root / "assets"
        return cls(
            legacy_root=legacy_root,
            variant_name=variant_name,
            output_root=Path(output_root).expanduser().resolve(),
            assets_root=Path(assets_root).expanduser().resolve(),
        )

    @property
    def legacy_variant_dir(self) -> Path:
        return self.legacy_root / self.variant_name

    @property
    def source_data_dir(self) -> Path:
        return self.legacy_variant_dir / "source_data"

    @property
    def report_sources_dir(self) -> Path:
        return self.source_data_dir / "report_sources"

    @property
    def output_source_data_dir(self) -> Path:
        return self.output_root / "source_data"

    @property
    def working_csv_dir(self) -> Path:
        return self.output_root / "working_csv"

    @property
    def report_dir(self) -> Path:
        return self.output_root / "report_latex"

    @property
    def plots_dir(self) -> Path:
        return self.output_root / "plots"

    def ensure_output_dirs(self) -> None:
        self.output_source_data_dir.mkdir(parents=True, exist_ok=True)
        self.working_csv_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ReserveStudyScenario:
    paths: ScenarioPaths
    assumptions: Assumptions
    components: list[Component]
    collection_schedule: object
    association_properties: dict[str, str] = field(default_factory=dict)
    cover_letter: str = ""
    preparer_report: str = ""


@dataclass(frozen=True)
class OptimizationResult:
    optimized_collection_schedule: object
    projection: object
    diagnostics: dict[str, object]

    def assessments_df(self) -> pd.DataFrame:
        return self.optimized_collection_schedule.annual_df()

    def projection_df(self) -> pd.DataFrame:
        return self.projection.to_dataframe()
