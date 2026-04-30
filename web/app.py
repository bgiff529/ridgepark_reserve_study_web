from pathlib import Path
from io import BytesIO
from html import escape
import base64
import os
import json
import sys
import shutil
import subprocess
import tempfile
import re

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import streamlit.components.v1 as components
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

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
    .rp-tabs {
        max-width: 1110px;
        margin: 18px auto 20px auto;
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
    .rp-native-toolbar {
        max-width: 1110px;
        margin: 0 auto;
        background: #fff;
        border: 1px solid var(--rp-line);
        border-bottom: 0;
        padding: 14px 16px 8px 16px;
    }
    .rp-native-toolbar [data-testid="stHorizontalBlock"] {
        align-items: center;
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
    .rp-components-table tbody tr:not(.group):hover td {
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
    .rp-icon-button button {
        min-width: 34px;
        padding-left: 0.4rem;
        padding-right: 0.4rem;
    }
    .rp-native-component-header {
        display: grid;
        grid-template-columns: 1.2fr 2.2fr 1.25fr 1fr 1fr 1fr 1.15fr .75fr .9fr 2.2fr 1.1fr;
        gap: 4px;
        align-items: center;
        background: #fff;
        border: 1px solid #e5e8eb;
        color: #5f6870;
        font-size: 12px;
        font-weight: 700;
        padding: 8px 7px;
        position: sticky;
        top: 0;
        z-index: 6;
    }
    .rp-category-strip,
    .rp-category-fill {
        background: var(--rp-blue-row);
        color: #42535f;
        min-height: 28px;
        padding: 6px 8px;
        box-sizing: border-box;
        font-weight: 700;
        border-top: 1px solid #e5e8eb;
        border-bottom: 1px solid #e5e8eb;
    }
    .rp-category-fill {
        color: transparent;
    }
    .rp-component-cell {
        min-height: 28px;
        background: #fff;
        border-bottom: 1px solid #edf0f2;
        color: #65717a;
        font-size: 12px;
        padding: 6px 2px;
        overflow-wrap: anywhere;
        box-sizing: border-box;
    }
    div[data-testid="stHorizontalBlock"]:has(.rp-component-cell):hover .rp-component-cell {
        background: #b7b7b7;
        color: #3d3d3d;
    }
    .rp-editing-note {
        background: #b7b7b7;
        color: #3d3d3d;
        font-size: 12px;
        font-weight: 600;
        padding: 2px 8px;
        border-top: 1px solid #a9a9a9;
    }
    div[data-testid="stHorizontalBlock"]:has(.rp-component-cell) {
        gap: 0.25rem;
    }
    div[data-testid="stHorizontalBlock"]:has(.rp-editing-row-marker),
    div[data-testid="stHorizontalBlock"]:has(.rp-category-edit-row-marker) {
        background: #b7b7b7;
        padding: 2px 0;
    }
    div[data-testid="stHorizontalBlock"]:has(.rp-editing-row-marker) input,
    div[data-testid="stHorizontalBlock"]:has(.rp-editing-row-marker) [data-baseweb="select"] > div,
    div[data-testid="stHorizontalBlock"]:has(.rp-category-edit-row-marker) input {
        min-height: 28px;
        height: 28px;
        font-size: 12px;
        color: #3d3d3d;
        background: #f5f5f5;
        border-color: #d8d8d8;
    }
    div[data-testid="stHorizontalBlock"]:has(.rp-editing-row-marker) div[data-testid="stTextInput"],
    div[data-testid="stHorizontalBlock"]:has(.rp-editing-row-marker) div[data-testid="stNumberInput"],
    div[data-testid="stHorizontalBlock"]:has(.rp-editing-row-marker) div[data-testid="stSelectbox"],
    div[data-testid="stHorizontalBlock"]:has(.rp-category-edit-row-marker) div[data-testid="stTextInput"] {
        margin-bottom: 0;
    }
    div[data-testid="stHorizontalBlock"]:has(.rp-editing-row-marker) button,
    div[data-testid="stHorizontalBlock"]:has(.rp-category-edit-row-marker) button {
        min-width: 24px;
        min-height: 24px;
        padding: 0 4px;
        background: transparent;
        border: 0;
        color: #d82020;
        font-size: 14px;
        font-weight: 600;
        box-shadow: none;
    }
    div[data-testid="stHorizontalBlock"]:has(.rp-editing-row-marker) button:hover,
    div[data-testid="stHorizontalBlock"]:has(.rp-category-edit-row-marker) button:hover {
        color: #b10000;
        background: #f6e0e0;
        border: 0;
    }
    div[data-testid="stHorizontalBlock"]:has(.rp-component-cell) button,
    div[data-testid="stHorizontalBlock"]:has(.rp-category-strip) button {
        min-width: 24px;
        min-height: 24px;
        padding: 0 4px;
        background: transparent;
        border: 0;
        color: #2b6f9c;
        font-size: 14px;
        font-weight: 600;
        box-shadow: none;
    }
    div[data-testid="stHorizontalBlock"]:has(.rp-category-strip) button {
        background: #fff;
        border: 1px solid #dfe7ec;
        color: #42535f;
        font-size: 12px;
        min-height: 24px;
        padding: 0 8px;
    }
    div[data-testid="stHorizontalBlock"]:has(.rp-component-cell) button:hover,
    div[data-testid="stHorizontalBlock"]:has(.rp-category-strip) button:hover {
        color: #1e567d;
        background: #eef5f8;
        border: 0;
    }
    .rp-empty-table {
        min-height: 180px;
        background: #fff;
        border: 1px solid #edf0f2;
        color: #9aa4ac;
        text-align: center;
        padding: 70px 0;
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
        st.session_state["editing_component_index"] = None
        st.session_state["editing_category"] = None
        st.session_state["moving_component_index"] = None
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
        (16, '* Method must be either "One Time" or "Repeating". Anything else imports as Repeating.'),
        (17, '* Remaining Useful Life must use yy:mm format, such as 0:06 or 14:00.'),
        (22, "* Data will be imported from the shaded rows."),
        (23, "* A blank Component field is interpreted as the end of your data."),
        (24, "* Quantity and Cost are separate numeric fields; units are separate text fields."),
        (25, "* Components to be replaced in the initial year should have Remaining Useful Life = 0:00."),
        (26, "* Use Notes for source page references and other supporting detail."),
        (33, '#1 Be a common-area maintenance responsibility of the Association.'),
        (34, '#2 Have a limited Useful Life (UL), not the life of the building.'),
        (35, "#3 Have a predictable Remaining Useful Life (RUL)."),
        (36, "#4 Be above a minimum threshold cost."),
    ]
    for row, text in instruction_lines:
        instructions.cell(row=row, column=1, value=text)

    headers = [
        "Category",
        "Subcategory",
        "Component",
        "Method",
        "Cost",
        "Cost Units",
        "Quantity",
        "Quantity Units",
        "Useful Life",
        "Remaining Useful Life",
        "Notes",
    ]
    for column_index, header in enumerate(headers, start=1):
        cell = component_sheet.cell(row=2, column=column_index, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
        cell.border = border

    method_validation = DataValidation(type="list", formula1='"One Time,Repeating"', allow_blank=False)
    component_sheet.add_data_validation(method_validation)
    for row in range(3, 83):
        component_sheet.cell(row=row, column=4, value="Repeating")
        component_sheet.cell(row=row, column=6, value="Each")
        component_sheet.cell(row=row, column=8, value="Each")
        component_sheet.cell(row=row, column=10, value="0:00")
        method_validation.add(component_sheet.cell(row=row, column=4))
        for col in range(1, len(headers) + 1):
            cell = component_sheet.cell(row=row, column=col)
            cell.fill = yellow
            cell.border = border
        component_sheet.cell(row=row, column=5).number_format = "$#,##0"

    widths = [24, 24, 38, 16, 14, 16, 14, 18, 14, 22, 36]
    for index, width in enumerate(widths, start=1):
        component_sheet.column_dimensions[chr(64 + index)].width = width
    component_sheet.freeze_panes = "A3"

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
        if "component" in values or "component description" in values or "component name" in values:
            header_index = index
            break
    if header_index is None:
        raise ValueError('Could not find a "Component" header in the uploaded template.')

    headers = [str(value).strip() for value in frame.loc[header_index].tolist()]
    data = frame.loc[header_index + 1 :].copy()
    data.columns = headers
    columns = _normalize_template_columns(data.columns)

    component_col = columns.get("component") or columns.get("component description") or columns.get("component name")
    if component_col is None:
        raise ValueError('The template must include a "Component" column.')

    category = "Imported Components"
    rows = []
    for _, row in data.iterrows():
        marker = _clean_template_value(row.get("#", ""))
        description = _clean_template_value(row.get(component_col, ""))

        if marker.lower() == "title":
            category = description or category
            continue
        if not description:
            continue

        funded = _clean_template_value(row.get(columns.get("funded (yes/no)", ""), "")) or "Yes"
        if funded.lower().startswith("n"):
            continue

        if columns.get("quantity units") is not None:
            quantity = _template_number(row.get(columns.get("quantity", ""), 0), default=0.0)
            quantity_units = _clean_template_value(row.get(columns.get("quantity units", ""), "")) or "Each"
        else:
            quantity, quantity_units = _parse_quantity(row.get(columns.get("quantity", ""), ""))

        current_cost = _template_number(row.get(columns.get("current cost", ""), 0))
        cost = _template_number(row.get(columns.get("cost", ""), current_cost), default=current_cost)
        cost_units = _clean_template_value(row.get(columns.get("cost units", ""), "")) or quantity_units
        if columns.get("cost") is None and current_cost:
            cost = current_cost / quantity if quantity else current_cost

        useful_life = _template_number(row.get(columns.get("useful life", columns.get("ul", "")), 0))
        remaining_useful_life = _clean_template_value(
            row.get(columns.get("remaining useful life", columns.get("rul", "")), "0:00")
        ) or "0:00"

        rows.append(
            {
                "category": _clean_template_value(row.get(columns.get("category", ""), "")) or category,
                "subcategory": _clean_template_value(row.get(columns.get("subcategory", ""), "")),
                "component": description,
                "method": _clean_template_value(row.get(columns.get("method", ""), "")) or "Repeating",
                "cost": cost,
                "cost_units": cost_units,
                "quantity": quantity,
                "quantity_units": quantity_units,
                "useful_life": useful_life,
                "remaining_useful_life": remaining_useful_life,
                "notes": _clean_template_value(row.get(columns.get("notes", ""), "")),
            }
        )

    return prepare_components_input(pd.DataFrame(rows, columns=COMPONENT_INPUT_COLUMNS))


def _component_list_frame_from_workbook(uploaded_file) -> pd.DataFrame:
    workbook_bytes = uploaded_file.getvalue()
    workbook_bytes = _recalculate_workbook_bytes(workbook_bytes, uploaded_file.name)
    formula_workbook = load_workbook(BytesIO(workbook_bytes), data_only=False, read_only=False)
    if "Component List" not in formula_workbook.sheetnames:
        raise ValueError('Workbook must include a sheet named exactly "Component List". Extra sheets are fine.')

    value_workbook = load_workbook(BytesIO(workbook_bytes), data_only=True, read_only=False)
    formula_sheet = formula_workbook["Component List"]
    value_sheet = value_workbook["Component List"]
    values, unresolved = _worksheet_values_with_formula_refs(formula_workbook, value_workbook, formula_sheet, value_sheet)
    _raise_for_uncalculated_required_formulas(values, formula_sheet, unresolved)
    return pd.DataFrame(values)


def _recalculate_workbook_bytes(workbook_bytes: bytes, file_name: str) -> bytes:
    compiler = shutil.which("soffice") or shutil.which("libreoffice")
    if compiler is None:
        return workbook_bytes

    suffix = Path(file_name).suffix.lower() or ".xlsx"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        source = tmp_path / f"upload{suffix}"
        source.write_bytes(workbook_bytes)
        result = subprocess.run(
            [compiler, "--headless", "--convert-to", "xlsx", "--outdir", str(tmp_path), str(source)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
        )
        converted = tmp_path / "upload.xlsx"
        if result.returncode == 0 and converted.exists():
            return converted.read_bytes()
    return workbook_bytes


def _worksheet_values_with_formula_refs(formula_workbook, value_workbook, formula_sheet, value_sheet):
    rows = []
    unresolved = set()
    for row_index in range(1, formula_sheet.max_row + 1):
        row_values = []
        for column_index in range(1, formula_sheet.max_column + 1):
            formula_cell = formula_sheet.cell(row=row_index, column=column_index)
            cached_value = value_sheet.cell(row=row_index, column=column_index).value
            value = cached_value
            if isinstance(formula_cell.value, str) and formula_cell.value.startswith("=") and cached_value is None:
                value = _resolve_simple_formula_reference(formula_cell.value, formula_workbook, value_workbook)
                if value is None:
                    unresolved.add((row_index, column_index))
            row_values.append(value)
        rows.append(row_values)
    return rows, unresolved


def _resolve_simple_formula_reference(formula: str, formula_workbook, value_workbook):
    match = re.fullmatch(r"=\s*(?:'([^']+)'|([^'!]+))!\$?([A-Z]+)\$?(\d+)\s*", formula.strip(), re.IGNORECASE)
    if not match:
        return None
    sheet_name = match.group(1) or match.group(2)
    coordinate = f"{match.group(3).upper()}{match.group(4)}"
    if sheet_name not in value_workbook.sheetnames:
        return None
    cached_value = value_workbook[sheet_name][coordinate].value
    if cached_value is not None:
        return cached_value
    raw_value = formula_workbook[sheet_name][coordinate].value
    if isinstance(raw_value, str) and raw_value.startswith("="):
        return _resolve_simple_formula_reference(raw_value, formula_workbook, value_workbook)
    return raw_value


def _raise_for_uncalculated_required_formulas(values, formula_sheet, unresolved) -> None:
    headers = {}
    for row_number, row in enumerate(values, start=1):
        normalized_values = [str(value).strip().lower() if value is not None else "" for value in row]
        if "component" in normalized_values or "component description" in normalized_values or "component name" in normalized_values:
            headers = {value: index + 1 for index, value in enumerate(normalized_values) if value}
            header_row = row_number
            break
    else:
        return

    required_columns = [
        headers.get("component") or headers.get("component description") or headers.get("component name"),
        headers.get("cost") or headers.get("current cost"),
        headers.get("quantity"),
        headers.get("useful life") or headers.get("ul"),
        headers.get("remaining useful life") or headers.get("rul"),
    ]
    required_columns = [column for column in required_columns if column is not None]
    for row_index in range(header_row + 1, formula_sheet.max_row + 1):
        for column_index in required_columns:
            if (row_index, column_index) in unresolved:
                raise ValueError(
                    "The Component List contains formulas that were not saved with calculated values. "
                    "Direct references such as =OtherTab!A1 are supported. For other formulas, open the workbook "
                    "in Excel or LibreOffice, let it recalculate, save it, and upload again."
                )


def load_component_upload(uploaded_file) -> pd.DataFrame:
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix in {".csv", ".xlscsv"}:
        frame = pd.read_csv(uploaded_file)
        if "component" in frame.columns:
            return prepare_components_input(frame)
        return components_from_template_frame(frame)
    if suffix in {".xlsx", ".xlsm"}:
        return components_from_template_frame(_component_list_frame_from_workbook(uploaded_file))
    if suffix == ".xls":
        return components_from_template_frame(pd.read_excel(uploaded_file, sheet_name="Component List", header=None))
    raise ValueError("Upload a component schedule in CSV, XLSX, XLSM, XLSCSV, or XLS format.")


def component_template_download_link() -> str:
    encoded = base64.b64encode(component_template_bytes()).decode("ascii")
    return (
        '<a download="ridge_park_component_import_template.xlsx" '
        'href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,'
        f'{encoded}">THIS TEMPLATE</a>'
    )


@st.dialog("Upload")
def render_component_import_dialog():
    st.markdown(
        "Upload a component schedule using "
        f"{component_template_download_link()} in CSV, XLSX, XLSM, or XLSCSV format.",
        unsafe_allow_html=True,
    )
    uploaded_components = st.file_uploader(
        "Upload component schedule",
        type=["csv", "xlsx", "xlsm", "xlscsv"],
        help='Upload CSV/XLSCSV or a workbook with a sheet named exactly "Component List". Extra workbook tabs are allowed.',
    )

    if uploaded_components is not None:
        if st.button("Load import", use_container_width=True):
            try:
                st.session_state["components_frame"] = load_component_upload(uploaded_components)
                st.session_state["results"] = None
                st.session_state["last_run_signature"] = None
                st.success("Component import loaded.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not import components: {exc}")


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


def mark_components_dirty():
    st.session_state["components_frame"] = prepare_components_input(st.session_state["components_frame"])
    st.session_state["results"] = None
    st.session_state["last_run_signature"] = None
    st.session_state.pop("components_editor", None)


def component_categories() -> list[str]:
    frame = prepare_components_input(st.session_state["components_frame"])
    return sorted([str(value) for value in frame["category"].dropna().unique() if str(value).strip()])


def add_component_to_category(category: str) -> None:
    frame = prepare_components_input(st.session_state["components_frame"])
    new_row = {
        "category": category,
        "subcategory": "",
        "component": "New Component",
        "method": "Repeating",
        "cost": 0.0,
        "cost_units": "Each",
        "quantity": 1.0,
        "quantity_units": "Each",
        "useful_life": 1.0,
        "remaining_useful_life": "0:00",
        "notes": "",
    }
    st.session_state["components_frame"] = pd.concat([frame, pd.DataFrame([new_row])], ignore_index=True)
    st.session_state["editing_component_index"] = len(st.session_state["components_frame"]) - 1
    st.session_state["moving_component_index"] = None
    mark_components_dirty()


def rename_component_category(old_category: str, new_category: str) -> None:
    new_category = str(new_category).strip()
    if not new_category:
        st.warning("Category name cannot be blank.")
        return
    frame = prepare_components_input(st.session_state["components_frame"])
    frame.loc[frame["category"] == old_category, "category"] = new_category
    st.session_state["components_frame"] = frame
    st.session_state["editing_category"] = None
    mark_components_dirty()


def delete_component_at(row_index: int) -> None:
    frame = prepare_components_input(st.session_state["components_frame"])
    if row_index not in frame.index:
        return
    st.session_state["components_frame"] = frame.drop(index=row_index).reset_index(drop=True)
    st.session_state["editing_component_index"] = None
    st.session_state["moving_component_index"] = None
    mark_components_dirty()


@st.dialog("Delete component")
def render_delete_component_dialog(row_index: int):
    frame = prepare_components_input(st.session_state["components_frame"])
    if row_index not in frame.index:
        st.warning("This component is no longer available.")
        if st.button("Close", use_container_width=True):
            st.rerun()
        return

    row = frame.loc[row_index]
    label = f"{row.get('subcategory', '')} / {row.get('component', '')}".strip(" /")
    st.write(f"Are you sure you want to delete {label}?")
    delete_col, cancel_col = st.columns(2)
    with delete_col:
        if st.button("Delete", type="primary", use_container_width=True):
            delete_component_at(row_index)
            st.rerun()
    with cancel_col:
        if st.button("Cancel", use_container_width=True):
            st.rerun()


def render_component_category_row(category: str) -> None:
    editing_category = st.session_state.get("editing_category")
    if editing_category == category:
        category_col, save_col, cancel_col = st.columns([8.5, 0.75, 0.75])
        with category_col:
            st.markdown("<span class='rp-category-edit-row-marker'></span>", unsafe_allow_html=True)
            new_category = st.text_input(
                "Category",
                value=category,
                label_visibility="collapsed",
                key=f"category_name_{category}",
            )
        with save_col:
            if st.button("💾", help="Save category name", key=f"save_category_{category}"):
                rename_component_category(category, new_category)
                st.rerun()
        with cancel_col:
            if st.button("✖", help="Cancel category edit", key=f"cancel_category_{category}"):
                st.session_state["editing_category"] = None
                st.rerun()
        return

    name_col, add_col, spacer_col, edit_col = st.columns([2.4, 1.4, 6.0, 0.75])
    with name_col:
        st.markdown(f"<div class='rp-category-strip'>{escape(category)}</div>", unsafe_allow_html=True)
    with add_col:
        if st.button("+ Add component", key=f"add_component_{category}"):
            add_component_to_category(category)
            st.rerun()
    with spacer_col:
        st.markdown("<div class='rp-category-fill'></div>", unsafe_allow_html=True)
    with edit_col:
        if st.button("✎", help="Edit category name", key=f"edit_category_{category}"):
            st.session_state["editing_category"] = category
            st.session_state["editing_component_index"] = None
            st.rerun()


def render_component_display_row(row_index: int, row: pd.Series, categories: list[str]) -> None:
    columns = st.columns([1.2, 2.2, 1.25, 1.0, 1.0, 1.0, 1.15, 0.75, 0.9, 2.2, 0.55, 0.55])
    values = [
        row["subcategory"],
        row["component"],
        row["method"],
        format_currency(row["cost"]),
        row["cost_units"],
        f"{float(row['quantity']):,.0f}",
        row["quantity_units"],
        f"{float(row['useful_life']):.0f}",
        row["remaining_useful_life"],
        row.get("notes", ""),
    ]
    for column, value in zip(columns[:10], values):
        with column:
            st.markdown(f"<div class='rp-component-cell'>{escape(str(value))}</div>", unsafe_allow_html=True)
    with columns[10]:
        if st.button("✎", help="Edit component", key=f"edit_component_{row_index}"):
            st.session_state["editing_component_index"] = row_index
            st.session_state["editing_category"] = None
            st.session_state["moving_component_index"] = None
            st.rerun()
    with columns[11]:
        if st.button("🗑", help="Delete component", key=f"delete_component_{row_index}"):
            render_delete_component_dialog(row_index)


def render_component_edit_row(row_index: int, row: pd.Series, categories: list[str]) -> None:
    columns = st.columns([1.2, 2.2, 1.25, 1.0, 1.0, 1.0, 1.15, 0.75, 0.9, 2.2, 0.5, 0.5, 0.5])
    with columns[0]:
        st.markdown("<span class='rp-editing-row-marker'></span>", unsafe_allow_html=True)
        subcategory = st.text_input("Subcategory", value=str(row["subcategory"]), key=f"edit_subcategory_{row_index}", label_visibility="collapsed")
    with columns[1]:
        component = st.text_input("Component", value=str(row["component"]), key=f"edit_component_name_{row_index}", label_visibility="collapsed")
    with columns[2]:
        method = st.selectbox(
            "Method",
            ["One Time", "Repeating"],
            index=0 if row["method"] == "One Time" else 1,
            key=f"edit_method_{row_index}",
            label_visibility="collapsed",
        )
    with columns[3]:
        cost = st.number_input("Cost", value=float(row["cost"]), min_value=0.0, step=100.0, key=f"edit_cost_{row_index}", label_visibility="collapsed")
    with columns[4]:
        cost_units = st.text_input("Cost Units", value=str(row["cost_units"]), key=f"edit_cost_units_{row_index}", label_visibility="collapsed")
    with columns[5]:
        quantity = st.number_input("Quantity", value=float(row["quantity"]), min_value=0.0, step=1.0, key=f"edit_quantity_{row_index}", label_visibility="collapsed")
    with columns[6]:
        quantity_units = st.text_input("Quantity Units", value=str(row["quantity_units"]), key=f"edit_quantity_units_{row_index}", label_visibility="collapsed")
    with columns[7]:
        useful_life = st.number_input("UL", value=float(row["useful_life"]), min_value=0.0, step=1.0, key=f"edit_useful_life_{row_index}", label_visibility="collapsed")
    with columns[8]:
        remaining_useful_life = st.text_input("RUL", value=str(row["remaining_useful_life"]), key=f"edit_remaining_life_{row_index}", label_visibility="collapsed")
    with columns[9]:
        notes = st.text_input("Notes", value=str(row.get("notes", "")), key=f"edit_notes_{row_index}", label_visibility="collapsed")
    with columns[10]:
        if st.button("💾", help="Save component", key=f"save_component_{row_index}"):
            frame = prepare_components_input(st.session_state["components_frame"])
            frame.loc[row_index, [
                "subcategory",
                "component",
                "method",
                "cost",
                "cost_units",
                "quantity",
                "quantity_units",
                "useful_life",
                "remaining_useful_life",
                "notes",
            ]] = [
                subcategory,
                component,
                method,
                cost,
                cost_units,
                quantity,
                quantity_units,
                useful_life,
                remaining_useful_life,
                notes,
            ]
            st.session_state["components_frame"] = frame
            st.session_state["editing_component_index"] = None
            st.session_state["moving_component_index"] = None
            mark_components_dirty()
            st.rerun()
    with columns[11]:
        if st.button("✖", help="Delete component", key=f"delete_edit_component_{row_index}"):
            render_delete_component_dialog(row_index)
    with columns[12]:
        if st.button("⇄", help="Move to another category", key=f"move_component_{row_index}"):
            st.session_state["moving_component_index"] = row_index
            st.rerun()

    if st.session_state.get("moving_component_index") == row_index:
        current_category = str(row["category"])
        current_index = categories.index(current_category) if current_category in categories else 0
        move_col, apply_col = st.columns([5, 1])
        with move_col:
            new_category = st.selectbox(
                "Move component to category",
                categories,
                index=current_index,
                key=f"move_category_select_{row_index}",
            )
        with apply_col:
            if st.button("Apply", key=f"apply_move_category_{row_index}", use_container_width=True):
                frame = prepare_components_input(st.session_state["components_frame"])
                frame.loc[row_index, "category"] = new_category
                st.session_state["components_frame"] = frame
                st.session_state["moving_component_index"] = None
                mark_components_dirty()
                st.rerun()


def render_component_table(frame: pd.DataFrame, chapter: str) -> None:
    frame = prepare_components_input(frame)
    display_frame = frame if chapter == "ALL" else frame.loc[frame["category"] == chapter]
    categories = component_categories()

    st.markdown(
        """
        <div class="rp-native-component-header">
            <span>Category/Subcategory</span><span>Component</span><span>Method</span><span>Cost</span>
            <span>Cost Units</span><span>Quantity</span><span>Quantity Units</span><span>UL</span><span>RUL</span><span>Notes</span><span>Options</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    current_category = None
    shown_rows = 0
    for row_index, row in display_frame.head(80).iterrows():
        category = str(row.get("category", "") or "Uncategorized")
        if category != current_category:
            current_category = category
            render_component_category_row(category)

        if st.session_state.get("editing_component_index") == row_index:
            render_component_edit_row(row_index, row, categories)
        else:
            render_component_display_row(row_index, row, categories)
        shown_rows += 1

    if shown_rows == 0:
        st.markdown("<div class='rp-empty-table'>No components in this chapter.</div>", unsafe_allow_html=True)


def component_table_html(components_frame: pd.DataFrame, chapter: str) -> str:
    frame = prepare_components_input(components_frame)
    if chapter != "ALL":
        frame = frame.loc[frame["category"] == chapter].copy()

    rows = []
    current_category = None
    for _, row in frame.head(80).iterrows():
        category = str(row.get("category", "") or "Uncategorized")
        if category != current_category:
            current_category = category
            rows.append(
                f"""
                <tr class="group">
                    <td colspan="10"><span class="rp-category-name">{escape(category)}</span><span class="rp-add-component">+ Add component</span></td>
                    <td class="rp-row-actions">✎ 🗑 ⬆</td>
                </tr>
                """
            )

        cost = format_currency(row["cost"])
        rows.append(
            f"""
            <tr>
                <td>{escape(str(row["subcategory"]))}</td>
                <td>{escape(str(row["component"]))}</td>
                <td>{escape(str(row["method"]))}</td>
                <td style="text-align:right;">{cost}</td>
                <td>{escape(str(row["cost_units"]))}</td>
                <td style="text-align:right;">{float(row["quantity"]):,.0f}</td>
                <td>{escape(str(row["quantity_units"]))}</td>
                <td style="text-align:right;">{float(row["useful_life"]):.0f}</td>
                <td style="text-align:right;">{escape(str(row["remaining_useful_life"]))}</td>
                <td>{escape(str(row.get("notes", "")))}</td>
                <td class="rp-row-actions">✎ &nbsp; 🗑</td>
            </tr>
            """
        )

    if not rows:
        rows.append('<tr><td colspan="11" style="height:180px;text-align:center;color:#9aa4ac;">No components in this chapter.</td></tr>')

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
        .rp-components-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 12px;
            color: #65717a;
        }}
        .rp-components-table th {{
            background: #fff;
            border: 1px solid #e5e8eb;
            border-left: 0;
            padding: 10px 8px;
            color: #5f6870;
            font-weight: 700;
            text-align: left;
            position: sticky;
            top: 0;
            z-index: 5;
        }}
        .rp-components-table th:first-child {{
            border-left: 1px solid #e5e8eb;
        }}
        .rp-components-table td {{
            border: 1px solid #edf0f2;
            border-left: 0;
            border-top: 0;
            padding: 9px 8px;
            background: #fff;
            vertical-align: middle;
        }}
        .rp-components-table td:first-child {{
            border-left: 1px solid #edf0f2;
        }}
        .rp-components-table tbody tr:not(.group):hover td {{
            background: #b7b7b7;
            color: #3d3d3d;
        }}
        .rp-components-table tr.group td {{
            background: var(--rp-blue-row);
            color: #42535f;
            font-weight: 700;
            padding: 8px;
            position: sticky;
            top: 38px;
            z-index: 4;
            border-top: 1px solid #e5e8eb;
            box-shadow: 0 1px 0 rgba(31,49,64,.06);
        }}
        .rp-category-name {{
            display: inline-block;
            min-width: 180px;
        }}
        .rp-add-component {{
            margin-left: 16px;
            background: #fff;
            border: 1px solid #dfe7ec;
            padding: 3px 9px;
            font-weight: 600;
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
        <table class="rp-components-table">
            <thead>
                <tr>
                    <th style="width:12%;">Category/Subcategory</th>
                    <th style="width:20%;">Component</th>
                    <th style="width:9%;">Method</th>
                    <th style="width:8%;text-align:right;">Cost</th>
                    <th style="width:8%;">Cost Units</th>
                    <th style="width:7%;text-align:right;">Quantity</th>
                    <th style="width:9%;">Quantity Units</th>
                    <th style="width:6%;text-align:right;">UL</th>
                    <th style="width:7%;text-align:right;">RUL</th>
                    <th>Notes</th>
                    <th style="width:7%;">Options</th>
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

    st.markdown('<div class="rp-native-toolbar">', unsafe_allow_html=True)
    chapter_col, spacer_col, upload_col, add_col, refresh_col, grid_col, print_col = st.columns([4.5, 3.7, 0.45, 0.45, 0.45, 0.45, 0.45])
    with chapter_col:
        chapter = st.selectbox("Chapters", categories, key="component_chapter")
    with upload_col:
        if st.button("⬆", help="Import Inventory", use_container_width=True):
            render_component_import_dialog()
    with add_col:
        if st.button("＋", help="Add component", use_container_width=True):
            target_category = chapter if chapter != "ALL" else (categories[1] if len(categories) > 1 else "New Category")
            add_component_to_category(target_category)
            st.rerun()
    with refresh_col:
        st.button("↻", help="Refresh component preview", use_container_width=True)
    with grid_col:
        st.button("▣", help="Component grid options", use_container_width=True)
    with print_col:
        st.button("▤", help="Export native CSV below", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="rp-panel">', unsafe_allow_html=True)
    render_component_table(frame, chapter)
    st.markdown("</div>", unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="rp-editor-shell">', unsafe_allow_html=True)
        st.markdown('<div class="rp-native-editor"><h4>Component Schedule Actions</h4></div>', unsafe_allow_html=True)

        download_col, reset_col, run_col = st.columns([1, 1, 1])
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
                st.session_state["editing_component_index"] = None
                st.session_state["editing_category"] = None
                st.session_state["moving_component_index"] = None
                st.session_state["results"] = None
                st.session_state["last_run_signature"] = None
                st.rerun()
        with run_col:
            run_requested = st.button("Run Study", type="primary", use_container_width=True)

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
            column_config={
                "category": st.column_config.TextColumn("Category"),
                "subcategory": st.column_config.TextColumn("Subcategory"),
                "component": st.column_config.TextColumn("Component"),
                "method": st.column_config.SelectboxColumn("Method", options=["One Time", "Repeating"]),
                "cost": st.column_config.NumberColumn("Cost", format="$%0.2f"),
                "cost_units": st.column_config.TextColumn("Cost Units"),
                "quantity": st.column_config.NumberColumn("Quantity", format="%0.2f"),
                "quantity_units": st.column_config.TextColumn("Quantity Units"),
                "useful_life": st.column_config.NumberColumn("Useful Life", format="%0.0f"),
                "remaining_useful_life": st.column_config.TextColumn("Remaining Useful Life"),
                "notes": st.column_config.TextColumn("Notes"),
            },
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
        date_cols=["replacement_date"],
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
