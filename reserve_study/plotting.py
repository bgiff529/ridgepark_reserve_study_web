from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

from .study import StudyResult


class PlotBuilder:
    def __init__(self, study_results: StudyResult):
        self.study_results = study_results
        self.scenario = study_results.scenario

    def build_all(self, output_dir: Path | None = None) -> list[Path]:
        output_dir = output_dir or self.scenario.paths.plots_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        reserve_projection = self.study_results.reserve_projection_df()
        expenditures = self.study_results.expenditures_summary_df().rename(columns={"replacement_year": "year"})
        assessments = self.study_results.collection_schedule.annual_df().rename(columns={"contribution": "annual_contribution"})

        plot_df = self._build_plot_frame(assessments, expenditures)
        paths = [
            self._plot_contributions(plot_df, output_dir / "contributions.png"),
            self._plot_expenditures_vs_contributions(plot_df, output_dir / "expenditures_vs_contributions.png"),
            self._plot_reserve_balance(reserve_projection, output_dir / "reserve_balance.png"),
            self._plot_percent_funded(reserve_projection, output_dir / "percent_funded.png"),
        ]
        return paths

    def _build_plot_frame(self, assessments: pd.DataFrame, expenditures: pd.DataFrame) -> pd.DataFrame:
        analysis_year = int(self.scenario.assumptions.analysis_year)
        projection_years = int(self.study_results.projection_years)
        years = pd.DataFrame({"year": np.arange(analysis_year, analysis_year + projection_years, dtype=int)})

        assessments = assessments.copy()
        if assessments.empty:
            assessments = years.assign(annual_contribution=0.0, special_assessment=0.0)
        if "annual_contribution" not in assessments.columns and "contribution" in assessments.columns:
            assessments = assessments.rename(columns={"contribution": "annual_contribution"})
        for column in ["annual_contribution", "special_assessment"]:
            if column not in assessments.columns:
                assessments[column] = 0.0
            assessments[column] = pd.to_numeric(assessments[column], errors="coerce").fillna(0.0)
        assessments["year"] = pd.to_numeric(assessments["year"], errors="coerce")
        assessments = assessments.dropna(subset=["year"]).copy()
        assessments["year"] = assessments["year"].astype(int)

        expenditures = expenditures.copy()
        if expenditures.empty:
            expenditures = years.assign(expenditures=0.0)
        expenditures["year"] = pd.to_numeric(expenditures["year"], errors="coerce")
        expenditures = expenditures.dropna(subset=["year"]).copy()
        expenditures["year"] = expenditures["year"].astype(int)
        expenditures["expenditures"] = pd.to_numeric(expenditures["expenditures"], errors="coerce").fillna(0.0)

        out = years.merge(assessments[["year", "annual_contribution", "special_assessment"]], on="year", how="left")
        out = out.merge(expenditures[["year", "expenditures"]], on="year", how="left")
        out[["annual_contribution", "special_assessment", "expenditures"]] = out[
            ["annual_contribution", "special_assessment", "expenditures"]
        ].fillna(0.0)
        out["total_contributions"] = out["annual_contribution"] + out["special_assessment"]
        inflation_factor = (1.0 + float(self.scenario.assumptions.inflation)) ** (out["year"] - analysis_year)
        out["total_contributions_real"] = out["total_contributions"] / inflation_factor
        out["expenditures_real"] = out["expenditures"] / inflation_factor
        out["cumulative_contributions"] = out["total_contributions"].cumsum()
        out["cumulative_contributions_real"] = out["total_contributions_real"].cumsum()
        out["cumulative_expenditures"] = out["expenditures"].cumsum()
        return out

    def _style_money_axis(self, axis) -> None:
        axis.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
        axis.grid(True, axis="y", alpha=0.25)

    def _finish(self, fig, path: Path) -> Path:
        fig.tight_layout()
        fig.savefig(path, dpi=180, bbox_inches="tight")
        plt.close(fig)
        return path

    def _plot_contributions(self, df: pd.DataFrame, path: Path) -> Path:
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.plot(df["year"], df["annual_contribution"], linewidth=2.5, label="Annual contribution")
        ax.plot(df["year"], df["special_assessment"], linewidth=2.0, label="Special assessment")
        ax.plot(df["year"], df["total_contributions_real"], linewidth=2.0, linestyle="--", label="Total, inflation-adjusted")
        ax2 = ax.twinx()
        ax2.plot(df["year"], df["cumulative_contributions"], color="0.25", linewidth=2.0, label="Cumulative total")
        ax2.plot(
            df["year"],
            df["cumulative_contributions_real"],
            color="0.45",
            linewidth=2.0,
            linestyle="--",
            label="Cumulative, inflation-adjusted",
        )
        ax.set_title("Reserve Contributions")
        ax.set_xlabel("Year")
        ax.set_ylabel("Annual dollars")
        ax2.set_ylabel("Cumulative dollars")
        self._style_money_axis(ax)
        self._style_money_axis(ax2)
        lines = ax.get_lines() + ax2.get_lines()
        ax.legend(lines, [line.get_label() for line in lines], loc="upper left")
        return self._finish(fig, path)

    def _plot_expenditures_vs_contributions(self, df: pd.DataFrame, path: Path) -> Path:
        fig, (ax, ax_bottom) = plt.subplots(2, 1, figsize=(11, 8), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
        ax.plot(df["year"], df["expenditures"], linewidth=2.2, label="Expenditures")
        ax.plot(df["year"], df["expenditures_real"], linewidth=2.0, linestyle="--", label="Expenditures, inflation-adjusted")
        ax.plot(df["year"], df["total_contributions"], linewidth=2.2, label="Contributions")
        ax.plot(
            df["year"],
            df["total_contributions_real"],
            linewidth=2.0,
            linestyle="--",
            label="Contributions, inflation-adjusted",
        )
        ax_bottom.plot(df["year"], df["cumulative_expenditures"], linewidth=2.2, label="Cumulative expenditures")
        ax_bottom.plot(df["year"], df["cumulative_contributions"], linewidth=2.2, label="Cumulative contributions")
        ax.set_title("Reserve Expenditures and Contributions")
        ax.set_ylabel("Annual dollars")
        ax_bottom.set_xlabel("Year")
        ax_bottom.set_ylabel("Cumulative dollars")
        self._style_money_axis(ax)
        self._style_money_axis(ax_bottom)
        ax.legend(loc="upper left")
        ax_bottom.legend(loc="upper left")
        return self._finish(fig, path)

    def _plot_reserve_balance(self, reserve_projection: pd.DataFrame, path: Path) -> Path:
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.plot(reserve_projection["year"], reserve_projection["end_balance"], linewidth=2.5, label="Ending reserve balance")
        if "funded_balance" in reserve_projection:
            ax.plot(reserve_projection["year"], reserve_projection["funded_balance"], linewidth=2.2, label="Fully funded balance")
        ax.axhline(0, color="0.25", linewidth=1)
        ax.set_title("Reserve Balance Projection")
        ax.set_xlabel("Year")
        ax.set_ylabel("Dollars")
        self._style_money_axis(ax)
        ax.legend(loc="upper left")
        return self._finish(fig, path)

    def _plot_percent_funded(self, reserve_projection: pd.DataFrame, path: Path) -> Path:
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.plot(reserve_projection["year"], reserve_projection["percent_funded"], linewidth=2.5)
        ax.axhline(100, color="0.25", linewidth=1, linestyle="--")
        ax.set_title("Percent Funded")
        ax.set_xlabel("Year")
        ax.set_ylabel("Percent")
        ax.yaxis.set_major_formatter(mtick.PercentFormatter())
        ax.grid(True, axis="y", alpha=0.25)
        return self._finish(fig, path)
