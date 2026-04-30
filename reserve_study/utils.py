from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd

DAY_OF_MONTH = 1


def normalize_to_month(dt, day: int = DAY_OF_MONTH) -> pd.Timestamp:
    dt = pd.Timestamp(dt)
    return pd.Timestamp(year=dt.year, month=dt.month, day=day)


def parse_remaining_life_to_months(text) -> float:
    text = str(text).strip()
    if text == "" or text.lower() == "nan":
        return np.nan
    if ":" in text:
        years, months = text.split(":", 1)
        return int(years) * 12 + int(months)
    return int(round(float(text) * 12))


def years_to_months(years) -> float:
    if pd.isna(years):
        return np.nan
    return int(round(float(years) * 12))


def months_to_ym(months) -> str | float:
    if pd.isna(months):
        return np.nan
    months = int(months)
    years = months // 12
    rem_months = months % 12
    return f"{years}:{rem_months:02d}"


def add_months(base_date, months, day: int = DAY_OF_MONTH) -> pd.Timestamp:
    base_date = normalize_to_month(base_date, day=day)
    months = int(months)
    total = (base_date.year * 12 + (base_date.month - 1)) + months
    year = total // 12
    month = total % 12 + 1
    return pd.Timestamp(year=year, month=month, day=day)


def shift_by_life(base_date, life_months, direction: int = 1, day: int = DAY_OF_MONTH) -> pd.Timestamp:
    return add_months(base_date, direction * int(life_months), day=day)


def months_between(start_date, end_date) -> int:
    start_date = normalize_to_month(start_date)
    end_date = normalize_to_month(end_date)
    return (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)


def money(value, decimals: int = 0) -> str:
    try:
        value = float(value)
    except Exception:
        return str(value)
    return f"${value:,.{decimals}f}"


def latex_escape(value) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\\", r"\textbackslash{}")
    for a, b in [('&', r'\&'), ('%', r'\%'), ('$', r'\$'), ('#', r'\#'), ('_', r'\_'), ('{', r'\{'), ('}', r'\}')]:
        text = text.replace(a, b)
    return text


def pct(value, decimals: int = 2) -> str:
    return f"{float(value):.{decimals}f}%"


def money_nodollar(value, decimals: int = 0) -> str:
    return f"{float(value):,.{decimals}f}"


def format_short_date(dt) -> str:
    if pd.isna(dt):
        return ""
    dt = pd.Timestamp(dt)
    return f"{dt.month}/{str(dt.year)[-2:]}"


def format_date_range(values) -> str:
    dates = pd.Series(values).dropna().sort_values()
    if len(dates) == 0:
        return ""
    if len(dates) == 1:
        return format_short_date(dates.iloc[0])
    return f"{format_short_date(dates.iloc[0])} - {format_short_date(dates.iloc[-1])}"


def text_to_latex_paragraphs(text: str) -> str:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", str(text).strip()) if block.strip()]
    return "\n\n".join(latex_escape(block) for block in blocks)


def parse_sectioned_text(text: str) -> list[tuple[str, str]]:
    text = str(text).strip().replace("\r\n", "\n")
    lines = text.split("\n")
    sections: list[tuple[str, str]] = []
    current_title = None
    current_body: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_body
        if current_title is not None:
            sections.append((current_title.strip(), "\n".join(current_body).strip()))
        current_title = None
        current_body = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]") and len(stripped) > 2:
            flush()
            current_title = stripped[1:-1].strip()
        elif stripped.startswith("## "):
            flush()
            current_title = stripped[3:].strip()
        elif stripped.startswith("# "):
            flush()
            current_title = stripped[2:].strip()
        elif stripped.endswith(":") and stripped[:-1].strip() and not current_body:
            flush()
            current_title = stripped[:-1].strip()
        else:
            if current_title is None and stripped:
                current_title = "Section"
                current_body = [line]
            else:
                current_body.append(line)

    flush()
    return sections


def render_preparer_sections(text: str) -> str:
    parts: list[str] = []
    for title, body in parse_sectioned_text(text):
        parts.append(rf"{{\bfseries {latex_escape(title)}}}\\")
        body_latex = text_to_latex_paragraphs(body)
        if body_latex:
            parts.append(body_latex)
        parts.append("")
    return "\n".join(parts).strip()


def render_template(template_text: str, values: dict[str, object]) -> str:
    rendered = template_text
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
