from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reserve_study.models import Assumptions, Component, ReserveStudyScenario, ScenarioPaths
from reserve_study.schedules import CollectionSchedule
from reserve_study.study import ReserveStudy


DEFAULT_PROJECTION_YEARS = 30
DEFAULT_UNITS = 138

COMPONENT_INPUT_COLUMNS = [
    "category",
    "subcategory",
    "component",
    "tracking",
    "method",
    "cost",
    "cost_units",
    "quantity",
    "quantity_units",
    "life_years",
    "remaining_life",
    "service_date",
    "source_page",
]

ASSESSMENT_INPUT_COLUMNS = [
    "year",
    "annual_contribution",
    "special_assessment",
]

ASSUMPTION_DEFAULTS = {
    "Analysis Date": "2026-01-01",
    "Inflation": 0.03,
    "Investment": 0.025,
    "Contribution Factor": 0.0,
    "Begin Balance": 0.0,
}


def coerce_assumptions_frame(source) -> pd.DataFrame:
    df = _read_frame(source)
    if df.empty:
        df = pd.DataFrame(
            [{"Parameter": key, "Value": value} for key, value in ASSUMPTION_DEFAULTS.items()]
        )

    if {"Parameter", "Value"}.issubset(df.columns):
        out = df[["Parameter", "Value"]].copy()
    else:
        raise ValueError("Assumptions must include Parameter and Value columns.")

    values = dict(zip(out["Parameter"], out["Value"]))
    for key, value in ASSUMPTION_DEFAULTS.items():
        if key not in values or pd.isna(values[key]) or values[key] == "":
            out.loc[len(out)] = {"Parameter": key, "Value": value}

    order = list(ASSUMPTION_DEFAULTS)
    out["_order"] = out["Parameter"].map({name: index for index, name in enumerate(order)})
    out = out.sort_values("_order", na_position="last").drop(columns="_order")
    return out.reset_index(drop=True)


def load_assumptions(source) -> dict[str, object]:
    frame = coerce_assumptions_frame(source)
    values = dict(zip(frame["Parameter"], frame["Value"]))
    return {
        "analysis_date": pd.to_datetime(values["Analysis Date"]),
        "inflation": float(values["Inflation"]),
        "investment": float(values["Investment"]),
        "contribution_factor": float(values["Contribution Factor"]),
        "begin_balance": float(values["Begin Balance"]),
    }


def prepare_components_input(source) -> pd.DataFrame:
    df = _read_frame(source)
    out = df.copy()
    for column in COMPONENT_INPUT_COLUMNS:
        if column not in out.columns:
            out[column] = "" if column in {"category", "subcategory", "component", "tracking", "method", "cost_units", "quantity_units", "remaining_life", "service_date", "source_page"} else 0
    out = out[COMPONENT_INPUT_COLUMNS].copy()

    for column in ["cost", "quantity", "life_years"]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0)

    for column in ["category", "subcategory", "component", "tracking", "method", "cost_units", "quantity_units", "remaining_life", "service_date", "source_page"]:
        out[column] = out[column].fillna("").astype(str)

    return out


def prepare_assessment_input(source) -> pd.DataFrame:
    df = _read_frame(source)
    out = df.copy()
    if "contribution" in out.columns and "annual_contribution" not in out.columns:
        out = out.rename(columns={"contribution": "annual_contribution"})
    for column in ASSESSMENT_INPUT_COLUMNS:
        if column not in out.columns:
            out[column] = 0
    out = out[ASSESSMENT_INPUT_COLUMNS].copy()
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    out = out.dropna(subset=["year"]).copy()
    out["year"] = out["year"].astype(int)
    out["annual_contribution"] = pd.to_numeric(out["annual_contribution"], errors="coerce").fillna(0.0)
    out["special_assessment"] = pd.to_numeric(out["special_assessment"], errors="coerce").fillna(0.0)
    return out.sort_values("year").reset_index(drop=True)


def run_reserve_study(
    assumptions_frame: pd.DataFrame,
    components_frame: pd.DataFrame,
    assessment_frame: pd.DataFrame,
    projection_years: int = DEFAULT_PROJECTION_YEARS,
    units: int = DEFAULT_UNITS,
) -> dict[str, object]:
    assumptions_input = coerce_assumptions_frame(assumptions_frame)
    components_input = prepare_components_input(components_frame)
    assessment_input = prepare_assessment_input(assessment_frame)

    assumptions = Assumptions.from_mapping(dict(zip(assumptions_input["Parameter"], assumptions_input["Value"])))
    components = [_component_from_row(row) for _, row in components_input.iterrows()]
    collection_schedule = CollectionSchedule.from_dataframe(assessment_input)
    scenario = ReserveStudyScenario(
        paths=ScenarioPaths.for_variant(
            legacy_root=PROJECT_ROOT,
            variant_name="web_session",
            output_root=PROJECT_ROOT / "runs" / "web_session",
            assets_root=PROJECT_ROOT / "assets",
        ),
        assumptions=assumptions,
        components=components,
        collection_schedule=collection_schedule,
        association_properties={"NUM_UNITS": str(int(units))},
    )
    result = ReserveStudy(scenario).run(projection_years=int(projection_years))

    return {
        "assumptions": load_assumptions(assumptions_input),
        "assumptions_frame": assumptions_input,
        "components_frame": components_input,
        "assessment_frame": assessment_input,
        "component_list_detail": result.component_details_df(),
        "expenditures_by_year_detail": result.expenditures_detail_df(),
        "expenditures_by_year_summary": result.expenditures_summary_df(),
        "expenditures_matrix": result.expenditures_matrix_df(),
        "reserve_projection": result.reserve_projection_df(),
        "statement_of_position": result.statement_of_position_df(),
        "statement_of_position_formatted": _statement_for_web(result.statement_of_position_formatted_df()),
        "study_result": result,
    }


def _component_from_row(row: pd.Series) -> Component:
    return Component(
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
        service_date=row.get("service_date") or None,
        source_page=row.get("source_page", ""),
    )


def _statement_for_web(df: pd.DataFrame) -> pd.DataFrame:
    out = df.rename(columns={"metric": "Metric", "formatted": "Value"})
    return out[["Metric", "Value"]]


def _read_frame(source) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source.copy()
    return pd.read_csv(source).copy()
