import os
from pydantic import BaseModel


class SolverParams(BaseModel):
    TRUE_THRESHOLD: float = 0.5
    APPLY_HEURISTICS: bool = True
    MODEL_SOLVER_VERBOSE: bool = False

    LIMIT_TIME_MINUTES_HEURISTICS: float = 3
    LIMIT_TIME_MINUTES_DETERMINISTIC: float = 3
    LIMIT_OPTIMALITY_GAP_DETERMINISTIC: float = 0.35
    LIMIT_OPTIMALITY_GAP_HEURISTICS: float = 0.75
    LIMIT_MEMORY_MB: int = 1024*8
    LIMIT_MULTI_THREAD: int = 6