from __future__ import annotations

import calendar
from pathlib import Path
import warnings

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
            self._plot_reserve_contributions_over_time(plot_df, output_dir / "reserve_contributions_over_time.pdf"),
            self._plot_expenditures_and_total_contributions(
                plot_df, output_dir / "expenditures_and_total_contributions.pdf"
            ),
            self._plot_annual_and_cumulative_expenditures_vs_contributions(
                plot_df, output_dir / "annual_and_cumulative_expenditures_vs_contributions.pdf"
            ),
            self._plot_annual_and_cumulative_reserve_contributions(
                plot_df, output_dir / "annual_and_cumulative_reserve_contributions.pdf"
            ),
            self._plot_annual_and_cumulative_contributions_and_expenditures(
                plot_df, output_dir / "annual_and_cumulative_contributions_and_expenditures.pdf"
            ),
            self._plot_reserve_balance_annotated(reserve_projection, output_dir / "reserve_balance.pdf"),
            self._plot_contributions(plot_df, output_dir / "contributions_detail.pdf"),
            self._plot_expenditures_vs_contributions(plot_df, output_dir / "expenditures_vs_contributions_detail.pdf"),
            self._plot_reserve_balance(reserve_projection, output_dir / "reserve_balance_vs_fully_funded.pdf"),
            self._plot_percent_funded(reserve_projection, output_dir / "percent_funded.pdf"),
        ]
        return paths

    def _build_plot_frame(self, assessments: pd.DataFrame, expenditures: pd.DataFrame) -> pd.DataFrame:
        analysis_year = int(self.scenario.assumptions.analysis_year)
        projection_years = int(self.study_results.projection_years)
        years = pd.DataFrame({"year": np.arange(analysis_year, analysis_year + projection_years, dtype=int)})

        assessments = assessments.copy()
        if assessments.empty:
            assessments = years.assign(annual_contribution=0.0, special_assessment=0.0, additional_income=0.0)
        if "annual_contribution" not in assessments.columns and "contribution" in assessments.columns:
            assessments = assessments.rename(columns={"contribution": "annual_contribution"})
        for column in ["annual_contribution", "special_assessment", "additional_income"]:
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

        out = years.merge(assessments[["year", "annual_contribution", "special_assessment", "additional_income"]], on="year", how="left")
        out = out.merge(expenditures[["year", "expenditures"]], on="year", how="left")
        out[["annual_contribution", "special_assessment", "additional_income", "expenditures"]] = out[
            ["annual_contribution", "special_assessment", "additional_income", "expenditures"]
        ].fillna(0.0)
        out["total_contributions"] = out["annual_contribution"] + out["special_assessment"] + out["additional_income"]
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
        path = path.with_suffix(".pdf")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="This figure includes Axes that are not compatible")
            fig.tight_layout()
        fig.savefig(path, dpi=180, bbox_inches="tight")
        plt.close(fig)
        return path

    def _find_milestone_info(
        self, df: pd.DataFrame, annual_col: str, fraction: float, timeline_start: int, timeline_end: int
    ) -> dict[str, object]:
        target = df[annual_col].sum() * fraction
        running_before = 0.0

        for _, row in df.iterrows():
            year = int(row["year"])
            annual_val = float(row[annual_col])
            running_after = running_before + annual_val

            if running_after >= target:
                frac_through_year = 0.0 if annual_val == 0 else (target - running_before) / annual_val
                crossing_x = year + frac_through_year
                month_num = min(max(int(frac_through_year * 12) + 1, 1), 12)
                crossing_month_year = f"{calendar.month_name[month_num]} {year}"
                timeline_fraction_x = timeline_start + (timeline_end - timeline_start) * fraction
                delta_years = crossing_x - timeline_fraction_x
                abs_years = abs(delta_years)
                whole_years = int(abs_years)
                whole_months = int(round((abs_years - whole_years) * 12))

                if whole_months == 12:
                    whole_years += 1
                    whole_months = 0

                if abs_years < 1 / 24:
                    timing_text = "On time"
                elif delta_years < 0:
                    timing_text = f"{whole_years} years, {whole_months} months early"
                else:
                    timing_text = f"{whole_years} years, {whole_months} months late"

                return {"x": crossing_x, "month_year": crossing_month_year, "timing_text": timing_text}

            running_before = running_after

        return {"x": None, "month_year": None, "timing_text": None}

    def _plot_reserve_contributions_over_time(self, df: pd.DataFrame, path: Path) -> Path:
        base_year = int(self.scenario.assumptions.analysis_year)
        last_year = int(df["year"].max())
        cumulative_real = df[["year", "total_contributions_real"]].copy()
        cumulative_real["cumulative_contributions_real"] = cumulative_real["total_contributions_real"].cumsum()
        cumulative_nominal = df[["year", "total_contributions"]].copy()
        cumulative_nominal["cumulative_contributions"] = cumulative_nominal["total_contributions"].cumsum()
        cumulative_real = pd.concat(
            [
                pd.DataFrame(
                    {"year": [base_year], "total_contributions_real": [0.0], "cumulative_contributions_real": [0.0]}
                ),
                cumulative_real,
            ],
            ignore_index=True,
        )
        cumulative_nominal = pd.concat(
            [
                pd.DataFrame(
                    {"year": [base_year], "total_contributions": [0.0], "cumulative_contributions": [0.0]}
                ),
                cumulative_nominal,
            ],
            ignore_index=True,
        )

        quarter_info = self._find_milestone_info(df, "total_contributions_real", 0.25, base_year, last_year)
        half_info = self._find_milestone_info(df, "total_contributions_real", 0.50, base_year, last_year)

        fig, ax = plt.subplots(figsize=(11, 6))
        ax2 = ax.twinx()
        colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        ax.plot(df["year"], df["annual_contribution"], marker="o", markersize=4, linewidth=1.6, color=colors[0], label="Assessment contribution")
        ax.plot(df["year"], df["special_assessment"], marker="o", markersize=4, linewidth=1.6, color=colors[1], label="Special assessment")
        ax.plot(df["year"], df["additional_income"], marker="o", markersize=4, linewidth=1.6, color=colors[3], label="Additional Income")
        ax.plot(df["year"], df["total_contributions_real"], linewidth=1.8, linestyle="--", color=colors[2], label="Total, inflation-adjusted")
        ax2.plot(
            cumulative_nominal["year"],
            cumulative_nominal["cumulative_contributions"],
            color="black",
            linewidth=1.8,
        )
        ax2.plot(
            cumulative_real["year"],
            cumulative_real["cumulative_contributions_real"],
            color="black",
            linewidth=2.4,
            linestyle="--",
        )

        ax.set_ylim(bottom=0)
        cum_max = max(
            cumulative_nominal["cumulative_contributions"].max(),
            cumulative_real["cumulative_contributions_real"].max(),
        )
        ax2.set_ylim(0, cum_max * 1.12 if cum_max else 1.0)
        bbox_style = {
            "boxstyle": "round,pad=0.35,rounding_size=0.2",
            "facecolor": "white",
            "edgecolor": "black",
            "linestyle": "--",
            "linewidth": 1.2,
            "alpha": 0.95,
        }
        for info, headline in [
            (quarter_info, "Quarter of\n30-year Cumulative\nReserve Inflows\nCollected"),
            (half_info, "Half of\n30-year Cumulative\nReserve Inflows\nCollected"),
        ]:
            if info["x"] is None:
                continue
            ax2.axvline(x=info["x"], color="black", linewidth=1.4, linestyle=":", alpha=0.7)
            ax2.annotate(
                f'{headline}\n\n{info["month_year"]}\n{info["timing_text"]}',
                xy=(info["x"], ax2.get_ylim()[1] * 0.96),
                xytext=(0, 0),
                textcoords="offset points",
                ha="center",
                va="top",
                multialignment="center",
                fontsize=11,
                color="black",
                bbox=bbox_style,
            )

        ax.set_title("Reserve Inflows Over Time")
        ax.set_xlabel("Year")
        ax.set_ylabel("Annual Dollars")
        ax2.set_ylabel("Cumulative Dollars")
        all_years = sorted(set(cumulative_nominal["year"]).union(set(cumulative_real["year"])))
        ax.set_xticks(all_years)
        ax.tick_params(axis="x", rotation=45)
        ax.set_xlim(base_year, df["year"].max() + 2)
        self._style_money_axis(ax)
        self._style_money_axis(ax2)
        lines = ax.get_lines() + ax2.get_lines()
        ax.legend(lines, [line.get_label() for line in lines], loc="upper left")
        return self._finish(fig, path)

    def _plot_expenditures_and_total_contributions(self, df: pd.DataFrame, path: Path) -> Path:
        fig, ax = plt.subplots(figsize=(11, 6))
        ax2 = ax.twinx()
        exp_color = "red"
        contrib_color = "green"
        ax.plot(df["year"], df["expenditures"], marker="o", markersize=4, linewidth=1.8, color=exp_color)
        ax.plot(df["year"], df["expenditures_real"], linewidth=1.8, linestyle="--", color=exp_color)
        ax2.plot(df["year"], df["total_contributions"], marker="o", markersize=4, linewidth=1.8, color=contrib_color)
        ax2.plot(df["year"], df["total_contributions_real"], linewidth=1.8, linestyle="--", color=contrib_color)
        ax.set_title("Expenditures and Total Reserve Inflows Over Time")
        ax.set_xlabel("Year")
        ax.set_ylabel("Annual Expenditures", color=exp_color)
        ax2.set_ylabel("Annual Total Reserve Inflows", color=contrib_color)
        ax.set_ylim(bottom=0)
        ax2.set_ylim(bottom=0)
        ax.set_xticks(sorted(df["year"].unique()))
        ax.tick_params(axis="x", rotation=45)
        ax.tick_params(axis="y", colors=exp_color)
        ax2.tick_params(axis="y", colors=contrib_color)
        ax.spines["left"].set_color(exp_color)
        ax2.spines["right"].set_color(contrib_color)
        ax.yaxis.label.set_color(exp_color)
        ax2.yaxis.label.set_color(contrib_color)
        ax.set_xlim(df["year"].min(), df["year"].max() + 2)
        self._style_money_axis(ax)
        self._style_money_axis(ax2)
        return self._finish(fig, path)

    def _plot_annual_and_cumulative_expenditures_vs_contributions(self, df: pd.DataFrame, path: Path) -> Path:
        exp_color = "red"
        contrib_color = "green"
        fig, (ax, ax_bottom) = plt.subplots(
            2, 1, figsize=(11, 10), sharex=True, gridspec_kw={"height_ratios": [3, 2], "hspace": 0.08}
        )
        ax.plot(df["year"], df["expenditures"], marker="o", markersize=4, linewidth=1.8, color=exp_color)
        ax.plot(df["year"], df["expenditures_real"], linewidth=1.8, linestyle="--", color=exp_color)
        ax.plot(df["year"], df["total_contributions"], marker="o", markersize=4, linewidth=1.8, color=contrib_color)
        ax.plot(df["year"], df["total_contributions_real"], linewidth=1.8, linestyle="--", color=contrib_color)
        ax.set_ylabel("Annual Dollars")
        ax.set_ylim(bottom=0)
        self._style_money_axis(ax)

        line_exp, = ax_bottom.plot(
            df["year"],
            df["cumulative_expenditures"],
            marker="o",
            markersize=4,
            linewidth=2.0,
            color=exp_color,
            label="Expenditures",
        )
        line_contrib, = ax_bottom.plot(
            df["year"],
            df["cumulative_contributions"],
            marker="o",
            markersize=4,
            linewidth=2.0,
            color=contrib_color,
            label="Reserve inflows",
        )
        ax_bottom.set_xlabel("Year")
        ax_bottom.set_ylabel("Cumulative Dollars")
        ax_bottom.set_ylim(bottom=0)
        self._style_money_axis(ax_bottom)
        ax_bottom.set_xticks(sorted(df["year"].unique()))
        ax_bottom.tick_params(axis="x", rotation=45)
        ax_bottom.set_xlim(df["year"].min(), df["year"].max() + 2)
        ax_bottom.legend(handles=[line_exp, line_contrib], loc="lower right")
        return self._finish(fig, path)

    def _plot_annual_and_cumulative_reserve_contributions(self, df: pd.DataFrame, path: Path) -> Path:
        fig, ax = plt.subplots(figsize=(11, 6))
        ax2 = ax.twinx()
        green = "green"
        ax.bar(
            df["year"],
            df["annual_contribution"],
            width=0.8,
            color=green,
            alpha=0.35,
            label="Assessment contribution",
        )
        ax.bar(
            df["year"],
            df["special_assessment"],
            width=0.8,
            bottom=df["annual_contribution"],
            color=green,
            alpha=0.7,
            label="Special assessment",
        )
        ax.bar(
            df["year"],
            df["additional_income"],
            width=0.8,
            bottom=df["annual_contribution"] + df["special_assessment"],
            color="tab:blue",
            alpha=0.55,
            label="Additional Income",
        )
        ax2.plot(
            df["year"],
            df["cumulative_contributions"],
            color=green,
            linewidth=2.5,
            marker="o",
            markersize=4,
            label="Cumulative reserve inflows",
        )
        ax.set_title("Annual and Cumulative Reserve Inflows")
        ax.set_xlabel("Year")
        ax.set_ylabel("Annual Reserve Inflows", color=green)
        ax2.set_ylabel("Cumulative Reserve Inflows", color=green)
        ax.set_xticks(df["year"])
        ax.set_xlim(df["year"].min() - 0.5, df["year"].max() + 0.5)
        ax.set_ylim(bottom=0)
        ax2.set_ylim(bottom=0)
        ax.tick_params(axis="x", rotation=45)
        ax.tick_params(axis="y", colors=green)
        ax2.tick_params(axis="y", colors=green)
        self._style_money_axis(ax)
        self._style_money_axis(ax2)
        handles1, labels1 = ax.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(handles1 + handles2, labels1 + labels2, loc="upper left")
        return self._finish(fig, path)

    def _plot_annual_and_cumulative_contributions_and_expenditures(self, df: pd.DataFrame, path: Path) -> Path:
        fig, ax = plt.subplots(figsize=(12, 6.5))
        ax2 = ax.twinx()
        green = "green"
        red = "red"
        ax.bar(
            df["year"],
            df["annual_contribution"],
            width=0.75,
            color=green,
            alpha=0.35,
            label="Assessment contribution",
            zorder=2,
        )
        ax.bar(
            df["year"],
            df["special_assessment"],
            width=0.75,
            bottom=df["annual_contribution"],
            color=green,
            alpha=0.7,
            label="Special assessment",
            zorder=2,
        )
        ax.bar(
            df["year"],
            df["additional_income"],
            width=0.75,
            bottom=df["annual_contribution"] + df["special_assessment"],
            color="tab:blue",
            alpha=0.55,
            label="Additional Income",
            zorder=2,
        )
        ax.bar(
            df["year"],
            df["expenditures"],
            width=0.75,
            color=red,
            alpha=0.35,
            label="Annual expenditures",
            zorder=3,
        )
        ax2.plot(
            df["year"],
            df["cumulative_contributions"],
            color=green,
            linewidth=2.5,
            marker="o",
            markersize=4,
            label="Cumulative reserve inflows",
            zorder=4,
        )
        ax2.plot(
            df["year"],
            df["cumulative_expenditures"],
            color=red,
            linewidth=2.5,
            marker="o",
            markersize=4,
            label="Cumulative expenditures",
            zorder=5,
        )
        ax.set_title("Annual and Cumulative Reserve Inflows and Expenditures")
        ax.set_xlabel("Year")
        ax.set_ylabel("Annual Dollars")
        ax2.set_ylabel("Cumulative Dollars")
        ax.set_xticks(df["year"])
        ax.tick_params(axis="x", rotation=45)
        ax.set_ylim(bottom=0)
        ax2.set_ylim(bottom=0)
        self._style_money_axis(ax)
        self._style_money_axis(ax2)
        handles1, labels1 = ax.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(handles1 + handles2, labels1 + labels2, loc="upper left", bbox_to_anchor=(0.18, 1.0))
        return self._finish(fig, path)

    def _plot_reserve_balance_annotated(self, reserve_projection: pd.DataFrame, path: Path) -> Path:
        proj = reserve_projection.copy()
        proj["year"] = pd.to_numeric(proj["year"], errors="coerce")
        proj["end_balance"] = pd.to_numeric(proj["end_balance"], errors="coerce")
        proj = proj.dropna(subset=["year", "end_balance"]).copy()
        proj["year"] = proj["year"].astype(int)
        proj = proj.sort_values("year").reset_index(drop=True)

        fig, ax = plt.subplots(figsize=(11, 6))
        balance_color = plt.rcParams["axes.prop_cycle"].by_key()["color"][0]
        ax.plot(
            proj["year"],
            proj["end_balance"],
            marker="o",
            markersize=4,
            linewidth=2.0,
            color=balance_color,
        )
        ax.set_title("Reserve Balance")
        ax.set_xlabel("Year")
        ax.set_ylabel("Reserve Balance", color=balance_color)
        ax.tick_params(axis="x", rotation=45)
        ax.tick_params(axis="y", colors=balance_color)
        ax.spines["left"].set_color(balance_color)
        ax.yaxis.label.set_color(balance_color)
        ax.set_xticks(proj["year"])
        ax.set_xlim(proj["year"].min(), proj["year"].max() + 2)
        ax.set_ylim(bottom=0)
        self._style_money_axis(ax)

        for _, row in proj.iterrows():
            ax.annotate(
                f'${row["end_balance"]:,.0f}',
                xy=(row["year"], row["end_balance"]),
                xytext=(0, 6),
                textcoords="offset points",
                ha="center",
                va="bottom",
                rotation=90,
                fontsize=9,
                color=balance_color,
            )

        return self._finish(fig, path)

    def _plot_contributions(self, df: pd.DataFrame, path: Path) -> Path:
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.plot(df["year"], df["annual_contribution"], linewidth=2.5, label="Assessment contribution")
        ax.plot(df["year"], df["special_assessment"], linewidth=2.0, label="Special assessment")
        ax.plot(df["year"], df["additional_income"], linewidth=2.0, label="Additional Income")
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
        ax.set_title("Reserve Inflows")
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
        ax.plot(df["year"], df["total_contributions"], linewidth=2.2, label="Reserve inflows")
        ax.plot(
            df["year"],
            df["total_contributions_real"],
            linewidth=2.0,
            linestyle="--",
            label="Reserve inflows, inflation-adjusted",
        )
        ax_bottom.plot(df["year"], df["cumulative_expenditures"], linewidth=2.2, label="Cumulative expenditures")
        ax_bottom.plot(df["year"], df["cumulative_contributions"], linewidth=2.2, label="Cumulative reserve inflows")
        ax.set_title("Reserve Expenditures and Inflows")
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
