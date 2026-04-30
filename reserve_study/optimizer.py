from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution, minimize

from .models import OptimizationResult
from .schedules import CollectionSchedule
from .study import FundedBalanceCalculator, ProjectionEngine, StudyResult


class ReserveOptimizer:
    def __init__(self, study_result: StudyResult):
        self.study_result = study_result
        self.scenario = study_result.scenario
        self.assumptions = study_result.scenario.assumptions

    @staticmethod
    def make_years(start_year: int, projection_years: int) -> np.ndarray:
        return np.arange(int(start_year), int(start_year) + int(projection_years), dtype=int)

    @staticmethod
    def make_min_balance_array(years, min_balance) -> np.ndarray:
        years = np.asarray(years, dtype=int)
        if np.isscalar(min_balance):
            return np.full(len(years), float(min_balance), dtype=float)
        if isinstance(min_balance, dict):
            return np.array([float(min_balance.get(int(year), 0.0)) for year in years], dtype=float)
        arr = np.asarray(min_balance, dtype=float)
        if len(arr) != len(years):
            raise ValueError("min_balance array must match number of projection years")
        return arr

    def get_existing_contributions(self, years) -> np.ndarray:
        base = self.study_result.collection_schedule.annual_df()
        if base.empty:
            return np.zeros(len(years), dtype=float)
        merged = pd.DataFrame({"year": years}).merge(base[["year", "contribution"]], on="year", how="left").fillna(0.0)
        return merged["contribution"].to_numpy(dtype=float)

    def get_existing_special_assessments(self, years) -> np.ndarray:
        base = self.study_result.collection_schedule.annual_df()
        if base.empty:
            return np.zeros(len(years), dtype=float)
        merged = pd.DataFrame({"year": years}).merge(base[["year", "special_assessment"]], on="year", how="left").fillna(0.0)
        return merged["special_assessment"].to_numpy(dtype=float)

    def resolve_special_assessments(self, years, mode: str = "zero", special_vector=None, special_dict=None, special_func=None) -> np.ndarray:
        years = np.asarray(years, dtype=int)
        if mode == "zero":
            return np.zeros(len(years), dtype=float)
        if mode == "existing":
            return self.get_existing_special_assessments(years)
        if mode == "fixed_vector":
            vec = np.asarray(special_vector, dtype=float)
            if len(vec) != len(years):
                raise ValueError("special_vector length must match number of years")
            return vec
        if mode == "fixed_dict":
            special_dict = special_dict or {}
            return np.array([float(special_dict.get(int(year), 0.0)) for year in years], dtype=float)
        if mode == "function":
            if special_func is None:
                raise ValueError("special_func is required for mode='function'")
            vec = np.asarray(special_func(years), dtype=float)
            if len(vec) != len(years):
                raise ValueError("special_func(years) must return one value per year")
            return vec
        raise ValueError("Unsupported special assessment mode")

    @staticmethod
    def transform_contributions(contribution_vector, round_to=None, floor_at_zero: bool = True) -> np.ndarray:
        vec = np.asarray(contribution_vector, dtype=float).copy()
        if floor_at_zero:
            vec = np.maximum(vec, 0.0)
        if round_to is not None and round_to > 0:
            vec = np.round(vec / round_to) * round_to
        return vec

    @staticmethod
    def contribution_fn_full_vector(params, years, assumptions) -> np.ndarray:
        params = np.asarray(params, dtype=float)
        if len(params) != len(years):
            raise ValueError("For full-vector mode, len(params) must equal len(years)")
        return params

    @staticmethod
    def contribution_fn_inflation_start_only(params, years, assumptions) -> np.ndarray:
        start_contribution = float(params[0])
        inflation = float(assumptions.inflation)
        k = np.arange(len(years), dtype=float)
        return start_contribution * (1.0 + inflation) ** k

    @staticmethod
    def contribution_fn_start_and_growth(params, years, assumptions) -> np.ndarray:
        start_contribution = float(params[0])
        growth_rate = float(params[1])
        k = np.arange(len(years), dtype=float)
        return start_contribution * (1.0 + growth_rate) ** k

    @staticmethod
    def contribution_fn_rise_then_plateau(params, years, assumptions) -> np.ndarray:
        start_contribution = float(params[0])
        annual_step = float(params[1])
        plateau_year_index = max(0, min(int(round(params[2])), len(years) - 1))
        return np.array(
            [
                start_contribution + annual_step * min(i, plateau_year_index)
                for i in range(len(years))
            ],
            dtype=float,
        )

    @staticmethod
    def contribution_fn_three_linear_then_inflation(params, years, assumptions) -> np.ndarray:
        start_contribution = float(params[0])
        step_1 = float(params[1])
        step_2 = float(params[2])
        step_3 = float(params[3])
        years_1 = max(4, min(6, int(round(params[4]))))
        years_2 = max(4, min(6, int(round(params[5]))))
        years_3 = max(4, min(6, int(round(params[6]))))
        inflation = float(assumptions.inflation)
        n = len(years)
        vals = np.zeros(n, dtype=float)
        vals[0] = start_contribution
        idx = 1
        current = start_contribution
        for years_in_regime, step in ((years_1, step_1), (years_2, step_2), (years_3, step_3)):
            for _ in range(years_in_regime):
                if idx >= n:
                    return vals
                current += step
                vals[idx] = current
                idx += 1
        while idx < n:
            current *= 1.0 + inflation
            vals[idx] = current
            idx += 1
        return vals

    def build_collection_schedule(self, years, contribution_vector, special_vector=None) -> CollectionSchedule:
        return self.study_result.collection_schedule.with_contributions(years, contribution_vector, special_vector=special_vector)

    def run_projection_from_contributions(self, years, contribution_vector, special_vector=None, starting_balance=None) -> tuple[CollectionSchedule, object]:
        collection_schedule = self.build_collection_schedule(years, contribution_vector, special_vector=special_vector)
        projection = ProjectionEngine.project(
            expenditure_schedule=self.study_result.expenditure_schedule,
            collection_schedule=collection_schedule,
            assumptions=self.assumptions,
            start_year=int(years[0]),
            projection_years=len(years),
            starting_balance=starting_balance,
        )
        return collection_schedule, projection

    def build_objective_inputs(self, params, contribution_fn, years, special_vector, transform_fn=None):
        contrib = np.asarray(contribution_fn(params, years, self.assumptions), dtype=float)
        if len(contrib) != len(years):
            raise ValueError("contribution_fn must return one contribution per year")
        if transform_fn is not None:
            contrib = np.asarray(transform_fn(contrib), dtype=float)
        _, projection = self.run_projection_from_contributions(years, contrib, special_vector=special_vector)
        projection_df = projection.to_dataframe()
        end_bal = projection_df["end_balance"].to_numpy(dtype=float)
        expenditures = projection_df["expenditures"].to_numpy(dtype=float)
        special = np.asarray(special_vector, dtype=float)
        return contrib, projection_df, end_bal, expenditures, special

    @staticmethod
    def common_constraint_penalty(contrib, end_bal, min_balance_array, objective_weights=None, extra_penalty_fn=None, params=None, projection=None, years=None, assumptions=None):
        objective_weights = objective_weights or {"constraint": 1e8}
        penalty_weight = float(objective_weights.get("constraint", 1e8))
        shortfall = np.maximum(min_balance_array - end_bal, 0.0)
        penalty = penalty_weight * np.sum(shortfall ** 2)
        if np.any(contrib < 0):
            penalty += penalty_weight * np.sum(np.maximum(-contrib, 0.0) ** 2)
        if extra_penalty_fn is not None:
            penalty += float(extra_penalty_fn(params, contrib, projection, years, assumptions))
        return penalty

    def objective_min_total_contributions(self, params, contribution_fn, years, special_vector, min_balance_array, transform_fn=None, objective_weights=None, extra_penalty_fn=None) -> float:
        contrib, projection, end_bal, _, _ = self.build_objective_inputs(params, contribution_fn, years, special_vector, transform_fn=transform_fn)
        penalty = self.common_constraint_penalty(contrib, end_bal, min_balance_array, objective_weights, extra_penalty_fn, params, projection, years, self.assumptions)
        return float(np.sum(contrib) + penalty)

    def objective_min_total_plus_smooth(self, params, contribution_fn, years, special_vector, min_balance_array, transform_fn=None, objective_weights=None, extra_penalty_fn=None) -> float:
        objective_weights = objective_weights or {"total": 1.0, "smooth": 1.0, "constraint": 1e8}
        contrib, projection, end_bal, _, _ = self.build_objective_inputs(params, contribution_fn, years, special_vector, transform_fn=transform_fn)
        total_term = float(objective_weights.get("total", 1.0)) * np.sum(contrib)
        smooth_term = float(objective_weights.get("smooth", 0.0)) * np.sum(np.diff(contrib) ** 2)
        penalty = self.common_constraint_penalty(contrib, end_bal, min_balance_array, objective_weights, extra_penalty_fn, params, projection, years, self.assumptions)
        return float(total_term + smooth_term + penalty)

    def objective_min_peak_contribution(self, params, contribution_fn, years, special_vector, min_balance_array, transform_fn=None, objective_weights=None, extra_penalty_fn=None) -> float:
        objective_weights = objective_weights or {"peak": 1.0, "total": 0.0, "constraint": 1e8}
        contrib, projection, end_bal, _, _ = self.build_objective_inputs(params, contribution_fn, years, special_vector, transform_fn=transform_fn)
        peak_term = float(objective_weights.get("peak", 1.0)) * np.max(contrib)
        total_term = float(objective_weights.get("total", 0.0)) * np.sum(contrib)
        penalty = self.common_constraint_penalty(contrib, end_bal, min_balance_array, objective_weights, extra_penalty_fn, params, projection, years, self.assumptions)
        return float(peak_term + total_term + penalty)

    def objective_min_short_term_burden(self, params, contribution_fn, years, special_vector, min_balance_array, transform_fn=None, objective_weights=None, extra_penalty_fn=None) -> float:
        objective_weights = objective_weights or {"short_term": 1.0, "constraint": 1e8}
        contrib, projection, end_bal, _, _ = self.build_objective_inputs(params, contribution_fn, years, special_vector, transform_fn=transform_fn)
        year_weights = np.linspace(1.0, 0.2, len(contrib))
        short_term_term = float(objective_weights.get("short_term", 1.0)) * np.sum(year_weights * contrib)
        penalty = self.common_constraint_penalty(contrib, end_bal, min_balance_array, objective_weights, extra_penalty_fn, params, projection, years, self.assumptions)
        return float(short_term_term + penalty)

    def objective_min_initial_raises_with_total_tradeoff(self, params, contribution_fn, years, special_vector, min_balance_array, transform_fn=None, objective_weights=None, extra_penalty_fn=None) -> float:
        objective_weights = objective_weights or {"initial_raise": 1.0, "total": 0.10, "constraint": 1e8, "funded_end_target": 1e10}
        contrib, projection, end_bal, _, _ = self.build_objective_inputs(params, contribution_fn, years, special_vector, transform_fn=transform_fn)
        diffs = np.diff(contrib)
        raise_weights = np.linspace(1.0, 0.2, max(len(contrib) - 1, 1))
        initial_raise_term = float(objective_weights.get("initial_raise", 1.0)) * np.sum(raise_weights * (diffs ** 2))
        total_term = float(objective_weights.get("total", 0.10)) * np.sum(contrib)
        penalty = self.common_constraint_penalty(contrib, end_bal, min_balance_array, objective_weights, extra_penalty_fn, params, projection, years, self.assumptions)
        funded_end = FundedBalanceCalculator.calculate(
            self.study_result.expenditure_schedule,
            self.assumptions,
            projection_years=len(years),
            method="current_cost_straight_line",
            funded_date="end",
            respect_one_time=True,
            inflate_result=True,
        )
        final_year = int(years[-1])
        final_fully_funded_balance = float(funded_end.loc[final_year])
        final_end_balance = float(end_bal[-1])
        final_percent_funded = 0.0 if final_fully_funded_balance <= 0 else final_end_balance / final_fully_funded_balance
        funded_target = 0.70
        funded_error = final_percent_funded - funded_target
        funded_penalty = float(objective_weights.get("funded_end_target", 1e10)) * (funded_error ** 2)
        return float(initial_raise_term + total_term + penalty + funded_penalty)

    def optimize(
        self,
        contribution_fn,
        objective_fn,
        initial_params,
        bounds,
        start_year: int | None = None,
        projection_years: int = 30,
        min_balance=0.0,
        special_mode: str = "zero",
        special_vector=None,
        special_dict=None,
        special_func=None,
        transform_fn=None,
        objective_weights=None,
        extra_penalty_fn=None,
        method: str = "SLSQP",
        options: dict | None = None,
    ) -> OptimizationResult:
        if start_year is None:
            start_year = pd.Timestamp(self.assumptions.analysis_date).year
        years = self.make_years(start_year, projection_years)
        min_balance_array = self.make_min_balance_array(years, min_balance)
        resolved_special = self.resolve_special_assessments(years, mode=special_mode, special_vector=special_vector, special_dict=special_dict, special_func=special_func)
        if options is None:
            options = {"maxiter": 2000, "ftol": 1e-9, "disp": False}

        def objective(params):
            return objective_fn(params, contribution_fn, years, resolved_special, min_balance_array, transform_fn, objective_weights, extra_penalty_fn)

        if method.lower() == "differential_evolution":
            result = differential_evolution(objective, bounds=bounds, **options)
        else:
            result = minimize(objective, x0=np.asarray(initial_params, dtype=float), bounds=bounds, method=method, options=options)

        best_params = np.asarray(result.x, dtype=float)
        best_contrib = np.asarray(contribution_fn(best_params, years, self.assumptions), dtype=float)
        if transform_fn is not None:
            best_contrib = np.asarray(transform_fn(best_contrib), dtype=float)
        collection_schedule, projection = self.run_projection_from_contributions(years, best_contrib, special_vector=resolved_special)
        diagnostics = {
            "success": bool(result.success),
            "status": int(getattr(result, "status", 0)),
            "message": str(getattr(result, "message", "")),
            "fun": float(result.fun),
            "x": best_params.tolist(),
            "years": years.tolist(),
        }
        return OptimizationResult(optimized_collection_schedule=collection_schedule, projection=projection, diagnostics=diagnostics)
