from pathlib import Path
import os
import json

import pandas as pd
import streamlit as st

from reserve_plots import build_all_plots
from reserve_study_v3_3 import (
    ASSESSMENT_INPUT_COLUMNS,
    COMPONENT_INPUT_COLUMNS,
    DEFAULT_PROJECTION_YEARS,
    DEFAULT_UNITS,
    coerce_assumptions_frame,
    load_assumptions,
    prepare_assessment_input,
    prepare_components_input,
    run_reserve_study,
)


APP_ROOT = Path(__file__).resolve().parent
DEFAULT_VARIANT = os.getenv("DEFAULT_VARIANT", "2026_joint_buget_maint")
DEFAULT_SOURCE_DIR = APP_ROOT / DEFAULT_VARIANT / "source_data"
DEFAULT_ASSUMPTIONS_FILE = DEFAULT_SOURCE_DIR / "assumptions.csv"
DEFAULT_COMPONENTS_FILE = DEFAULT_SOURCE_DIR / "component_list_v2.csv"
DEFAULT_ASSESSMENT_FILE = DEFAULT_SOURCE_DIR / "assessment_contributions.csv"


def load_default_inputs():
    assumptions = (
        load_assumptions(DEFAULT_ASSUMPTIONS_FILE)
        if DEFAULT_ASSUMPTIONS_FILE.exists()
        else load_assumptions(
            pd.DataFrame(
                [
                    {"Parameter": "Analysis Date", "Value": "2026-01-01"},
                    {"Parameter": "Inflation", "Value": "0.03"},
                    {"Parameter": "Investment", "Value": "0.025"},
                    {"Parameter": "Contribution Factor", "Value": "0"},
                    {"Parameter": "Begin Balance", "Value": "0"},
                ]
            )
        )
    )
    components = (
        prepare_components_input(pd.read_csv(DEFAULT_COMPONENTS_FILE))
        if DEFAULT_COMPONENTS_FILE.exists()
        else prepare_components_input(pd.DataFrame(columns=COMPONENT_INPUT_COLUMNS))
    )
    assessments = (
        prepare_assessment_input(pd.read_csv(DEFAULT_ASSESSMENT_FILE))
        if DEFAULT_ASSESSMENT_FILE.exists()
        else prepare_assessment_input(pd.DataFrame(columns=ASSESSMENT_INPUT_COLUMNS))
    )

    return {
        "assumptions": assumptions,
        "components": components,
        "assessments": assessments,
    }


def seed_session_state(force=False):
    defaults = load_default_inputs()
    assumptions = defaults["assumptions"]

    if force or "analysis_date" not in st.session_state:
        st.session_state.pop("components_editor", None)
        st.session_state.pop("assessments_editor", None)
        st.session_state["analysis_date"] = pd.Timestamp(assumptions["analysis_date"]).date()
        st.session_state["inflation"] = float(assumptions["inflation"])
        st.session_state["investment"] = float(assumptions["investment"])
        st.session_state["contribution_factor"] = float(assumptions.get("contribution_factor", 0))
        st.session_state["begin_balance"] = float(assumptions["begin_balance"])
        st.session_state["projection_years"] = DEFAULT_PROJECTION_YEARS
        st.session_state["units"] = DEFAULT_UNITS
        st.session_state["components_frame"] = defaults["components"]
        st.session_state["assessment_frame"] = defaults["assessments"]
        st.session_state["results"] = None
        st.session_state["last_run_signature"] = None


def require_password():
    password = os.getenv("APP_PASSWORD", "")
    allow_no_password = os.getenv("ALLOW_NO_PASSWORD", "false").lower() == "true"

    if not password:
        if allow_no_password:
            st.sidebar.warning("Password bypass is enabled for local development.")
            return

        st.error("This app is not configured for public access yet. Set APP_PASSWORD before deploying.")
        st.stop()

    if st.session_state.get("authenticated"):
        return

    st.title("Ridge Park Reserve Study")
    st.caption("Enter the shared password to access the reserve-study workspace.")

    with st.form("login_form"):
        submitted_password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Unlock")

    if submit and submitted_password == password:
        st.session_state["authenticated"] = True
        st.rerun()

    if submit:
        st.error("Incorrect password.")

    st.stop()


def assumptions_frame_from_state():
    return coerce_assumptions_frame(
        pd.DataFrame(
            [
                {"Parameter": "Analysis Date", "Value": pd.Timestamp(st.session_state["analysis_date"]).strftime("%Y-%m-%d")},
                {"Parameter": "Inflation", "Value": st.session_state["inflation"]},
                {"Parameter": "Investment", "Value": st.session_state["investment"]},
                {"Parameter": "Contribution Factor", "Value": st.session_state["contribution_factor"]},
                {"Parameter": "Begin Balance", "Value": st.session_state["begin_balance"]},
            ]
        )
    )


def csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")


def matrix_csv_bytes(df):
    return df.to_csv().encode("utf-8")


def format_currency(value):
    if pd.isna(value) or value == "":
        return ""
    return f"${float(value):,.0f}"


def format_percent(value):
    if pd.isna(value) or value == "":
        return ""
    return f"{float(value):.2f}%"


def format_date(value):
    if pd.isna(value) or value == "":
        return ""
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def format_results_table(df, currency_cols=None, percent_cols=None, date_cols=None, integer_cols=None):
    out = df.copy()
    currency_cols = currency_cols or []
    percent_cols = percent_cols or []
    date_cols = date_cols or []
    integer_cols = integer_cols or []

    for col in currency_cols:
        if col in out.columns:
            out[col] = out[col].apply(format_currency)

    for col in percent_cols:
        if col in out.columns:
            out[col] = out[col].apply(format_percent)

    for col in date_cols:
        if col in out.columns:
            out[col] = out[col].apply(format_date)

    for col in integer_cols:
        if col in out.columns:
            out[col] = out[col].apply(lambda value: "" if pd.isna(value) or value == "" else str(int(float(value))))

    return out


def serialize_for_signature(value):
    if isinstance(value, pd.DataFrame):
        df = value.copy()
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype(str)
        return df.fillna("").to_dict(orient="records")
    return value


def current_input_signature():
    payload = {
        "assumptions": assumptions_frame_from_state().to_dict(orient="records"),
        "components": serialize_for_signature(st.session_state["components_frame"]),
        "assessments": serialize_for_signature(st.session_state["assessment_frame"]),
        "projection_years": int(st.session_state["projection_years"]),
        "units": int(st.session_state["units"]),
    }
    return json.dumps(payload, sort_keys=True, default=str)


def show_sidebar_tools():
    st.sidebar.header("Workspace")

    if st.sidebar.button("Reset to default inputs", use_container_width=True):
        seed_session_state(force=True)
        st.rerun()

    uploaded_components = st.sidebar.file_uploader("Replace components from CSV", type=["csv"])
    if uploaded_components is not None and st.sidebar.button("Load components CSV", use_container_width=True):
        st.session_state["components_frame"] = prepare_components_input(pd.read_csv(uploaded_components))
        st.session_state["results"] = None
        st.session_state["last_run_signature"] = None
        st.rerun()

    uploaded_assessments = st.sidebar.file_uploader("Replace assessment schedule from CSV", type=["csv"])
    if uploaded_assessments is not None and st.sidebar.button("Load assessment CSV", use_container_width=True):
        st.session_state["assessment_frame"] = prepare_assessment_input(pd.read_csv(uploaded_assessments))
        st.session_state["results"] = None
        st.session_state["last_run_signature"] = None
        st.rerun()

    st.sidebar.download_button(
        "Download current assumptions",
        data=csv_bytes(assumptions_frame_from_state()),
        file_name="assumptions.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.sidebar.download_button(
        "Download current components",
        data=csv_bytes(st.session_state["components_frame"]),
        file_name="component_list_v2.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.sidebar.download_button(
        "Download current assessments",
        data=csv_bytes(st.session_state["assessment_frame"]),
        file_name="assessment_contributions.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_inputs():
    st.title("Ridge Park Reserve Study")
    st.caption("Edit assumptions, maintain the component schedule, update annual reserve contributions, and run the study.")

    controls_col, summary_col = st.columns([2, 1])
    with controls_col:
        st.subheader("Assumptions")
        st.session_state["analysis_date"] = st.date_input("Analysis date", value=st.session_state["analysis_date"])
        inflation_percent = st.number_input(
            "Inflation rate (%)",
            min_value=0.0,
            step=0.1,
            format="%.2f",
            value=float(st.session_state["inflation"]) * 100,
        )
        investment_percent = st.number_input(
            "Investment rate (%)",
            min_value=0.0,
            step=0.1,
            format="%.2f",
            value=float(st.session_state["investment"]) * 100,
        )
        contribution_factor_percent = st.number_input(
            "Contribution factor (%)",
            step=0.1,
            format="%.2f",
            value=float(st.session_state["contribution_factor"]) * 100,
        )
        st.session_state["inflation"] = inflation_percent / 100
        st.session_state["investment"] = investment_percent / 100
        st.session_state["contribution_factor"] = contribution_factor_percent / 100
        st.session_state["begin_balance"] = st.number_input(
            "Beginning reserve balance ($)",
            min_value=0.0,
            step=1000.0,
            format="%.2f",
            value=float(st.session_state["begin_balance"]),
        )

    with summary_col:
        st.subheader("Study Settings")
        st.number_input(
            "Projection years",
            value=int(st.session_state["projection_years"]),
            disabled=True,
        )
        st.number_input(
            "Units",
            value=int(st.session_state["units"]),
            disabled=True,
        )
        st.info(
            "Adjust the parameters to the right to modify the Reserve Study Assumptions."
        )

    apply_requested = False
    run_requested = False

    with st.form("schedule_form", clear_on_submit=False):
        st.subheader("Component Schedule")
        st.caption("Edit the table below. `Run Study` will apply these edits automatically, or you can save them first without rerunning.")
        components_frame = st.data_editor(
            st.session_state["components_frame"],
            num_rows="dynamic",
            use_container_width=True,
            height=420,
            key="components_editor",
        )

        st.subheader("Assessment Schedule")
        st.caption("Edit the table below. `Run Study` will apply these edits automatically, or you can save them first without rerunning.")
        assessments_frame = st.data_editor(
            st.session_state["assessment_frame"],
            num_rows="dynamic",
            use_container_width=True,
            height=280,
            key="assessments_editor",
        )

        action_col, run_col = st.columns(2)
        with action_col:
            apply_requested = st.form_submit_button(
                "Apply Schedule Changes",
                use_container_width=True,
            )
        with run_col:
            run_requested = st.form_submit_button(
                "Run Study",
                type="primary",
                use_container_width=True,
            )

    if apply_requested or run_requested:
        st.session_state["components_frame"] = prepare_components_input(pd.DataFrame(components_frame))
        st.session_state["assessment_frame"] = prepare_assessment_input(pd.DataFrame(assessments_frame))

    if apply_requested and not run_requested:
        st.success("Schedule changes saved in this browser session. Click `Run Study` to refresh results.")

    return run_requested


def render_outputs(results):
    st.subheader("Study Results")

    raw_statement = results["statement_of_position"].set_index("Metric")["Value"]
    reserve_projection_display = format_results_table(
        results["reserve_projection"],
        currency_cols=[
            "begin_balance",
            "contribution",
            "special_assessment",
            "expenditures",
            "interest",
            "end_balance",
            "funded_balance",
        ],
        percent_cols=["percent_funded"],
        integer_cols=["year"],
    )
    expenditure_summary_display = format_results_table(
        results["expenditures_by_year_summary"],
        currency_cols=["expenditures"],
        integer_cols=["replacement_year", "component_count"],
    )
    expenditure_detail_display = format_results_table(
        results["expenditures_by_year_detail"],
        currency_cols=["current_cost", "future_cost"],
        date_cols=["replacement_date"],
        integer_cols=["component_id", "occurrence", "replacement_year", "life_months"],
    )
    component_detail_display = format_results_table(
        results["component_list_detail"],
        currency_cols=["cost", "current_cost", "future_cost"],
        date_cols=["service_date", "replacement_date"],
        integer_cols=["component_id", "life_months", "remaining_life_months"],
    )
    assessment_input_display = format_results_table(
        results["assessment_frame"],
        currency_cols=["annual_contribution", "special_assessment"],
        integer_cols=["year"],
    )

    metric_cols = st.columns(4)
    metric_cols[0].metric("Percent funded", f"{raw_statement['Percent Funded']:.2f}%")
    metric_cols[1].metric("Fully funded balance", f"${raw_statement['Fully Funded Reserve Balance']:,.0f}")
    metric_cols[2].metric("Reserve deficit", f"${raw_statement['Reserve Deficit']:,.0f}")
    metric_cols[3].metric("Annual contribution", f"${raw_statement['Projected Annual Reserve Contribution']:,.0f}")

    tabs = st.tabs(
        [
            "Statement",
            "Plots",
            "Reserve Projection",
            "Expenditure Detail",
            "Year Summary",
            "Component Detail",
            "Assessment Input",
        ]
    )

    with tabs[0]:
        st.dataframe(results["statement_of_position_formatted"], use_container_width=True, hide_index=True)
        st.download_button(
            "Download statement of position",
            data=csv_bytes(results["statement_of_position"]),
            file_name="statement_of_position.csv",
            mime="text/csv",
        )

    with tabs[1]:
        for title, figure in build_all_plots(results):
            st.markdown(f"#### {title}")
            st.pyplot(figure, use_container_width=True)

    with tabs[2]:
        st.dataframe(reserve_projection_display, use_container_width=True, hide_index=True)
        st.download_button(
            "Download reserve projection",
            data=csv_bytes(results["reserve_projection"]),
            file_name="reserve_projection.csv",
            mime="text/csv",
        )

    with tabs[3]:
        st.dataframe(expenditure_detail_display, use_container_width=True, hide_index=True)
        st.download_button(
            "Download expenditure detail",
            data=csv_bytes(results["expenditures_by_year_detail"]),
            file_name="expenditures_by_year_detail.csv",
            mime="text/csv",
        )

    with tabs[4]:
        st.dataframe(expenditure_summary_display, use_container_width=True, hide_index=True)
        st.download_button(
            "Download year summary",
            data=csv_bytes(results["expenditures_by_year_summary"]),
            file_name="expenditures_by_year_summary.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download expenditures matrix",
            data=matrix_csv_bytes(results["expenditures_matrix"]),
            file_name="expenditures_matrix.csv",
            mime="text/csv",
        )

    with tabs[5]:
        st.dataframe(component_detail_display, use_container_width=True, hide_index=True)
        st.download_button(
            "Download component detail",
            data=csv_bytes(results["component_list_detail"]),
            file_name="component_list_detail.csv",
            mime="text/csv",
        )

    with tabs[6]:
        st.dataframe(assessment_input_display, use_container_width=True, hide_index=True)
        st.download_button(
            "Download assessment input",
            data=csv_bytes(results["assessment_frame"]),
            file_name="assessment_contributions.csv",
            mime="text/csv",
        )


def main():
    st.set_page_config(page_title="Reserve Study", layout="wide")
    seed_session_state()
    require_password()
    show_sidebar_tools()

    run_requested = render_inputs()
    input_signature = current_input_signature()

    if run_requested:
        try:
            st.session_state["results"] = run_reserve_study(
                assumptions_frame=assumptions_frame_from_state(),
                components_frame=st.session_state["components_frame"],
                assessment_frame=st.session_state["assessment_frame"],
                projection_years=st.session_state["projection_years"],
                units=st.session_state["units"],
            )
            st.session_state["last_run_signature"] = input_signature
        except Exception as exc:
            st.error(f"Study run failed: {exc}")
            st.exception(exc)

    has_results = st.session_state.get("results") is not None
    is_dirty = st.session_state.get("last_run_signature") != input_signature

    if has_results and is_dirty:
        st.info("Inputs have changed. Click `Run Study` to refresh the results.")

    if has_results and not is_dirty:
        render_outputs(st.session_state["results"])


if __name__ == "__main__":
    main()
