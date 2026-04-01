# %%
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# %%
PROJECT_ROOT = Path(__file__).resolve().parent
VARIANT_NAME = os.getenv("RESERVE_STUDY_VARIANT", "2026_brendan_plan")
BASE_DIR = PROJECT_ROOT / VARIANT_NAME
SOURCE_DATA = BASE_DIR / "source_data"
WORKING_CSV = BASE_DIR / "working_csv"
WORKING_CSV.mkdir(parents=True, exist_ok=True)

COMPONENT_FILE = SOURCE_DATA / "component_list_v2.csv"
ASSUMPTIONS_FILE = SOURCE_DATA / "assumptions.csv"
ASSESSMENT_FILE = SOURCE_DATA / "assessment_contributions.csv" 

# %%
DAY_OF_MONTH = 1
DEFAULT_PROJECTION_YEARS = 30
DEFAULT_UNITS = 138

ASSUMPTIONS_PARAMETER_ORDER = [
    "Analysis Date",
    "Inflation",
    "Investment",
    "Contribution Factor",
    "Begin Balance",
]

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

def normalize_to_month(dt, day=DAY_OF_MONTH):
    dt = pd.Timestamp(dt)
    return pd.Timestamp(year=dt.year, month=dt.month, day=day)

def parse_remaining_life_to_months(text):
    text = str(text).strip()
    if text == "" or text.lower() == "nan":
        return np.nan
    if ":" in text:
        y, m = text.split(":")
        return int(y) * 12 + int(m)
    return int(round(float(text) * 12))

def years_to_months(years):
    if pd.isna(years):
        return np.nan
    return int(round(float(years) * 12))

def months_to_ym(months):
    if pd.isna(months):
        return np.nan
    months = int(months)
    y = months // 12
    m = months % 12
    return f"{y}:{m:02d}"

def add_months(base_date, months, day=DAY_OF_MONTH):
    base_date = normalize_to_month(base_date, day=day)
    months = int(months)
    total = (base_date.year * 12 + (base_date.month - 1)) + months
    year = total // 12
    month = total % 12 + 1
    return pd.Timestamp(year=year, month=month, day=day)

def shift_by_life(base_date, life_months, direction=1, day=DAY_OF_MONTH):
    return add_months(base_date, direction * int(life_months), day=day)

def months_between(start_date, end_date):
    start_date = normalize_to_month(start_date)
    end_date = normalize_to_month(end_date)
    return (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)

# %%
def load_assumptions(path):
    assumptions = path.copy() if isinstance(path, pd.DataFrame) else pd.read_csv(path)
    values = dict(zip(assumptions["Parameter"], assumptions["Value"]))

    return {
        "analysis_date": normalize_to_month(pd.to_datetime(values["Analysis Date"])),
        "inflation": float(values["Inflation"]),
        "investment": float(values["Investment"]),
        "contribution_factor": float(values["Contribution Factor"]),
        "begin_balance": float(values["Begin Balance"]),
    }


def assumptions_dict_to_frame(assumptions):
    return pd.DataFrame(
        [
            {"Parameter": "Analysis Date", "Value": pd.Timestamp(assumptions["analysis_date"]).strftime("%Y-%m-%d")},
            {"Parameter": "Inflation", "Value": assumptions["inflation"]},
            {"Parameter": "Investment", "Value": assumptions["investment"]},
            {"Parameter": "Contribution Factor", "Value": assumptions.get("contribution_factor", 0)},
            {"Parameter": "Begin Balance", "Value": assumptions["begin_balance"]},
        ]
    )


def coerce_assumptions_frame(df):
    assumptions = df.copy()
    assumptions.columns = [str(c).strip() for c in assumptions.columns]

    if "Parameter" not in assumptions.columns or "Value" not in assumptions.columns:
        raise ValueError("Assumptions input must contain Parameter and Value columns.")

    assumptions["Parameter"] = assumptions["Parameter"].astype(str).str.strip()
    assumptions["Value"] = assumptions["Value"].astype(str).str.strip()

    missing = [name for name in ASSUMPTIONS_PARAMETER_ORDER if name not in set(assumptions["Parameter"])]
    if missing:
        raise ValueError(f"Missing assumptions parameters: {missing}")

    assumptions = assumptions.drop_duplicates(subset=["Parameter"], keep="last")
    assumptions = assumptions.set_index("Parameter").loc[ASSUMPTIONS_PARAMETER_ORDER].reset_index()
    return assumptions


def prepare_components_input(df):
    components = df.copy()
    components.columns = [str(c).strip() for c in components.columns]

    for col in COMPONENT_INPUT_COLUMNS:
        if col not in components.columns:
            components[col] = ""

    components = components[COMPONENT_INPUT_COLUMNS].copy()
    components["source_page"] = components["source_page"].fillna("").astype(str)
    return components


def prepare_assessment_input(df):
    assessments = df.copy()
    assessments.columns = [str(c).strip() for c in assessments.columns]

    for col in ASSESSMENT_INPUT_COLUMNS:
        if col not in assessments.columns:
            assessments[col] = 0

    return assessments[ASSESSMENT_INPUT_COLUMNS].copy()

def load_components(path):
    df = prepare_components_input(path.copy() if isinstance(path, pd.DataFrame) else pd.read_csv(path).copy())

    required_columns = [
        "category", "subcategory", "component", "tracking", "method",
        "cost", "cost_units", "quantity", "quantity_units",
        "life_years", "remaining_life", "service_date",
    ]

    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in component source: {missing}")

    text_cols = [
        "category", "subcategory", "component", "tracking",
        "method", "cost_units", "quantity_units", "remaining_life",
    ]

    for col in text_cols:
        df[col] = df[col].astype(str).str.strip()

    df["method"] = df["method"].replace({
        "fixed": "Fixed",
        "one time": "One Time",
    })

    df["cost"] = pd.to_numeric(df["cost"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["life_years"] = pd.to_numeric(df["life_years"], errors="coerce")

    df["life_months"] = df["life_years"].apply(years_to_months)
    df["remaining_life_months"] = df["remaining_life"].apply(parse_remaining_life_to_months)

    df["service_date"] = pd.to_datetime(df["service_date"], errors="coerce")
    df["service_date"] = df["service_date"].apply(
        lambda x: normalize_to_month(x) if pd.notna(x) else pd.NaT
    )

    df["current_cost"] = df["cost"] * df["quantity"]

    return df

def load_assessment_contributions(path):
    df = prepare_assessment_input(path.copy() if isinstance(path, pd.DataFrame) else pd.read_csv(path).copy())
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype(int)
    df["contribution"] = pd.to_numeric(df["annual_contribution"], errors="coerce").fillna(0.0)
    df["special_assessment"] = pd.to_numeric(df["special_assessment"], errors="coerce").fillna(0.0)
    return df[["year", "contribution", "special_assessment"]]

# %%
def build_component_list_detail(components, assumptions):
    df = components.copy().reset_index(drop=True)

    analysis_date = normalize_to_month(pd.Timestamp(assumptions["analysis_date"]))
    inflation = float(assumptions["inflation"])

    df["component_id"] = df.index.astype(int)

    df["replacement_date"] = df["remaining_life_months"].apply(
        lambda m: add_months(analysis_date, m) if pd.notna(m) else pd.NaT
    )

    df["future_cost"] = (
        df["current_cost"] * (1 + inflation) ** (df["remaining_life_months"] / 12)
    ).round(2)

    df["life_display"] = df["life_months"].apply(months_to_ym)
    df["remaining_life_display"] = df["remaining_life_months"].apply(months_to_ym)

    return df[
        [
            "component_id",
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
            "life_months",
            "life_display",
            "remaining_life",
            "remaining_life_months",
            "remaining_life_display",
            "service_date",
            "current_cost",
            "replacement_date",
            "future_cost",
            "source_page",
        ]
    ].copy()

# %%
def build_expenditures_by_year_detail(
    component_list_detail,
    assumptions,
    projection_years=30,
    extend_for_next_instance=True,
):
    analysis_date = normalize_to_month(pd.Timestamp(assumptions["analysis_date"]))
    inflation = float(assumptions["inflation"])

    max_life_months = int(component_list_detail["life_months"].max())

    projection_months = projection_years * 12
    if extend_for_next_instance:
        projection_months += max_life_months

    projection_end = add_months(analysis_date, projection_months)

    records = []

    for _, row in component_list_detail.iterrows():
        replacement_date = pd.Timestamp(row["replacement_date"])
        life_months = int(row["life_months"])
        method = str(row["method"]).strip().lower()

        occurrence = 1

        while replacement_date <= projection_end:
            months_from_analysis = months_between(analysis_date, replacement_date)

            occurrence_future_cost = (
                float(row["current_cost"]) * (1 + inflation) ** (months_from_analysis / 12)
            )

            records.append({
                "component_id": row["component_id"],
                "replacement_date": replacement_date,
                "occurrence": occurrence,
                "category": row["category"],
                "subcategory": row["subcategory"],
                "component": row["component"],
                "tracking": row["tracking"],
                "method": row["method"],
                "life_years": row["life_years"],
                "life_months": row["life_months"],
                "current_cost": row["current_cost"],
                "future_cost": round(occurrence_future_cost, 2),
                "source_page": row["source_page"],
            })

            if method == "one time":
                break

            replacement_date = shift_by_life(replacement_date, life_months, direction=1)
            occurrence += 1

    out = pd.DataFrame(records)
    out["replacement_year"] = out["replacement_date"].dt.year

    return out.sort_values(
        ["component_id", "replacement_date", "occurrence"]
    ).reset_index(drop=True)

# %%
def build_expenditures_by_year_summary(expenditures_by_year_detail, projection_years=30):
    first_year = int(expenditures_by_year_detail["replacement_year"].min())
    max_year = first_year + projection_years - 1

    out = (
        expenditures_by_year_detail.loc[
            expenditures_by_year_detail["replacement_year"] <= max_year
        ]
        .groupby("replacement_year", as_index=False)
        .agg(
            expenditures=("future_cost", "sum"),
            component_count=("component", "count")
        )
        .sort_values("replacement_year")
        .reset_index(drop=True)
    )

    out["expenditures"] = out["expenditures"].round(2)
    return out

# %%
# =========================================
# BUILD EXPENDITURES MATRIX
# =========================================

def build_expenditures_matrix(expenditures_by_year_detail, projection_years=30):
    first_year = int(expenditures_by_year_detail["replacement_year"].min())
    max_year = first_year + projection_years - 1

    out = (
        expenditures_by_year_detail.loc[
            expenditures_by_year_detail["replacement_year"] <= max_year
        ]
        .pivot_table(
            index="category",
            columns="replacement_year",
            values="future_cost",
            aggfunc="sum",
            fill_value=0.0
        )
        .sort_index()
    )

    return out.round(2)

# %%
def build_funded_balance(
    expenditures_by_year_detail,
    assumptions,
    projection_years=30,
    method="current_cost_straight_line",   # "current_cost_straight_line", "future_cost_straight_line", "future_cost_time_valued"
    funded_date="analysis",                # "analysis", "beginning", "end", "custom"
    custom_month=1,
    custom_day=1,
    respect_one_time=True,
    inflate_result=False,
):
    valid_methods = {
        "current_cost_straight_line",
        "future_cost_straight_line",
        "future_cost_time_valued",
    }

    if method not in valid_methods:
        raise ValueError(f"method must be one of {sorted(valid_methods)}")

    df = expenditures_by_year_detail.copy()
    df["replacement_date"] = pd.to_datetime(df["replacement_date"])

    analysis_date = normalize_to_month(pd.Timestamp(assumptions["analysis_date"]))
    inflation = float(assumptions["inflation"])
    investment = float(assumptions["investment"])

    years = [analysis_date.year + i for i in range(projection_years + 1)]
    funded_balances = []

    for year in years:
        if funded_date == "analysis":
            as_of_date = pd.Timestamp(
                year=year,
                month=analysis_date.month,
                day=analysis_date.day
            )
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

        for component_id, group in df.groupby("component_id", sort=False):
            group = group.sort_values("replacement_date").reset_index(drop=True)

            row_method = str(group["method"].iloc[0]).strip().lower()
            one_time_mode = respect_one_time and (row_method == "one time")

            active_rows = group.loc[group["replacement_date"] >= as_of_date]

            if not active_rows.empty:
                active_row = active_rows.iloc[0]
                next_service_date = pd.Timestamp(active_row["replacement_date"])
                life_months = int(active_row["life_months"])
                current_cost = float(active_row["current_cost"])
                future_cost = float(active_row["future_cost"])
            else:
                if one_time_mode:
                    continue

                last_row = group.iloc[-1]
                life_months = int(last_row["life_months"])
                current_cost = float(last_row["current_cost"])

                next_service_date = pd.Timestamp(last_row["replacement_date"])
                while next_service_date < as_of_date:
                    next_service_date = shift_by_life(
                        next_service_date,
                        life_months,
                        direction=1
                    )

                months_to_next = months_between(analysis_date, next_service_date)
                future_cost = current_cost * (1 + inflation) ** (months_to_next / 12)

            if one_time_mode and next_service_date < as_of_date:
                continue

            service_date = shift_by_life(
                next_service_date,
                life_months,
                direction=-1
            )

            age_months = months_between(service_date, as_of_date)
            age_months = max(0, min(age_months, life_months))

            if method == "current_cost_straight_line":
                funded_value = current_cost * (age_months / life_months)

            elif method == "future_cost_straight_line":
                funded_value = future_cost * (age_months / life_months)

            elif method == "future_cost_time_valued":
                age_years = age_months / 12
                life_years = life_months / 12

                if investment == 0:
                    funded_fraction = age_months / life_months
                else:
                    funded_fraction = (
                        ((1 + investment) ** age_years - 1)
                        / ((1 + investment) ** life_years - 1)
                    )

                funded_value = future_cost * funded_fraction

            total += funded_value

        if inflate_result:
            inflation_months = months_between(analysis_date, as_of_date)
            total = total * (1 + inflation) ** (inflation_months / 12)

        funded_balances.append(round(total, 2))

    return pd.Series(funded_balances, index=years, name="funded_balance")

# %%
def build_reserve_projection(
    expenditures_by_year_detail,
    assumptions,
    assessment_contributions,
    start_year=None,
    projection_years=30,
    starting_balance=None,
):
    """
    Build annual reserve projection using monthly cash flow with:
      - 360-day year
      - monthly_rate = annual_rate / 12
      - monthly order = cies
          c = regular monthly contribution
          i = interest
          e = expenditures in month due
          s = special assessment in January
    """

    annual_rate = float(assumptions["investment"])
    monthly_rate = annual_rate / 12.0

    if start_year is None:
        start_year = pd.Timestamp(assumptions["analysis_date"]).year

    if starting_balance is None:
        current_balance = float(assumptions["begin_balance"])
    else:
        current_balance = float(starting_balance)

    end_year = start_year + projection_years - 1

    # -----------------------------
    # Contributions / assessments
    # -----------------------------
    assess = assessment_contributions.copy()
    assess["year"] = assess["year"].astype(int)
    assess["contribution"] = pd.to_numeric(
        assess["contribution"], errors="coerce"
    ).fillna(0.0)
    assess["special_assessment"] = pd.to_numeric(
        assess["special_assessment"], errors="coerce"
    ).fillna(0.0)

    contrib_map = dict(zip(assess["year"], assess["contribution"]))
    special_map = dict(zip(assess["year"], assess["special_assessment"]))

    # -----------------------------
    # Expenditures by year / month
    # -----------------------------
    exp = expenditures_by_year_detail.copy()
    exp["replacement_date"] = pd.to_datetime(exp["replacement_date"])
    exp["replacement_year"] = exp["replacement_date"].dt.year
    exp["replacement_month"] = exp["replacement_date"].dt.month
    exp["future_cost"] = pd.to_numeric(exp["future_cost"], errors="coerce").fillna(0.0)

    monthly_exp_map = (
        exp.groupby(["replacement_year", "replacement_month"])["future_cost"]
        .sum()
        .to_dict()
    )

    # -----------------------------
    # Run monthly cash flow
    # -----------------------------
    records = []

    for year in range(start_year, end_year + 1):
        begin_balance = current_balance

        annual_contribution = float(contrib_map.get(year, 0.0))
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

        records.append(
            {
                "year": year,
                "begin_balance": round(begin_balance, 2),
                "contribution": round(annual_contribution, 2),
                "special_assessment": round(annual_special, 2),
                "expenditures": round(year_expenditures, 2),
                "interest": round(year_interest, 2),
                "end_balance": round(current_balance, 2),
            }
        )

    return pd.DataFrame(records)


# %%
def format_statement_of_position(df):
    out = df.copy()

    col_map = {str(c).strip().lower(): c for c in out.columns}
    metric_col = col_map.get("metric")
    value_col = col_map.get("value")

    if metric_col is None or value_col is None:
        raise KeyError(
            f"statement_of_position must contain Metric/Value columns. Found: {list(out.columns)}"
        )

    out = out.rename(columns={metric_col: "metric", value_col: "value"})
    out["metric"] = out["metric"].astype(str).str.strip()

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

    def fmt(row):
        metric = row["metric"]
        value = row["value"]

        if metric in money_metrics:
            return f"${float(value):,.0f}"
        if metric in percent_metrics:
            return f"{float(value):.2f} %"
        return value

    out["formatted"] = out.apply(fmt, axis=1)
    return out[["metric", "formatted"]]


def build_statement_of_position(
    assumptions,
    component_list_detail,
    expenditures_by_year_detail,
    assessment_contributions,
    units=DEFAULT_UNITS,
    projection_years=DEFAULT_PROJECTION_YEARS,
):
    analysis_date = pd.Timestamp(assumptions["analysis_date"])
    analysis_year = analysis_date.year
    units = int(units)

    statement_funded_balance = build_funded_balance(
        expenditures_by_year_detail,
        assumptions,
        projection_years=projection_years,
        method="current_cost_straight_line",
        funded_date="analysis",
        respect_one_time=True,
        inflate_result=False,
    )

    statement_funded_amount = float(statement_funded_balance.loc[analysis_year])
    projected_balance_reserves = float(assumptions["begin_balance"])
    percent_funded = projected_balance_reserves / statement_funded_amount * 100
    reserve_deficit_per_unit = (statement_funded_amount - projected_balance_reserves) / units

    first_year_assessment = assessment_contributions.loc[
        assessment_contributions["year"] == analysis_year
    ]
    if first_year_assessment.empty:
        first_year_row = {"contribution": 0.0, "special_assessment": 0.0}
    else:
        first_year_row = first_year_assessment.iloc[0]

    projected_reserve_contribution = (
        float(first_year_row["contribution"]) + float(first_year_row["special_assessment"])
    )
    monthly_reserve_contribution_first_year = float(first_year_row["contribution"]) / 12

    statement_of_position = pd.DataFrame(
        [
            ["Current Replacement Cost", float(component_list_detail["current_cost"].sum())],
            ["Future Replacement Cost", float(component_list_detail["future_cost"].sum())],
            ["Current Reserve Fund Balance", projected_balance_reserves],
            ["Fully Funded Reserve Balance", statement_funded_amount],
            ["Percent Funded", percent_funded],
            ["Reserve Deficit", statement_funded_amount - projected_balance_reserves],
            ["Reserve Deficit per Unit", reserve_deficit_per_unit],
            ["Projected Annual Reserve Contribution", projected_reserve_contribution],
            ["Average Annual Reserve Contribution per Unit", float(first_year_row["contribution"]) / units],
            ["Projected Monthly Reserve Contribution", monthly_reserve_contribution_first_year],
            ["Average Monthly Reserve Contribution per Unit", monthly_reserve_contribution_first_year / units],
        ],
        columns=["Metric", "Value"],
    )

    return statement_of_position, format_statement_of_position(statement_of_position)


def run_reserve_study(
    assumptions_frame,
    components_frame,
    assessment_frame,
    projection_years=DEFAULT_PROJECTION_YEARS,
    units=DEFAULT_UNITS,
):
    assumptions_clean = coerce_assumptions_frame(assumptions_frame)
    components_clean = prepare_components_input(components_frame)
    assessments_clean = prepare_assessment_input(assessment_frame)

    if components_clean.replace("", np.nan).dropna(how="all").empty:
        raise ValueError("At least one component row is required to run the study.")

    assumptions = load_assumptions(assumptions_clean)
    components_raw = load_components(components_clean)
    assessment_contributions = load_assessment_contributions(assessments_clean)

    analysis_year = pd.Timestamp(assumptions["analysis_date"]).year

    component_list_detail = build_component_list_detail(components_raw, assumptions)
    expenditures_by_year_detail = build_expenditures_by_year_detail(
        component_list_detail,
        assumptions,
        projection_years=projection_years,
        extend_for_next_instance=True,
    )
    expenditures_by_year_summary = build_expenditures_by_year_summary(
        expenditures_by_year_detail,
        projection_years=projection_years,
    )
    expenditures_matrix = build_expenditures_matrix(
        expenditures_by_year_detail,
        projection_years=projection_years,
    )
    reserve_projection = build_reserve_projection(
        expenditures_by_year_detail=expenditures_by_year_detail,
        assumptions=assumptions,
        assessment_contributions=assessment_contributions,
        start_year=analysis_year,
        projection_years=projection_years,
    )

    funded_balance_end = build_funded_balance(
        component_list_detail,
        assumptions,
        projection_years=projection_years,
        method="current_cost_straight_line",
        funded_date="end",
        respect_one_time=True,
        inflate_result=True,
    )

    reserve_projection["funded_balance"] = reserve_projection["year"].map(funded_balance_end)
    reserve_projection["percent_funded"] = (
        reserve_projection["end_balance"] / reserve_projection["funded_balance"] * 100
    ).round(2)

    statement_of_position, statement_of_position_formatted = build_statement_of_position(
        assumptions=assumptions,
        component_list_detail=component_list_detail,
        expenditures_by_year_detail=expenditures_by_year_detail,
        assessment_contributions=assessment_contributions,
        units=units,
        projection_years=projection_years,
    )

    return {
        "assumptions": assumptions,
        "assumptions_frame": assumptions_clean.reset_index(drop=True),
        "components_frame": components_clean.reset_index(drop=True),
        "assessment_frame": assessments_clean.reset_index(drop=True),
        "component_list_detail": component_list_detail,
        "expenditures_by_year_detail": expenditures_by_year_detail,
        "expenditures_by_year_summary": expenditures_by_year_summary,
        "expenditures_matrix": expenditures_matrix,
        "reserve_projection": reserve_projection,
        "statement_of_position": statement_of_position,
        "statement_of_position_formatted": statement_of_position_formatted,
    }

# %%
if __name__ == "__main__":
    assumptions = load_assumptions(ASSUMPTIONS_FILE)
    analysis_date = pd.Timestamp(assumptions["analysis_date"])
    analysis_year = analysis_date.year
    inflation = float(assumptions["inflation"])
    investment = float(assumptions["investment"])

    components_raw = load_components(COMPONENT_FILE)
    assessment_contributions = load_assessment_contributions(ASSESSMENT_FILE)

    component_list_detail = build_component_list_detail(
        components_raw,
        assumptions
    )

    output_path = WORKING_CSV / "component_list_detail.csv"
    component_list_detail.to_csv(output_path, index=False)
    print("Saved:", output_path)

    expenditures_by_year_detail = build_expenditures_by_year_detail(
        component_list_detail,
        assumptions,
        projection_years=30,
        extend_for_next_instance=True,
    )

    output_path = WORKING_CSV / "expenditures_by_year_detail.csv"
    expenditures_by_year_detail.to_csv(output_path, index=False)
    print("Saved:", output_path)

    expenditures_by_year_summary = build_expenditures_by_year_summary(
        expenditures_by_year_detail,
        projection_years=30
    )

    expenditures_by_year_summary

    output_path = WORKING_CSV / "expenditures_by_year_summary.csv"
    expenditures_by_year_summary.to_csv(output_path, index=False)
    print("Saved:", output_path)

    expenditures_matrix = build_expenditures_matrix(
        expenditures_by_year_detail,
        projection_years=30
    )

    output_path = WORKING_CSV / "expenditures_matrix.csv"
    expenditures_matrix.to_csv(output_path)
    print("Saved:", output_path)

    reserve_projection = build_reserve_projection(
        expenditures_by_year_detail=expenditures_by_year_detail,
        assumptions=assumptions,
        assessment_contributions=assessment_contributions,
        start_year=analysis_year,
        projection_years=30,
    )

    fb_end = build_funded_balance(
        component_list_detail,
        assumptions,
        projection_years=30,
        method="current_cost_straight_line",
        funded_date="end",
        respect_one_time=True,
        inflate_result=True,
    )

    reserve_projection["funded_balance"] = reserve_projection["year"].map(fb_end)
    reserve_projection["percent_funded"] = (
        reserve_projection["end_balance"] / reserve_projection["funded_balance"] * 100
    ).round(2)

    output_path = WORKING_CSV / "reserve_projection.csv"
    reserve_projection.to_csv(output_path, index=False)
    print("Saved:", output_path)

    units = 138
    statement_funded_balance = build_funded_balance(
        expenditures_by_year_detail,
        assumptions,
        projection_years=30,
        method="current_cost_straight_line",
        funded_date="analysis",
        respect_one_time=True,
        inflate_result=False,
    )

    statement_funded_amount = float(statement_funded_balance.loc[analysis_year])

    current_replacement_cost_all_components = float(component_list_detail["current_cost"].sum())
    future_replacement_cost_all_components = float(component_list_detail["future_cost"].sum())
    projected_balance_reserves = float(assumptions["begin_balance"])

    percent_funded = projected_balance_reserves / statement_funded_amount * 100
    reserve_deficit_per_unit = (statement_funded_amount - projected_balance_reserves) / units

    first_year_assessment = assessment_contributions.loc[
        assessment_contributions["year"] == analysis_year
    ].iloc[0]

    projected_reserve_contribution = (
        float(first_year_assessment["contribution"]) +
        float(first_year_assessment["special_assessment"])
    )

    avg_annual_reserve_contribution_per_unit = (
        float(first_year_assessment["contribution"]) / units
    )

    monthly_reserve_contribution_first_year = (
        float(first_year_assessment["contribution"]) / 12
    )

    avg_monthly_reserve_contribution_per_unit = (
        monthly_reserve_contribution_first_year / units
    )

    statement_of_position = pd.DataFrame(
        [
            ["Current Replacement Cost", current_replacement_cost_all_components],
            ["Future Replacement Cost", future_replacement_cost_all_components],
            ["Current Reserve Fund Balance", projected_balance_reserves],
            ["Fully Funded Reserve Balance", statement_funded_amount],
            ["Percent Funded", percent_funded],
            ["Reserve Deficit", statement_funded_amount - projected_balance_reserves],
            ["Reserve Deficit per Unit", reserve_deficit_per_unit],
            ["Projected Annual Reserve Contribution", projected_reserve_contribution],
            ["Average Annual Reserve Contribution per Unit", avg_annual_reserve_contribution_per_unit],
            ["Projected Monthly Reserve Contribution", monthly_reserve_contribution_first_year],
            ["Average Monthly Reserve Contribution per Unit", avg_monthly_reserve_contribution_per_unit],
        ],
        columns=["Metric", "Value"],
    )

    statement_of_position_formatted = format_statement_of_position(statement_of_position)

    statement_of_position.to_csv(
        WORKING_CSV / "statement_of_position.csv",
        index=False
    )

    statement_of_position_formatted.to_csv(
        WORKING_CSV / "statement_of_position_formatted.csv",
        index=False
    )

    print("Saved:", WORKING_CSV / "statement_of_position.csv")
    print("Saved:", WORKING_CSV / "statement_of_position_formatted.csv")

# %%
