from pathlib import Path
from io import BytesIO
from html import escape
import os
import json
import sys

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import streamlit.components.v1 as components
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

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
        justify-content: flex-start;
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
    .rp-upload-card {
        border: 1px solid var(--rp-line);
        background: #fff;
        padding: 14px;
        margin: 8px 0 16px 0;
    }
    .rp-upload-title {
        background: var(--rp-teal);
        color: white;
        font-weight: 700;
        padding: 9px 12px;
        margin: -14px -14px 14px -14px;
    }
    .rp-upload-row {
        display: flex;
        align-items: center;
        gap: 10px;
        color: #6a7580;
        font-size: 13px;
    }
    .rp-upload-icon {
        display: inline-flex;
        width: 34px;
        height: 26px;
        align-items: center;
        justify-content: center;
        background: var(--rp-green);
        color: #1f7b21;
        border-radius: 4px;
        border: 1px solid #8ee06f;
        font-weight: 800;
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


def component_template_bytes():
    workbook = Workbook()
    instructions = workbook.active
    instructions.title = "Instructions"
    component_sheet = workbook.create_sheet("Component List")

    teal = PatternFill("solid", fgColor="2D8599")
    yellow = PatternFill("solid", fgColor="FFF6A5")
    section_yellow = PatternFill("solid", fgColor="FFF13B")
    blue = PatternFill("solid", fgColor="A7C9EA")
    thin_gray = Side(style="thin", color="8C8C8C")
    border = Border(left=thin_gray, right=thin_gray, top=thin_gray, bottom=thin_gray)

    instructions.column_dimensions["A"].width = 8
    instructions.column_dimensions["B"].width = 32
    instructions.column_dimensions["C"].width = 38
    instructions.column_dimensions["D"].width = 32
    instructions["B2"] = "RIDGE PARK"
    instructions["B2"].font = Font(size=24, bold=True, color="2D8599")
    instructions["C2"] = "RESERVES"
    instructions["C2"].font = Font(size=24, bold=True, color="2D8599")
    instructions["B5"] = "Master Template for Component List Import"
    instructions["B5"].font = Font(italic=True, color="666666")
    instructions["A8"] = "If you wish to import your own Reserve Component List, this is the starting point!"
    instructions["A8"].font = Font(size=14, bold=True)
    instructions["B11"] = "Note: This file contains two worksheet tabs along the bottom: Instructions and Component List"

    sections = [
        (13, "Instructions"),
        (20, "Tips & Techniques"),
        (31, "Component Guidance"),
    ]
    for row, label in sections:
        instructions.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
        cell = instructions.cell(row=row, column=1, value=label)
        cell.fill = section_yellow
        cell.font = Font(size=14, bold=True)
        cell.alignment = Alignment(horizontal="center")
        cell.border = border

    instruction_lines = [
        (15, '* Enter your component information in the shaded rows and columns on the "Component List" worksheet.'),
        (16, "* Useful Life (UL) and Remaining Useful Life (RUL) must be non-negative numbers."),
        (17, "* Current Cost must be a non-negative number."),
        (22, "* Data will be imported starting with component #1."),
        (23, "* A blank Component Description field is interpreted as the end of your data."),
        (24, "* A blank Quantity field may remain blank."),
        (25, "* A blank Useful Life field causes RUL and Current Cost to be ignored."),
        (26, "* Components to be replaced in the initial year should have RUL = 0."),
        (27, "* Current Cost is already formatted as currency, so no $ symbol is required."),
        (33, '#1 Be a common-area maintenance responsibility of the Association.'),
        (34, '#2 Have a limited Useful Life (UL), not the life of the building.'),
        (35, "#3 Have a predictable Remaining Useful Life (RUL)."),
        (36, "#4 Be above a minimum threshold cost."),
    ]
    for row, text in instruction_lines:
        instructions.cell(row=row, column=1, value=text)

    headers = ["#", "Component #", "Funded (Yes/No)", "Component Description", "Quantity", "UL", "RUL", "Current Cost", "Notes"]
    for column_index, header in enumerate(headers, start=1):
        cell = component_sheet.cell(row=2, column=column_index, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
        cell.border = border
    component_sheet.cell(row=3, column=1, value="Title").font = Font(bold=True)
    component_sheet.cell(row=3, column=2, value="General Common Areas").font = Font(bold=True)
    for col in range(2, 10):
        component_sheet.cell(row=3, column=col).fill = blue
        component_sheet.cell(row=3, column=col).border = border

    for row in range(4, 84):
        component_sheet.cell(row=row, column=1, value=row - 3)
        component_sheet.cell(row=row, column=3, value="Yes")
        for col in range(1, 10):
            cell = component_sheet.cell(row=row, column=col)
            if 2 <= col <= 9:
                cell.fill = yellow
            cell.border = border
        component_sheet.cell(row=row, column=8).number_format = "$#,##0"

    widths = [8, 16, 22, 38, 22, 9, 9, 18, 28]
    for index, width in enumerate(widths, start=1):
        component_sheet.column_dimensions[chr(64 + index)].width = width
    component_sheet.freeze_panes = "A4"

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def _clean_template_value(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def _template_number(value, default=0.0):
    if pd.isna(value) or value == "":
        return default
    text = str(value).strip().replace("$", "").replace(",", "")
    if ":" in text:
        text = text.split(":", 1)[0]
    try:
        return float(text)
    except ValueError:
        return default


def _parse_quantity(value):
    text = _clean_template_value(value)
    if not text:
        return 1.0, "Allow"
    parts = text.replace(",", "").split()
    try:
        quantity = float(parts[0])
        units = " ".join(parts[1:]).strip() or "Each"
        return quantity, units
    except (ValueError, IndexError):
        return 1.0, text


def _normalize_template_columns(columns):
    normalized = {}
    for column in columns:
        key = str(column).strip().lower().replace("\n", " ")
        key = " ".join(key.split())
        normalized[key] = column
    return normalized


def components_from_template_frame(raw_frame: pd.DataFrame) -> pd.DataFrame:
    frame = raw_frame.dropna(how="all").copy()
    if frame.empty:
        return prepare_components_input(pd.DataFrame(columns=COMPONENT_INPUT_COLUMNS))

    header_index = None
    for index, row in frame.iterrows():
        values = [str(value).strip().lower() for value in row.tolist()]
        if "component description" in values or "component name" in values:
            header_index = index
            break
    if header_index is None:
        raise ValueError('Could not find a "Component Description" header in the uploaded template.')

    headers = [str(value).strip() for value in frame.loc[header_index].tolist()]
    data = frame.loc[header_index + 1 :].copy()
    data.columns = headers
    columns = _normalize_template_columns(data.columns)

    component_col = columns.get("component description") or columns.get("component name")
    if component_col is None:
        raise ValueError('The template must include a "Component Description" or "Component Name" column.')

    category = "Imported Components"
    rows = []
    for _, row in data.iterrows():
        marker = _clean_template_value(row.get("#", ""))
        component_number = _clean_template_value(row.get(columns.get("component #", ""), ""))
        description = _clean_template_value(row.get(component_col, ""))

        if marker.lower() == "title":
            category = component_number or description or category
            continue
        if not description:
            continue

        funded = _clean_template_value(row.get(columns.get("funded (yes/no)", ""), "")) or "Yes"
        if funded.lower().startswith("n"):
            continue

        quantity, quantity_units = _parse_quantity(row.get(columns.get("quantity", ""), ""))
        life_years = _template_number(row.get(columns.get("ul", ""), 0))
        remaining_life_years = _template_number(row.get(columns.get("rul", ""), 0))
        current_cost = _template_number(row.get(columns.get("current cost", ""), 0))
        unit_cost = current_cost / quantity if quantity else current_cost

        rows.append(
            {
                "category": category,
                "subcategory": "",
                "component": description,
                "tracking": "Imported",
                "method": "Fixed",
                "cost": unit_cost,
                "cost_units": quantity_units,
                "quantity": quantity,
                "quantity_units": quantity_units,
                "life_years": life_years,
                "remaining_life": f"{int(remaining_life_years)}:00",
                "service_date": "",
                "source_page": _clean_template_value(row.get(columns.get("notes", ""), "")),
            }
        )

    return prepare_components_input(pd.DataFrame(rows, columns=COMPONENT_INPUT_COLUMNS))


def load_component_upload(uploaded_file) -> pd.DataFrame:
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(uploaded_file)
        if set(COMPONENT_INPUT_COLUMNS).issubset(frame.columns):
            return prepare_components_input(frame)
        return components_from_template_frame(frame)
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return components_from_template_frame(pd.read_excel(uploaded_file, sheet_name="Component List", header=None))
    raise ValueError("Upload a native component CSV or the Excel template downloaded from this page.")


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
    <style>
        :root {{
            --rp-blue-row: #c5e5f1;
            --rp-line: #e3e7eb;
            --rp-green: #72d957;
        }}
        body {{
            margin: 0;
            background: #fff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #65717a;
        }}
        .rp-panel {{
            background: #fff;
            border: 1px solid var(--rp-line);
            box-shadow: 0 1px 2px rgba(31,49,64,.06);
            padding: 14px 16px 28px 16px;
            box-sizing: border-box;
        }}
        .rp-toolbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            font-size: 12px;
        }}
        .rp-green-btn {{
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
            box-sizing: border-box;
        }}
        .rp-components-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            color: #65717a;
        }}
        .rp-components-table th {{
            background: #fff;
            border: 1px solid #e5e8eb;
            padding: 10px 8px;
            color: #5f6870;
            font-weight: 700;
            text-align: left;
        }}
        .rp-components-table td {{
            border: 1px solid #edf0f2;
            padding: 9px 8px;
            background: #fff;
            vertical-align: middle;
        }}
        .rp-components-table tr.selected td {{
            background: #b7b7b7;
            color: #3d3d3d;
        }}
        .rp-components-table tr.group td {{
            background: var(--rp-blue-row);
            color: #42535f;
            font-weight: 700;
            padding: 8px;
        }}
        .rp-funded {{
            display: inline-block;
            border: 1px solid #d7dde2;
            border-radius: 3px;
            padding: 2px 8px;
            background: #fafafa;
            color: #69747c;
        }}
        .rp-row-actions {{
            color: #2b6f9c;
            font-weight: 700;
            white-space: nowrap;
        }}
    </style>
    <div class="rp-panel">
        <div class="rp-toolbar">
            <div>Chapters: <span style="display:inline-block;min-width:160px;border:1px solid #dfe5e9;padding:4px 10px;background:#fff;">{escape(chapter)} ▾</span></div>
            <div>
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
    components.html(component_table_html(frame, chapter), height=720, scrolling=True)

    with st.container():
        st.markdown('<div class="rp-editor-shell">', unsafe_allow_html=True)
        st.markdown('<div class="rp-native-editor"><h4>Edit Component Schedule</h4></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="rp-small-note">Use this editable grid for now; the table above previews the denser component workspace style.</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="rp-upload-card">
                <div class="rp-upload-title">Upload</div>
                <div class="rp-upload-row">
                    <span class="rp-upload-icon">⬆</span>
                    <span>Import components using only the downloadable template, or load the native component CSV.</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        template_col, file_col, load_col = st.columns([1.15, 1.85, 1])
        with template_col:
            st.download_button(
                "THIS template",
                data=component_template_bytes(),
                file_name="ridge_park_component_import_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help='Download the Excel workbook with "Instructions" and "Component List" tabs.',
                use_container_width=True,
            )
        with file_col:
            uploaded_components = st.file_uploader(
                "Upload completed template or native CSV",
                type=["csv", "xlsx", "xlsm", "xls"],
                help='Upload the completed Excel template, or a native component_list_v2.csv file.',
            )
        with load_col:
            st.write("")
            st.write("")
            load_import = st.button("Load import", use_container_width=True, disabled=uploaded_components is None)

        if uploaded_components is not None and load_import:
            try:
                st.session_state["components_frame"] = load_component_upload(uploaded_components)
                st.session_state["results"] = None
                st.session_state["last_run_signature"] = None
                st.success("Component import loaded.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not import components: {exc}")

        st.markdown('<div class="rp-small-note">Native CSV imports still work for component_list_v2.csv compatibility.</div>', unsafe_allow_html=True)

        download_col, reset_col = st.columns([1, 1])
        with download_col:
            st.download_button(
                "Download native CSV",
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
    st.set_page_config(page_title="Reserve Study", layout="wide", initial_sidebar_state="collapsed")
    inject_styles()
    seed_session_state()
    require_password()

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
