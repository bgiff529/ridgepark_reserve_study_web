from pathlib import Path
from io import BytesIO
from html import escape
import os
import json
import sys

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from reserve_plots import build_all_plots
from reserve_study_web_adapter import (
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


DEFAULT_VARIANT = os.getenv("DEFAULT_VARIANT", "2026_joint_buget_maint")
DEFAULT_SOURCE_DIR = PROJECT_ROOT / DEFAULT_VARIANT / "source_data"
DEFAULT_ASSUMPTIONS_FILE = DEFAULT_SOURCE_DIR / "assumptions.csv"
DEFAULT_COMPONENTS_FILE = DEFAULT_SOURCE_DIR / "component_list_v2.csv"
DEFAULT_ASSESSMENT_FILE = DEFAULT_SOURCE_DIR / "assessment_contributions.csv"
UI_TABS = [
    "Components",
    "Control Panel",
    "Recommendations",
    "Funding Plan Override",
    "Tables and Charts",
]


APP_CSS = """
<style>
    :root {
        --rp-navy: #1f3140;
        --rp-navy-dark: #182836;
        --rp-teal: #2d8599;
        --rp-blue-row: #c5e5f1;
        --rp-page: #f3f5f7;
        --rp-line: #e3e7eb;
        --rp-green: #72d957;
        --rp-green-dark: #46b737;
    }
    .stApp {
        background: var(--rp-page);
        color: #4b5563;
    }
    section[data-testid="stSidebar"] {
        width: 238px !important;
        min-width: 238px !important;
        background: var(--rp-navy);
        border-right: 1px solid #10202b;
    }
    section[data-testid="stSidebar"] > div {
        background: var(--rp-navy);
        padding-top: 1.3rem;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span {
        color: #eaf2f6 !important;
    }
    div[data-testid="stAppViewContainer"] .main .block-container {
        max-width: 1180px;
        padding: 1.1rem 1.8rem 3rem 1.8rem;
    }
    header[data-testid="stHeader"] {
        background: #ffffff;
        border-bottom: 1px solid var(--rp-line);
    }
    .rp-shell-top {
        height: 50px;
        background: #fff;
        border-bottom: 1px solid var(--rp-line);
        margin: -1.1rem -1.8rem 1.6rem -1.8rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 1.25rem;
        color: #71808a;
        font-size: 12px;
    }
    .rp-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 700;
        letter-spacing: .04em;
        color: #6696a2;
        text-transform: uppercase;
        line-height: 1;
    }
    .rp-logo-mark {
        width: 34px;
        height: 34px;
        background: linear-gradient(135deg, #1e6f82 0 58%, #b7d85b 58% 100%);
        border-radius: 2px;
        box-shadow: inset 0 0 0 4px #fff;
        border: 1px solid #d5dde2;
    }
    .rp-project-card {
        margin: 0 auto;
        max-width: 1110px;
        background: #fff;
        border: 1px solid var(--rp-line);
        box-shadow: 0 1px 2px rgba(31,49,64,.08);
    }
    .rp-project-banner {
        min-height: 176px;
        background: var(--rp-navy);
        border: 1px solid #0d1921;
        position: relative;
    }
    .rp-avatar {
        position: absolute;
        left: 16px;
        bottom: -36px;
        width: 112px;
        height: 112px;
        background: #f7f8fa;
        border: 4px solid white;
        box-shadow: 0 1px 4px rgba(0,0,0,.22);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #c7cbd0;
        font-size: 54px;
    }
    .rp-project-title {
        position: absolute;
        left: 138px;
        bottom: 20px;
        color: white;
        font-weight: 700;
        font-size: 20px;
        line-height: 1.2;
    }
    .rp-project-title span {
        display: block;
        font-size: 11px;
        font-weight: 600;
        color: #d8e1e7;
    }
    .rp-project-subtabs {
        height: 38px;
        padding-left: 136px;
        display: flex;
        align-items: stretch;
        gap: 0;
    }
    .rp-project-subtabs span {
        border-left: 1px solid var(--rp-line);
        border-right: 1px solid var(--rp-line);
        padding: 12px 20px 0 20px;
        color: #6aa6b8;
        font-size: 12px;
        font-weight: 700;
    }
    .rp-cost-row {
        max-width: 1110px;
        margin: 18px auto 8px auto;
        display: flex;
        align-items: center;
        justify-content: space-between;
        color: #75838d;
        font-size: 12px;
    }
    .rp-select-pill {
        background: #4bb4d4;
        color: white;
        padding: 4px 8px;
        border-radius: 2px;
        font-weight: 700;
        margin-left: 6px;
    }
    .rp-tutorial {
        background: var(--rp-green);
        color: #287a29;
        font-weight: 700;
        padding: 6px 12px;
        border-radius: 3px;
    }
    .rp-tabs {
        max-width: 1110px;
        margin: 8px auto 20px auto;
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        text-align: center;
        gap: 18px;
    }
    .rp-tab {
        color: #7f8991;
        text-transform: uppercase;
        font-weight: 700;
        font-size: 12px;
        padding: 13px 4px 12px 4px;
        border-bottom: 2px solid transparent;
        white-space: nowrap;
    }
    .rp-tab.active {
        color: #3d7f98;
        border-bottom-color: #9ec3d2;
    }
    .rp-panel {
        max-width: 1110px;
        margin: 0 auto;
        background: #fff;
        border: 1px solid var(--rp-line);
        box-shadow: 0 1px 2px rgba(31,49,64,.06);
        padding: 14px 16px 28px 16px;
    }
    .rp-toolbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .rp-green-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 32px;
        height: 26px;
        background: var(--rp-green);
        color: #1f7b21;
        border-radius: 4px;
        border: 1px solid #8ee06f;
        font-weight: 800;
        font-size: 13px;
        margin-left: 5px;
        padding: 0 10px;
    }
    .rp-components-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
        color: #65717a;
    }
    .rp-components-table th {
        background: #fff;
        border: 1px solid #e5e8eb;
        padding: 10px 8px;
        color: #5f6870;
        font-weight: 700;
        text-align: left;
    }
    .rp-components-table td {
        border: 1px solid #edf0f2;
        padding: 9px 8px;
        background: #fff;
        vertical-align: middle;
    }
    .rp-components-table tr.selected td {
        background: #b7b7b7;
        color: #3d3d3d;
    }
    .rp-components-table tr.group td {
        background: var(--rp-blue-row);
        color: #42535f;
        font-weight: 700;
        padding: 8px;
    }
    .rp-funded {
        display: inline-block;
        border: 1px solid #d7dde2;
        border-radius: 3px;
        padding: 2px 8px;
        background: #fafafa;
        color: #69747c;
    }
    .rp-row-actions {
        color: #2b6f9c;
        font-weight: 700;
        white-space: nowrap;
    }
    .rp-native-editor {
        margin-top: 18px;
        border-top: 1px solid var(--rp-line);
        padding-top: 16px;
    }
    .rp-native-editor h4 {
        margin: 0 0 8px 0;
        color: #57636c;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: .05em;
    }
    .rp-editor-shell {
        max-width: 1110px;
        margin: 0 auto 24px auto;
        background: #fff;
        border-left: 1px solid var(--rp-line);
        border-right: 1px solid var(--rp-line);
        border-bottom: 1px solid var(--rp-line);
        padding: 0 16px 22px 16px;
    }
    .rp-small-note {
        color: #7f8b94;
        font-size: 12px;
        margin: 2px 0 12px 0;
    }
    div.stButton > button,
    div.stDownloadButton > button {
        background: var(--rp-green);
        color: #1f7b21;
        border: 1px solid #8ee06f;
        border-radius: 4px;
        min-height: 30px;
        font-weight: 700;
    }
    div.stButton > button:hover,
    div.stDownloadButton > button:hover {
        border-color: var(--rp-green-dark);
        color: #0f6c18;
    }
</style>
"""


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


def inject_styles():
    st.markdown(APP_CSS, unsafe_allow_html=True)


def render_sidebar_shell():
    st.sidebar.markdown(
        """
        <div style="text-align:center;font-size:16px;font-weight:700;margin-bottom:18px;">Client Center</div>
        <div style="background:#192936;margin:0 -16px 12px -16px;padding:12px 16px;font-weight:700;font-size:12px;">Dashboard</div>
        <div style="display:flex;gap:6px;margin-bottom:18px;">
            <span style="background:#f28b30;color:#152531;padding:3px 6px;border-radius:2px;font-weight:700;">rss</span>
            <span style="background:#4ba4d9;color:white;padding:3px 6px;border-radius:2px;font-weight:700;">t</span>
            <span style="background:#4169a8;color:white;padding:3px 6px;border-radius:2px;font-weight:700;">f</span>
            <span style="background:#d84b35;color:white;padding:3px 6px;border-radius:2px;font-weight:700;">in</span>
        </div>
        <div style="border:1px solid #7d93a3;padding:8px;font-weight:700;font-size:12px;">Latest updates</div>
        """,
        unsafe_allow_html=True,
    )


def render_project_shell(active_tab: str = "Components"):
    tabs = "".join(
        f'<div class="rp-tab {"active" if tab == active_tab else ""}">{tab}</div>'
        for tab in UI_TABS
    )
    st.markdown(
        f"""
        <div class="rp-shell-top">
            <div class="rp-brand"><div class="rp-logo-mark"></div><div>Ridge Park<br>Reserves</div></div>
            <div>Demonstration User</div>
        </div>
        <div class="rp-project-card">
            <div class="rp-project-banner">
                <div class="rp-avatar">●</div>
                <div class="rp-project-title">Ridge Park Reserve Study<span>Project workspace</span></div>
            </div>
            <div class="rp-project-subtabs"><span>Documents</span><span>uPlanIt</span></div>
        </div>
        <div class="rp-cost-row">
            <div>Cost Centers:<span class="rp-select-pill">⌄</span></div>
            <div class="rp-tutorial">Video Overview (3:22)</div>
        </div>
        <div class="rp-tabs">{tabs}</div>
        """,
        unsafe_allow_html=True,
    )


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


def figure_png_bytes(figure):
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=160, bbox_inches="tight")
    plt.close(figure)
    buffer.seek(0)
    return buffer


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


def component_table_html(components_frame: pd.DataFrame, chapter: str) -> str:
    frame = prepare_components_input(components_frame)
    if chapter != "ALL":
        frame = frame.loc[frame["category"] == chapter].copy()

    rows = []
    current_category = None
    selected_position = min(8, max(len(frame) - 1, 0))
    for display_index, (_, row) in enumerate(frame.head(80).iterrows(), start=1):
        category = str(row.get("category", "") or "Uncategorized")
        if category != current_category:
            current_category = category
            rows.append(
                f"""
                <tr class="group">
                    <td colspan="8">{escape(category)} <span style="margin-left:16px;background:#fff;border:1px solid #dfe7ec;padding:3px 9px;">+ Add component</span></td>
                    <td class="rp-row-actions">✎ 🗑 ⬆</td>
                </tr>
                """
            )

        selected_class = "selected" if display_index - 1 == selected_position else ""
        quantity = f"{float(row['quantity']):,.0f} {escape(str(row['quantity_units']))}" if pd.notna(row["quantity"]) else ""
        cost = format_currency(row["cost"] * row["quantity"])
        rows.append(
            f"""
            <tr class="{selected_class}">
                <td style="text-align:right;">{display_index * 25}</td>
                <td><span class="rp-funded">Yes⌄</span></td>
                <td>{escape(str(row["component"]))}</td>
                <td>{quantity}</td>
                <td style="text-align:right;">{float(row["life_years"]):.0f}</td>
                <td style="text-align:right;">{escape(str(row["remaining_life"]))}</td>
                <td style="text-align:right;">{cost}</td>
                <td>{escape(str(row.get("source_page", "")))}</td>
                <td class="rp-row-actions">✎ &nbsp; 🗑</td>
            </tr>
            """
        )

    if not rows:
        rows.append('<tr><td colspan="9" style="height:180px;text-align:center;color:#9aa4ac;">No components in this chapter.</td></tr>')

    return f"""
    <div class="rp-panel">
        <div class="rp-toolbar">
            <div>Chapters: <span style="display:inline-block;min-width:160px;border:1px solid #dfe5e9;padding:4px 10px;background:#fff;">{escape(chapter)} ▾</span></div>
            <div>
                <span class="rp-green-btn">View Tutorial (4:29)</span>
                <span class="rp-green-btn">⬆</span>
                <span class="rp-green-btn">＋</span>
                <span class="rp-green-btn">↻</span>
                <span class="rp-green-btn">▣</span>
                <span class="rp-green-btn">▤</span>
            </div>
        </div>
        <table class="rp-components-table">
            <thead>
                <tr>
                    <th style="width:7%;text-align:right;">#</th>
                    <th style="width:7%;">Funded</th>
                    <th style="width:23%;">Component Name</th>
                    <th style="width:17%;">Quantity/Specs</th>
                    <th style="width:6%;text-align:right;">UL</th>
                    <th style="width:6%;text-align:right;">RUL</th>
                    <th style="width:9%;text-align:right;">Current<br>Cost</th>
                    <th>Notes</th>
                    <th style="width:9%;">Options</th>
                </tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
    </div>
    """


def render_component_workspace() -> bool:
    render_project_shell("Components")
    frame = st.session_state["components_frame"]
    categories = ["ALL"] + sorted([str(value) for value in frame["category"].dropna().unique() if str(value).strip()])
    chapter = st.selectbox("Chapters", categories, label_visibility="collapsed", key="component_chapter")
    st.markdown(component_table_html(frame, chapter), unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="rp-editor-shell">', unsafe_allow_html=True)
        st.markdown('<div class="rp-native-editor"><h4>Edit Component Schedule</h4></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="rp-small-note">Use this editable grid for now; the table above previews the denser component workspace style.</div>',
            unsafe_allow_html=True,
        )

        uploaded_components = st.file_uploader(
            "Import component CSV",
            type=["csv"],
            help="Upload a component_list_v2-style CSV to replace the current component schedule.",
        )
        upload_col, download_col, reset_col = st.columns([1, 1, 1])
        with upload_col:
            if uploaded_components is not None and st.button("Load imported components", use_container_width=True):
                st.session_state["components_frame"] = prepare_components_input(pd.read_csv(uploaded_components))
                st.session_state["results"] = None
                st.session_state["last_run_signature"] = None
                st.rerun()
        with download_col:
            st.download_button(
                "Download components",
                data=csv_bytes(st.session_state["components_frame"]),
                file_name="component_list_v2.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with reset_col:
            if st.button("Reset components", use_container_width=True):
                defaults = load_default_inputs()
                st.session_state["components_frame"] = defaults["components"]
                st.session_state["results"] = None
                st.session_state["last_run_signature"] = None
                st.rerun()

        apply_requested = False
        run_requested = False
        with st.form("components_form", clear_on_submit=False):
            components_frame = st.data_editor(
                st.session_state["components_frame"],
                num_rows="dynamic",
                use_container_width=True,
                height=420,
                key="components_editor",
            )
            action_col, run_col = st.columns(2)
            with action_col:
                apply_requested = st.form_submit_button("Apply Component Changes", use_container_width=True)
            with run_col:
                run_requested = st.form_submit_button("Run Study", type="primary", use_container_width=True)

        if apply_requested or run_requested:
            st.session_state["components_frame"] = prepare_components_input(pd.DataFrame(components_frame))

        if apply_requested and not run_requested:
            st.success("Component changes saved in this browser session. Click Run Study to refresh results.")

        st.markdown("</div>", unsafe_allow_html=True)

    return run_requested


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
            st.image(figure_png_bytes(figure), use_container_width=True)

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
    inject_styles()
    seed_session_state()
    require_password()
    render_sidebar_shell()
    if st.sidebar.button("Reset workspace", use_container_width=True):
        seed_session_state(force=True)
        st.rerun()

    run_requested = render_component_workspace()
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
