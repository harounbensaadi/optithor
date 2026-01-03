# src/optithor/lp_solver.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from scipy.optimize import linprog

from .config import SolverConfig


@dataclass(frozen=True, slots=True)
class LpSolution:
    success: bool
    message: str
    x: np.ndarray | None


def solve_linear_program(
    a_eq: np.ndarray,
    b_eq: np.ndarray,
    num_variables: int,
    solver_config: SolverConfig,
) -> LpSolution:
    """
    Solve a linear program:
        minimize c^T x
        subject to A_eq x = b_eq
                   bounds on x
    """
    cost_vector = np.full(
        shape=(num_variables,),
        fill_value=float(solver_config.default_cost),
        dtype=float,
    )

    bounds: List[Tuple[float, float]] = [
        (float(solver_config.lower_bound), float(solver_config.upper_bound))
    ] * num_variables

    result = linprog(
        cost_vector,
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=bounds,
        method=solver_config.method,
    )

    if not bool(result.success):
        return LpSolution(success=False, message=str(result.message), x=None)

    return LpSolution(success=True, message=str(result.message), x=result.x)
