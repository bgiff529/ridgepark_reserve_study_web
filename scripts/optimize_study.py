from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reserve_study import ReserveOptimizer, ReserveStudy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Optimize reserve contribution schedules using the OO package")
    parser.add_argument("variant", nargs="?", default="2026_brendan_plan")
    parser.add_argument("--legacy-root", default=None, help="Optional external project root. Defaults to this OO project.")
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--projection-years", type=int, default=30)
    parser.add_argument("--min-balance", type=float, default=200000.0)
    parser.add_argument("--start-contribution", type=float, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    study = ReserveStudy.from_variant(args.variant, scenario_root=args.legacy_root, output_root=args.output_root)
    study_results = study.run(projection_years=args.projection_years)
    study_results.write_outputs()

    optimizer = ReserveOptimizer(study_results)
    analysis_year = study.scenario.assumptions.analysis_year
    start_contribution = args.start_contribution
    if start_contribution is None:
        start_contribution = float(study.scenario.collection_schedule.annual_for_year(analysis_year).contribution)

    result = optimizer.optimize(
        contribution_fn=optimizer.contribution_fn_three_linear_then_inflation,
        objective_fn=optimizer.objective_min_total_plus_smooth,
        initial_params=[start_contribution, 20000.0, 20000.0, 20000.0, 5, 5, 5],
        bounds=[
            (start_contribution, start_contribution),
            (0.0, 100000.0),
            (0.0, 100000.0),
            (0.0, 100000.0),
            (4, 6),
            (4, 6),
            (4, 6),
        ],
        start_year=analysis_year,
        projection_years=args.projection_years,
        min_balance=args.min_balance,
        special_mode="zero",
        transform_fn=lambda values: optimizer.transform_contributions(values, round_to=100.0),
        method="differential_evolution",
        options={
            "maxiter": 200,
            "popsize": 12,
            "tol": 0.01,
            "mutation": (0.1, 1.0),
            "recombination": 0.7,
            "seed": 42,
            "polish": False,
            "disp": False,
        },
    )
    output_root = study_results.write_optimization_result(result)
    print(result.diagnostics)
    print(f"Wrote optimization outputs to {output_root}")


if __name__ == "__main__":
    main()
