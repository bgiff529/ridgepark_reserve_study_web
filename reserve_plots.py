import calendar
import os
from pathlib import Path

MPL_CONFIG_DIR = Path(os.environ.get("MPLCONFIGDIR", "/tmp/reserve-study-mplconfig"))
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(MPL_CONFIG_DIR)
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", "/tmp/reserve-study-cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(CACHE_DIR)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd


def _money_axis(axis):
    axis.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))


def _prepare_assessment_plot_df(results):
    assumptions = results["assumptions"]
    analysis_year = int(pd.Timestamp(assumptions["analysis_date"]).year)
    inflation = float(assumptions["inflation"])

    plot_df = results["assessment_frame"].copy()
    plot_df.columns = plot_df.columns.str.strip()
    plot_df["year"] = pd.to_numeric(plot_df["year"], errors="coerce")
    plot_df = plot_df.dropna(subset=["year"]).copy()
    plot_df["year"] = plot_df["year"].astype(int)
    plot_df = plot_df.sort_values("year").reset_index(drop=True)

    plot_df["annual_contribution"] = pd.to_numeric(
        plot_df["annual_contribution"], errors="coerce"
    ).fillna(0.0)
    plot_df["special_assessment"] = pd.to_numeric(
        plot_df["special_assessment"], errors="coerce"
    ).fillna(0.0)
    plot_df["total_contributions"] = (
        plot_df["annual_contribution"] + plot_df["special_assessment"]
    )

    expenditures = results["expenditures_by_year_detail"].copy()
    expenditures["replacement_year"] = pd.to_numeric(
        expenditures["replacement_year"], errors="coerce"
    )
    expenditures["future_cost"] = pd.to_numeric(
        expenditures["future_cost"], errors="coerce"
    ).fillna(0.0)
    exp_by_year = (
        expenditures.dropna(subset=["replacement_year"])
        .groupby("replacement_year", as_index=False)["future_cost"]
        .sum()
        .rename(columns={"replacement_year": "year", "future_cost": "expenditures"})
    )
    exp_by_year["year"] = exp_by_year["year"].astype(int)

    plot_df = plot_df.merge(exp_by_year, on="year", how="left")
    plot_df["expenditures"] = plot_df["expenditures"].fillna(0.0)

    inflation_factor = (1 + inflation) ** (plot_df["year"] - analysis_year)
    plot_df["total_contributions_real"] = plot_df["total_contributions"] / inflation_factor
    plot_df["expenditures_real"] = plot_df["expenditures"] / inflation_factor
    plot_df["cumulative_contributions"] = plot_df["total_contributions"].cumsum()
    plot_df["cumulative_expenditures"] = plot_df["expenditures"].cumsum()

    return plot_df, analysis_year


def _find_milestone_info(df, annual_col, fraction, timeline_start, timeline_end):
    target = df[annual_col].sum() * fraction

    running_before = 0.0
    crossing_x = None
    crossing_month_year = None

    for _, row in df.iterrows():
        year = int(row["year"])
        annual_val = float(row[annual_col])
        running_after = running_before + annual_val

        if running_after >= target:
            frac_through_year = 0.0 if annual_val == 0 else (target - running_before) / annual_val
            crossing_x = year + frac_through_year
            month_num = min(max(int(frac_through_year * 12) + 1, 1), 12)
            crossing_month_year = f"{calendar.month_name[month_num]} {year}"
            break

        running_before = running_after

    if crossing_x is None:
        return {"x": None, "month_year": None, "timing_text": None}

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


def plot_reserve_contributions_over_time(results):
    plot_df, analysis_year = _prepare_assessment_plot_df(results)
    base_year = analysis_year
    last_year = int(plot_df["year"].max())

    contribution_plot = plot_df[["year", "annual_contribution", "special_assessment", "total_contributions_real"]].copy()
    contribution_plot = contribution_plot.rename(columns={"annual_contribution": "contribution"})

    cumulative_plot = plot_df[["year", "total_contributions_real"]].copy()
    cumulative_plot["cumulative_contributions_real"] = cumulative_plot["total_contributions_real"].cumsum()

    cumulative_plot_nominal = plot_df[["year", "total_contributions"]].copy()
    cumulative_plot_nominal["cumulative_contributions"] = cumulative_plot_nominal["total_contributions"].cumsum()

    cumulative_plot = pd.concat(
        [
            pd.DataFrame(
                {
                    "year": [base_year],
                    "total_contributions_real": [0.0],
                    "cumulative_contributions_real": [0.0],
                }
            ),
            cumulative_plot,
        ],
        ignore_index=True,
    )
    cumulative_plot_nominal = pd.concat(
        [
            pd.DataFrame(
                {
                    "year": [base_year],
                    "total_contributions": [0.0],
                    "cumulative_contributions": [0.0],
                }
            ),
            cumulative_plot_nominal,
        ],
        ignore_index=True,
    )

    quarter_info = _find_milestone_info(plot_df, "total_contributions_real", 0.25, base_year, last_year)
    half_info = _find_milestone_info(plot_df, "total_contributions_real", 0.50, base_year, last_year)

    fig, ax = plt.subplots(figsize=(11, 6))
    ax2 = ax.twinx()

    annual_color = plt.rcParams["axes.prop_cycle"].by_key()["color"][0]
    special_color = plt.rcParams["axes.prop_cycle"].by_key()["color"][1]
    real_total_color = plt.rcParams["axes.prop_cycle"].by_key()["color"][2]
    cumulative_color = "black"

    ax.plot(contribution_plot["year"], contribution_plot["contribution"], marker="o", markersize=4, linewidth=1.6, linestyle="-", color=annual_color)
    ax.plot(contribution_plot["year"], contribution_plot["special_assessment"], marker="o", markersize=4, linewidth=1.6, linestyle="-", color=special_color)
    ax.plot(contribution_plot["year"], contribution_plot["total_contributions_real"], linewidth=1.8, linestyle="--", color=real_total_color)
    ax2.plot(cumulative_plot_nominal["year"], cumulative_plot_nominal["cumulative_contributions"], color=cumulative_color, linewidth=1.8, linestyle="-")
    ax2.plot(cumulative_plot["year"], cumulative_plot["cumulative_contributions_real"], color=cumulative_color, linewidth=2.4, linestyle="--")

    ax.set_ylim(bottom=0)
    cum_max = max(
        cumulative_plot_nominal["cumulative_contributions"].max(),
        cumulative_plot["cumulative_contributions_real"].max(),
    )
    ax2.set_ylim(0, cum_max * 1.12 if cum_max else 1.0)

    milestones = [
        {"info": quarter_info, "headline": "Quarter of\n30-year Cumulative\nContributions\nCollected", "text_y": 0.96},
        {"info": half_info, "headline": "Half of\n30-year Cumulative\nContributions\nCollected", "text_y": 0.96},
    ]
    bbox_style = {
        "boxstyle": "round,pad=0.35,rounding_size=0.2",
        "facecolor": "white",
        "edgecolor": "black",
        "linestyle": "--",
        "linewidth": 1.2,
        "alpha": 0.95,
    }

    for milestone in milestones:
        info = milestone["info"]
        if info["x"] is None:
            continue
        ax2.axvline(x=info["x"], color="black", linewidth=1.4, linestyle=":", alpha=0.7)
        line_label_y = ax2.get_ylim()[1] * milestone["text_y"]
        label_text = (
            f'{milestone["headline"]}\n\n'
            f'{info["month_year"]}\n'
            f'{info["timing_text"]}'
        )
        ax2.annotate(
            label_text,
            xy=(info["x"], line_label_y),
            xytext=(0, 0),
            textcoords="offset points",
            ha="center",
            va="top",
            multialignment="center",
            fontsize=11,
            color="black",
            bbox=bbox_style,
        )

    ax.set_title("Reserve Contributions Over Time")
    ax.set_xlabel("Year")
    ax.set_ylabel("Annual Dollars")
    ax2.set_ylabel("Cumulative Dollars")
    all_years = sorted(set(cumulative_plot_nominal["year"]).union(set(cumulative_plot["year"])))
    ax.set_xticks(all_years)
    ax.tick_params(axis="x", rotation=45)
    x_right_limit = contribution_plot["year"].max() + 2
    ax.set_xlim(base_year, x_right_limit)
    _money_axis(ax)
    _money_axis(ax2)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def plot_expenditures_and_total_contributions(results):
    plot_df, _ = _prepare_assessment_plot_df(results)

    fig, ax = plt.subplots(figsize=(11, 6))
    ax2 = ax.twinx()

    exp_color = "red"
    contrib_color = "green"
    ax.plot(plot_df["year"], plot_df["expenditures"], marker="o", markersize=4, linewidth=1.8, linestyle="-", color=exp_color)
    ax.plot(plot_df["year"], plot_df["expenditures_real"], linewidth=1.8, linestyle="--", color=exp_color)
    ax2.plot(plot_df["year"], plot_df["total_contributions"], marker="o", markersize=4, linewidth=1.8, linestyle="-", color=contrib_color)
    ax2.plot(plot_df["year"], plot_df["total_contributions_real"], linewidth=1.8, linestyle="--", color=contrib_color)

    ax.set_title("Expenditures and Total Contributions Over Time")
    ax.set_xlabel("Year")
    ax.set_ylabel("Annual Expenditures", color=exp_color)
    ax2.set_ylabel("Annual Total Contributions", color=contrib_color)
    ax.set_ylim(bottom=0)
    ax2.set_ylim(bottom=0)
    ax.set_xticks(sorted(plot_df["year"].unique()))
    ax.tick_params(axis="x", rotation=45)
    ax.tick_params(axis="y", colors=exp_color)
    ax2.tick_params(axis="y", colors=contrib_color)
    ax.spines["left"].set_color(exp_color)
    ax2.spines["right"].set_color(contrib_color)
    ax.yaxis.label.set_color(exp_color)
    ax2.yaxis.label.set_color(contrib_color)
    ax.set_xlim(plot_df["year"].min(), plot_df["year"].max() + 2)
    _money_axis(ax)
    _money_axis(ax2)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def plot_annual_and_cumulative_expenditures_vs_contributions(results):
    plot_df, _ = _prepare_assessment_plot_df(results)

    exp_color = "red"
    contrib_color = "green"
    fig, (ax, ax_bottom) = plt.subplots(
        2,
        1,
        figsize=(11, 10),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 2], "hspace": 0.08},
    )

    ax.plot(plot_df["year"], plot_df["expenditures"], marker="o", markersize=4, linewidth=1.8, linestyle="-", color=exp_color)
    ax.plot(plot_df["year"], plot_df["expenditures_real"], linewidth=1.8, linestyle="--", color=exp_color)
    ax.plot(plot_df["year"], plot_df["total_contributions"], marker="o", markersize=4, linewidth=1.8, linestyle="-", color=contrib_color)
    ax.plot(plot_df["year"], plot_df["total_contributions_real"], linewidth=1.8, linestyle="--", color=contrib_color)
    ax.set_ylabel("Annual Dollars")
    ax.set_ylim(bottom=0)
    _money_axis(ax)
    ax.grid(True, axis="y", alpha=0.3)

    line_exp, = ax_bottom.plot(plot_df["year"], plot_df["cumulative_expenditures"], marker="o", markersize=4, linewidth=2.0, linestyle="-", color=exp_color, label="Expenditures")
    line_contrib, = ax_bottom.plot(plot_df["year"], plot_df["cumulative_contributions"], marker="o", markersize=4, linewidth=2.0, linestyle="-", color=contrib_color, label="Contributions")
    ax_bottom.set_xlabel("Year")
    ax_bottom.set_ylabel("Cumulative Dollars")
    ax_bottom.set_ylim(bottom=0)
    _money_axis(ax_bottom)
    ax_bottom.grid(True, axis="y", alpha=0.3)
    ax_bottom.set_xticks(sorted(plot_df["year"].unique()))
    ax_bottom.tick_params(axis="x", rotation=45)
    ax_bottom.set_xlim(plot_df["year"].min(), plot_df["year"].max() + 2)
    ax_bottom.legend(handles=[line_exp, line_contrib], loc="lower right")
    fig.tight_layout()
    return fig


def plot_annual_and_cumulative_reserve_contributions(results):
    plot_df, _ = _prepare_assessment_plot_df(results)

    fig, ax = plt.subplots(figsize=(11, 6))
    ax2 = ax.twinx()
    green = "green"

    ax.bar(plot_df["year"], plot_df["annual_contribution"], width=0.8, color=green, alpha=0.35, label="Annual contribution")
    ax.bar(plot_df["year"], plot_df["special_assessment"], width=0.8, bottom=plot_df["annual_contribution"], color=green, alpha=0.7, label="Special assessment")
    ax2.plot(plot_df["year"], plot_df["cumulative_contributions"], color=green, linewidth=2.5, marker="o", markersize=4, label="Cumulative contributions")

    ax.set_title("Annual and Cumulative Reserve Contributions")
    ax.set_xlabel("Year")
    ax.set_ylabel("Annual Reserve Contributions", color=green)
    ax2.set_ylabel("Cumulative Reserve Contributions", color=green)
    ax.set_xticks(plot_df["year"])
    ax.set_xlim(plot_df["year"].min() - 0.5, plot_df["year"].max() + 0.5)
    ax.set_ylim(bottom=0)
    ax2.set_ylim(bottom=0)
    ax.tick_params(axis="x", rotation=45)
    ax.tick_params(axis="y", colors=green)
    ax2.tick_params(axis="y", colors=green)
    _money_axis(ax)
    _money_axis(ax2)
    ax.grid(True, axis="y", alpha=0.3)

    handles1, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(handles1 + handles2, labels1 + labels2, loc="upper left")
    fig.tight_layout()
    return fig


def plot_annual_and_cumulative_contributions_and_expenditures(results):
    plot_df, _ = _prepare_assessment_plot_df(results)

    green = "green"
    red = "red"
    fig, ax = plt.subplots(figsize=(12, 6.5))
    ax2 = ax.twinx()

    ax.bar(plot_df["year"], plot_df["total_contributions"], width=0.75, color=green, alpha=0.35, label="Annual reserve contributions", zorder=2)
    ax.bar(plot_df["year"], plot_df["expenditures"], width=0.75, color=red, alpha=0.35, label="Annual expenditures", zorder=3)
    ax2.plot(plot_df["year"], plot_df["cumulative_contributions"], color=green, linewidth=2.5, marker="o", markersize=4, label="Cumulative reserve contributions", zorder=4)
    ax2.plot(plot_df["year"], plot_df["cumulative_expenditures"], color=red, linewidth=2.5, marker="o", markersize=4, label="Cumulative expenditures", zorder=5)

    ax.set_title("Annual and Cumulative Reserve Contributions and Expenditures")
    ax.set_xlabel("Year")
    ax.set_ylabel("Annual Dollars")
    ax2.set_ylabel("Cumulative Dollars")
    ax.set_xticks(plot_df["year"])
    ax.tick_params(axis="x", rotation=45)
    ax.set_ylim(bottom=0)
    ax2.set_ylim(bottom=0)
    _money_axis(ax)
    _money_axis(ax2)
    ax.grid(True, axis="y", alpha=0.3)

    handles1, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(handles1 + handles2, labels1 + labels2, loc="upper left", bbox_to_anchor=(0.18, 1.0))
    fig.tight_layout()
    return fig


def plot_reserve_balance(results):
    proj = results["reserve_projection"].copy()
    proj.columns = proj.columns.str.strip()
    proj["year"] = pd.to_numeric(proj["year"], errors="coerce")
    proj["end_balance"] = pd.to_numeric(proj["end_balance"], errors="coerce")
    proj = proj.dropna(subset=["year", "end_balance"]).copy()
    proj["year"] = proj["year"].astype(int)
    proj = proj.sort_values("year").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(11, 6))
    balance_color = plt.rcParams["axes.prop_cycle"].by_key()["color"][0]
    ax.plot(proj["year"], proj["end_balance"], marker="o", markersize=4, linewidth=2.0, linestyle="-", color=balance_color)
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
    _money_axis(ax)
    ax.grid(True, axis="y", alpha=0.3)

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

    fig.tight_layout()
    return fig


def build_all_plots(results):
    return [
        ("Reserve Contributions Over Time", plot_reserve_contributions_over_time(results)),
        ("Expenditures and Total Contributions Over Time", plot_expenditures_and_total_contributions(results)),
        ("Annual and Cumulative Expenditures vs Contributions", plot_annual_and_cumulative_expenditures_vs_contributions(results)),
        ("Annual and Cumulative Reserve Contributions", plot_annual_and_cumulative_reserve_contributions(results)),
        ("Annual and Cumulative Reserve Contributions and Expenditures", plot_annual_and_cumulative_contributions_and_expenditures(results)),
        ("Reserve Balance", plot_reserve_balance(results)),
    ]
