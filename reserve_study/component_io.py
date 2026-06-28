from __future__ import annotations

import pandas as pd

from .utils import months_to_ym, parse_remaining_life_to_months


COMPONENT_INPUT_COLUMNS = [
    "category",
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
    "B6_category",
]

TEXT_COMPONENT_COLUMNS = {
    "category",
    "subcategory",
    "component",
    "method",
    "cost_units",
    "quantity_units",
    "remaining_useful_life",
    "notes",
    "B6_category",
}


def normalize_method(value) -> str:
    return "One Time" if str(value).strip().lower() == "one time" else "Repeating"


def normalize_remaining_life(value) -> str:
    months = parse_remaining_life_to_months(value)
    return "0:00" if pd.isna(months) else str(months_to_ym(months))


def prepare_components_input(source) -> pd.DataFrame:
    df = source.copy() if isinstance(source, pd.DataFrame) else pd.read_csv(source).copy()
    out = df.copy()

    if "useful_life" not in out.columns and "life_years" in out.columns:
        out["useful_life"] = out["life_years"]
    if "remaining_useful_life" not in out.columns and "remaining_life" in out.columns:
        out["remaining_useful_life"] = out["remaining_life"]

    notes = out["notes"].fillna("").astype(str) if "notes" in out.columns else pd.Series([""] * len(out), index=out.index)
    if "source_page" in out.columns:
        source_pages = out["source_page"].fillna("").astype(str).str.strip()
        notes = [
            _merge_notes_and_source(note, source_page)
            for note, source_page in zip(notes, source_pages)
        ]
        out["notes"] = notes

    for column in COMPONENT_INPUT_COLUMNS:
        if column not in out.columns:
            out[column] = "" if column in TEXT_COMPONENT_COLUMNS else 0

    out = out[COMPONENT_INPUT_COLUMNS].copy()
    for column in ["cost", "quantity", "useful_life"]:
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0)
    for column in TEXT_COMPONENT_COLUMNS:
        out[column] = out[column].fillna("").astype(str)

    out["method"] = out["method"].apply(normalize_method)
    out["remaining_useful_life"] = out["remaining_useful_life"].apply(normalize_remaining_life)
    return out.reset_index(drop=True)


def _merge_notes_and_source(note: str, source_page: str) -> str:
    note = str(note).strip()
    source_page = str(source_page).strip()
    if not source_page or source_page.lower() == "nan":
        return note
    source_note = f"Source page: {source_page}"
    if not note:
        return source_note
    if source_note.lower() in note.lower():
        return note
    return f"{note} | {source_note}"
