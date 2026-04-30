from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from .models import ReportMetadata
from .study import StudyResult
from .utils import format_date_range, format_short_date, latex_escape, money, months_to_ym, pct, render_preparer_sections, render_template, text_to_latex_paragraphs

ROW = " \\\\"


def latex_money(value, decimals: int = 0) -> str:
    return latex_escape(money(value, decimals=decimals))


def latex_pct(value, decimals: int = 2) -> str:
    return latex_escape(pct(value, decimals=decimals))


class ReportBuilder:
    def __init__(self, study_results: StudyResult, metadata: ReportMetadata | None = None):
        self.study_results = study_results
        self.scenario = study_results.scenario
        self.metadata = metadata or ReportMetadata()

    def _make_matrix_table_chunk(self, exp_matrix: pd.DataFrame, start_col: int, end_col: int) -> str:
        years = list(exp_matrix.columns[start_col:end_col])
        header = "Category & " + " & ".join(str(year) for year in years) + ROW
        rows = [header, r"\midrule"]
        visible_idx = 0
        for _, row in exp_matrix.iterrows():
            vals = []
            for year in years:
                value = row[year]
                vals.append("" if pd.isna(value) or float(value) == 0 else latex_money(value))
            prefix = r"\rowcolor{blue!12} " if visible_idx % 2 == 0 else ""
            rows.append(prefix + latex_escape(row["category"]) + " & " + " & ".join(vals) + ROW)
            visible_idx += 1
        return "\n".join(rows)

    def _rows_join(self, rows: list[str]) -> str:
        return "\n".join(rows)

    def _make_statement_table(self, df: pd.DataFrame) -> str:
        rows = []
        for index, row in enumerate(df.itertuples()):
            prefix = r"\rowcolor{blue!12} " if index % 2 == 0 else ""
            rows.append(f"{prefix}{latex_escape(row.metric)} & {latex_escape(row.formatted)}{ROW}")
        return self._rows_join(rows)

    def _make_summary_table(self, df: pd.DataFrame) -> str:
        rows = []
        for index, row in enumerate(df.itertuples()):
            prefix = r"\rowcolor{blue!12} " if index % 2 == 0 else ""
            rows.append(
                f"{prefix}{latex_escape(row.category)} & {latex_escape(row.useful_lives)} & "
                f"{latex_escape(row.replacement_years)} & {latex_escape(row.remaining_years)} & {latex_money(row.future_cost)}{ROW}"
            )
        return self._rows_join(rows)

    def _make_percent_funded_table(self, df: pd.DataFrame) -> str:
        rows = []
        for index, row in enumerate(df.itertuples()):
            prefix = r"\rowcolor{blue!12} " if index % 2 == 0 else ""
            rows.append(f"{prefix}{int(row.year)} & {latex_money(row.end_balance)} & {latex_money(row.funded_balance)} & {latex_pct(row.percent_funded)}{ROW}")
        return self._rows_join(rows)

    def _make_cashflow_table(self, df: pd.DataFrame) -> str:
        rows = []
        for index, row in enumerate(df.itertuples()):
            prefix = r"\rowcolor{blue!12} " if index % 2 == 0 else ""
            rows.append(
                f"{prefix}{int(row.year)} & {latex_money(row.begin_balance)} & {latex_money(row.contribution)} & "
                f"{latex_money(row.special_assessment)} & {latex_money(row.expenditures)} & {latex_money(row.interest)} & {latex_money(row.end_balance)}{ROW}"
            )
        return self._rows_join(rows)

    def _make_component_summary_longtable(self, df: pd.DataFrame) -> str:
        rows: list[str] = []
        shade_index = 0
        for category, sub in df.groupby("category", sort=False, dropna=False):
            category_label = "" if pd.isna(category) else str(category)
            rows.append(rf"\multicolumn{{8}}{{l}}{{\textbf{{{latex_escape(category_label)}}}}}{ROW}")
            for _, row in sub.iterrows():
                prefix = r"\rowcolor{blue!12} " if shade_index % 2 == 0 else ""
                rows.append(
                    f"{prefix}{latex_escape(row['component'])} & {latex_escape(row['replace_date_display'])} & "
                    f"{latex_money(row['basis_cost'])} & {latex_escape(row['quantity_display'])} & {latex_money(row['current_cost'])} & "
                    f"{latex_escape(row['est_life_display'])} & {latex_escape(row['rem_life_display'])} & {latex_money(row['future_cost'])}{ROW}"
                )
                shade_index += 1
        return self._rows_join(rows)

    def _make_upcoming_table(self, df: pd.DataFrame) -> str:
        rows = []
        for index, row in enumerate(df.itertuples()):
            prefix = r"\rowcolor{blue!12} " if index % 2 == 0 else ""
            rows.append(
                f"{prefix}{latex_escape(format_short_date(row.replacement_date))} & {latex_escape(row.category)} & "
                f"{latex_escape(row.component)} & {latex_money(row.future_cost)}{ROW}"
            )
        return self._rows_join(rows)

    def build_tex(self) -> Path:
        paths = self.scenario.paths
        paths.ensure_output_dirs()
        assumptions = self.scenario.assumptions
        analysis_year = assumptions.analysis_year
        analysis_date_str = assumptions.analysis_date.strftime("%B %d, %Y").replace(" 0", " ")
        association = self.scenario.association_properties

        statement = self.study_results.statement_of_position_formatted_df()
        reserve = self.study_results.reserve_projection_df()
        components = self.study_results.component_details_df()
        exp_matrix = self.study_results.expenditures_matrix_df().reset_index()
        exp_detail = self.study_results.expenditures_detail_df()

        cover_image_file = self.scenario.paths.assets_root / "cover_img.png"
        if cover_image_file.exists():
            shutil.copy2(cover_image_file, paths.report_dir / cover_image_file.name)

        summary = (
            components.groupby("category", dropna=False)
            .agg(
                useful_min=("life_years", "min"),
                useful_max=("life_years", "max"),
                repl_min=("replacement_date", "min"),
                repl_max=("replacement_date", "max"),
                rem_min=("remaining_life_months", "min"),
                rem_max=("remaining_life_months", "max"),
                future_cost=("future_cost", "sum"),
            )
            .reset_index()
            .sort_values("future_cost", ascending=False)
        )
        summary["useful_lives"] = summary.apply(
            lambda row: f"{int(row.useful_min)}" if int(row.useful_min) == int(row.useful_max) else f"{int(row.useful_min)}-{int(row.useful_max)}",
            axis=1,
        )
        summary["replacement_years"] = summary.apply(
            lambda row: str(row.repl_min.year) if row.repl_min.year == row.repl_max.year else f"{row.repl_min.year}-{row.repl_max.year}",
            axis=1,
        )
        summary["remaining_years"] = summary.apply(
            lambda row: months_to_ym(row.rem_min) if int(row.rem_min) == int(row.rem_max) else f"{months_to_ym(row.rem_min)}-{months_to_ym(row.rem_max)}",
            axis=1,
        )

        upcoming = (
            exp_detail[exp_detail["replacement_date"].dt.year <= analysis_year + 1]
            .sort_values(["replacement_date", "future_cost"], ascending=[True, False])
            .head(18)[["replacement_date", "category", "component", "future_cost"]]
        )

        component_summary = components.copy()
        component_summary["replace_date_display"] = component_summary.groupby(["category", "component"], dropna=False)["replacement_date"].transform(format_date_range)
        component_summary_grouped = (
            component_summary.groupby(["category", "component"], dropna=False)
            .agg(
                replace_date_display=("replace_date_display", "first"),
                basis_cost=("cost", "first"),
                quantity=("quantity", "sum"),
                current_cost=("current_cost", "sum"),
                life_years_min=("life_years", "min"),
                life_years_max=("life_years", "max"),
                rem_life_min=("remaining_life_months", "min"),
                rem_life_max=("remaining_life_months", "max"),
                future_cost=("future_cost", "sum"),
                replacement_date_min=("replacement_date", "min"),
            )
            .reset_index()
            .sort_values(["category", "replacement_date_min", "component"])
        )
        component_summary_grouped["quantity_display"] = component_summary_grouped["quantity"].apply(
            lambda value: f"{float(value):,.0f}" if float(value).is_integer() else f"{float(value):,.2f}"
        )
        component_summary_grouped["est_life_display"] = component_summary_grouped.apply(
            lambda row: f"{int(row.life_years_min)}" if int(row.life_years_min) == int(row.life_years_max) else f"{int(row.life_years_min)}-{int(row.life_years_max)}",
            axis=1,
        )
        component_summary_grouped["rem_life_display"] = component_summary_grouped.apply(
            lambda row: months_to_ym(row.rem_life_min) if int(row.rem_life_min) == int(row.rem_life_max) else f"{months_to_ym(row.rem_life_min)}-{months_to_ym(row.rem_life_max)}",
            axis=1,
        )

        template_text = (self.scenario.paths.assets_root / "reserve_report_base.tex").read_text(encoding="utf-8")
        first_year = reserve.iloc[0]
        final_year = reserve.iloc[-1]
        max_category = summary.iloc[0]
        min_balance_row = reserve.loc[reserve["end_balance"].idxmin()]
        max_funded_row = reserve.loc[reserve["percent_funded"].idxmax()]

        values = {
            "ASSOC_NAME": latex_escape(association.get("ASSOC_NAME", "Ridge Park")),
            "CITY_STATE": latex_escape(association.get("CITY_STATE", "")),
            "COVER_LETTER_BODY": text_to_latex_paragraphs(self.scenario.cover_letter),
            "SIGNER_NAME": latex_escape(self.metadata.signer_name),
            "SIGNER_TITLE": latex_escape(self.metadata.signer_title),
            "REPORT_TITLE": latex_escape(self.metadata.report_title),
            "REPORT_TYPE": latex_escape(self.metadata.report_type),
            "REPORT_SUBTITLE": latex_escape(self.metadata.report_subtitle),
            "ANALYSIS_DATE_STR": latex_escape(analysis_date_str),
            "COVER_IMAGE_FILENAME": latex_escape(cover_image_file.name),
            "PREPARER_BODY": render_preparer_sections(self.scenario.preparer_report),
            "ANALYSIS_YEAR": analysis_year,
            "PROJECTION_END_YEAR": analysis_year + self.study_results.projection_years - 1,
            "PROJECT_TYPE": latex_escape(association.get("PROJECT_TYPE", "")),
            "NUM_UNITS": latex_escape(association.get("NUM_UNITS", "")),
            "CONSTRUCTION_DATE": latex_escape(association.get("CONSTRUCTION_DATE", "")),
            "PREPARER": latex_escape(association.get("PREPARER", "")),
            "STATEMENT_TABLE": self._make_statement_table(statement),
            "FIRST_YEAR_CONTRIBUTION": latex_money(first_year["contribution"] + first_year["special_assessment"]),
            "FIRST_YEAR_END_BALANCE": latex_money(first_year["end_balance"]),
            "FINAL_YEAR": int(final_year["year"]),
            "FINAL_YEAR_END_BALANCE": latex_money(final_year["end_balance"]),
            "INFLATION_PCT": latex_pct(assumptions.inflation * 100),
            "INVESTMENT_PCT": latex_pct(assumptions.investment * 100),
            "CONTRIBUTION_FACTOR": latex_escape(str(assumptions.contribution_factor)),
            "SUMMARY_TABLE": self._make_summary_table(summary),
            "PERCENT_FUNDED_TABLE": self._make_percent_funded_table(reserve),
            "CASHFLOW_TABLE": self._make_cashflow_table(reserve),
            "BEGIN_BALANCE": latex_money(assumptions.begin_balance),
            "MATRIX_1_10": self._make_matrix_table_chunk(exp_matrix, 1, min(11, len(exp_matrix.columns))),
            "MATRIX_11_20": self._make_matrix_table_chunk(exp_matrix, 11, min(21, len(exp_matrix.columns))),
            "MATRIX_21_30": self._make_matrix_table_chunk(exp_matrix, 21, min(31, len(exp_matrix.columns))),
            "COMPONENT_SUMMARY_LONGTABLE": self._make_component_summary_longtable(component_summary_grouped),
            "UPCOMING_TABLE": self._make_upcoming_table(upcoming),
            "MAX_CATEGORY": latex_escape(max_category["category"]),
            "MAX_CATEGORY_COST": latex_money(max_category["future_cost"]),
            "MIN_BALANCE_YEAR": int(min_balance_row["year"]),
            "MIN_BALANCE_VALUE": latex_money(min_balance_row["end_balance"]),
            "MAX_FUNDED_YEAR": int(max_funded_row["year"]),
            "MAX_FUNDED_VALUE": latex_pct(max_funded_row["percent_funded"]),
        }

        rendered = render_template(template_text, values)
        tex_path = paths.report_dir / f"{self.metadata.report_file_stem}.tex"
        tex_path.write_text(rendered, encoding="utf-8")
        return tex_path

    def build_pdf(self, tex_path: Path | None = None) -> Path:
        tex_path = tex_path or self.build_tex()
        pdf_path = tex_path.with_suffix(".pdf")
        mactex_bin = "/Library/TeX/texbin"
        tinytex_bin = str(Path.home() / "Library" / "TinyTeX" / "bin" / "universal-darwin")
        env = os.environ.copy()
        env["PATH"] = os.pathsep.join([mactex_bin, tinytex_bin, env.get("PATH", "")])

        compiler = self.find_pdf_compiler(env["PATH"], mactex_bin=mactex_bin)
        if compiler is None:
            raise OSError(
                "Could not compile PDF because neither latexmk nor pdflatex was found. "
                "Install a TeX distribution such as MacTeX, ensure /Library/TeX/texbin is present, "
                "or add latexmk/pdflatex to PATH, then rerun with --compile-pdf."
            )

        def run_cmd(cmd: list[str]) -> None:
            result = subprocess.run(cmd, cwd=tex_path.parent, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if result.returncode != 0:
                raise RuntimeError(result.stdout)

        name, executable = compiler
        if name == "latexmk":
            run_cmd([executable, "-C", tex_path.name])
            run_cmd([executable, "-g", "-pdf", "-interaction=nonstopmode", "-halt-on-error", tex_path.name])
        else:
            run_cmd([executable, "-interaction=nonstopmode", "-halt-on-error", tex_path.name])
            run_cmd([executable, "-interaction=nonstopmode", "-halt-on-error", tex_path.name])
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF was not created: {pdf_path}")
        return pdf_path

    @staticmethod
    def find_pdf_compiler(path: str | None = None, mactex_bin: str = "/Library/TeX/texbin", include_tinytex: bool = True) -> tuple[str, str] | None:
        tinytex_bin = Path.home() / "Library" / "TinyTeX" / "bin" / "universal-darwin"
        search_parts = [path or os.environ.get("PATH", "")]
        if include_tinytex:
            search_parts.append(str(tinytex_bin))
        search_path = os.pathsep.join(part for part in search_parts if part)
        for name in ("latexmk", "pdflatex"):
            executable = shutil.which(name, path=search_path)
            if executable:
                return name, executable
            candidate = Path(mactex_bin) / name
            if candidate.exists():
                return name, str(candidate)
        return None
