from abc import ABC, ABCMeta, abstractmethod
import uuid
import time, threading
from datetime import datetime, timezone
from pyscipopt import SCIP_PARAMSETTING # type: ignore
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from ortools.sat.python import cp_model
from pydantic import BaseModel
from typing import Any, Dict, Generic, Type, Optional, TypeVar, final

from src.stitchlab_optimization.solver.engine import SolverEngine
from src.stitchlab_optimization.solver.status import SolverStatus
from src.stitchlab_optimization.tools.utils import monitor_resources

from src.stitchlab_optimization.solver.config import SolverConfig
SOLVER_CONFIG = SolverConfig()


ParamsBaseModel = TypeVar("ParamsBaseModel", bound="ModelParams")
SolutionBaseModel = TypeVar("SolutionBaseModel", bound=BaseModel)

class ModelParams(BaseModel, ABC):
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


class ModelMeta(ABCMeta):
    def __new__(mcls, name, bases, attrs):
        cls = super().__new__(mcls, name, bases, attrs)

        if "name" not in attrs:
            attrs["name"] = name

        # Skip base class
        if ABC in bases:
            return cls

        # Enforce that each subclass defines `builders`
        if "builders_registry" not in attrs:
            raise TypeError(f"{name} must define class-level attribute `builders_registry`.")

        # Enforce correct type
        if not isinstance(attrs["builders_registry"], dict):
            raise TypeError(f"{name}.builders_registry must be a dict[SolverEngine, Type[ModelBuilder].")

        return cls


class ModelBuilder(Generic[ParamsBaseModel, SolutionBaseModel], ABC):
    params: ParamsBaseModel
    solution: Optional[SolutionBaseModel] = None
    solver_engine: SolverEngine
    solver_status: SolverStatus
    model: Any = None
    model_output: Any = None
    model_vars: Optional[Dict[str, Any]] = None  # Mandatory for OR-Tools CPSAT
    runtime_message: str = ""
    runtime_seconds: float = 0
    
    @final
    def __init__(self, params: ParamsBaseModel, solver_engine: SolverEngine):
        self.params = params
        self.solver_engine = solver_engine
        self.solver_status = SolverStatus.UNSOLVED

    @final
    def _set_model(self, model: Any):
        self.model = model

    @final
    def execute(self) -> Optional[SolutionBaseModel]:
        self.build()

        if self.model is None:
            raise ValueError("Model must be built before execution.")
        
        if self.solver_engine == SolverEngine.ORTOOLS_CPSAT and self.model_vars is None:    
            raise ValueError("Model variables (model_vars) must be set in the builder when using OR-Tools CPSAT.")

        self.solve()
        self.solution = self.construct_solution()

        return self.solution

    @abstractmethod
    def build(self):
        """
        MUST call: self._set_model(...)
        """
        ...

    @abstractmethod
    def construct_solution(self) -> Optional[SolutionBaseModel]:
        pass

    def solve(self):
        if self.solver_engine == SolverEngine.PYSCIPOPT:
            self.solve_pyscipopt()

        elif self.solver_engine == SolverEngine.GUROBI:
            self.solve_gurobi()

        elif self.solver_engine == SolverEngine.ORTOOLS_SCIP:
            self.solve_ortools_scip()

        elif self.solver_engine == SolverEngine.ORTOOLS_ROUTING:
            self.solve_ortools_routing()
        
        elif self.solver_engine == SolverEngine.ORTOOLS_CPSAT:
            self.solve_ortools_cpsat()

        else:
            raise ValueError(f"Solver engine {self.solver_engine} not supported")
    
    def solve_pyscipopt(self):
        start_sol = None
        
        self.model.setParam("display/verblevel", SOLVER_CONFIG.MODEL_SOLVER_VERBOSE)

        self.model.setIntParam("parallel/maxnthreads", SOLVER_CONFIG.LIMIT_MULTI_THREAD)
        self.model.setIntParam("parallel/minnthreads", SOLVER_CONFIG.LIMIT_MULTI_THREAD)

        if SOLVER_CONFIG.APPLY_HEURISTICS:
            # Phase 1: Heuristics only
            self.model.setHeuristics(SCIP_PARAMSETTING.AGGRESSIVE)

            self.model.setParam("limits/time", SOLVER_CONFIG.LIMIT_TIME_MINUTES_HEURISTICS*60)
            self.model.setParam("limits/gap", SOLVER_CONFIG.LIMIT_OPTIMALITY_GAP_HEURISTICS)
            self.model.setParam("limits/nodes", 500)   # limit nodes so B&B doesn't go far
            self.model.setParam("presolving/maxrounds", 0)  # skip heavy presolve if desired
            self.model.setParam("limits/memory", SOLVER_CONFIG.LIMIT_MEMORY_MB)

            self.model.optimize()

            try:
                sol = self.model.getBestSol()
                start_sol = {v.name: self.model.getSolVal(sol, v) for v in self.model.getVars()}

            except:
                pass

        # Phase 2: Exact MILP solving
        self.model.resetParams()
        self.model.setHeuristics(SCIP_PARAMSETTING.DEFAULT)

        self.model.setParam("limits/time", SOLVER_CONFIG.LIMIT_TIME_MINUTES_DETERMINISTIC*60)
        self.model.setParam("limits/gap", SOLVER_CONFIG.LIMIT_OPTIMALITY_GAP_DETERMINISTIC)
        self.model.setParam("limits/memory", SOLVER_CONFIG.LIMIT_MEMORY_MB)

        try:
            if start_sol is not None:
                # Feed initial solution
                sol_obj = self.model.createSol()
                for var in self.model.getVars():
                    if var.name in start_sol:
                        self.model.setSolVal(sol_obj, var, start_sol[var.name])
                self.model.addSol(sol_obj, free=True)

        except:
            pass

        self.model.optimize()
    
        self.solver_status = SolverStatus.from_pyscipopt_status(self.model.getStatus())
        print("STATUS", self.model.getStatus(), self.solver_status, "\n\n")

        if SolverStatus.is_solution_found(self.solver_status):
            self.construct_solution()

    def solve_gurobi(self):
        self.model.setParam('OutputFlag', SOLVER_CONFIG.MODEL_SOLVER_VERBOSE)

        start_sol = None
        if SOLVER_CONFIG.APPLY_HEURISTICS:
            # Phase 1: Heuristics only
            self.model.setParam('TimeLimit', SOLVER_CONFIG.LIMIT_TIME_MINUTES_HEURISTICS * 60)
            self.model.setParam('MIPGap', SOLVER_CONFIG.LIMIT_OPTIMALITY_GAP_HEURISTICS)
            self.model.setParam('NodeLimit', 500)  # limit nodes so B&B doesn't go far
            self.model.setParam('Presolve', 0)  # skip heavy presolve if desired
            self.model.setParam('Threads', SOLVER_CONFIG.LIMIT_MULTI_THREAD)

            # Set heuristic focus
            self.model.setParam('Heuristics', 0.8)  # Aggressive heuristics
            
            self.model.optimize()

            try:
                status = SolverStatus.from_gurobi_status(self.model.status)
                if SolverStatus.is_solution_found(status):
                    start_sol = {}
                    for var in self.model.getVars():
                        start_sol[var.varName] = var.x
            except:
                pass

        # Phase 2: Exact MILP solving
        # Reset parameters for exact solving
        self.model.setParam('TimeLimit', SOLVER_CONFIG.LIMIT_TIME_MINUTES_DETERMINISTIC * 60)
        self.model.setParam('MIPGap', SOLVER_CONFIG.LIMIT_OPTIMALITY_GAP_DETERMINISTIC)
        self.model.setParam('NodeLimit', 1000000)
        self.model.setParam('Presolve', -1)  # Default presolve
        self.model.setParam('Heuristics', 0.05)  # Default heuristics
        self.model.setParam('Threads', SOLVER_CONFIG.LIMIT_MULTI_THREAD)

        try:
            if start_sol is not None:
                # Feed initial solution
                for var in self.model.getVars():
                    if var.varName in start_sol:
                        var.start = start_sol[var.varName]
        except:
            pass

        self.model.optimize()

        self.solver_status = SolverStatus.from_gurobi_status(self.model.status)
        print("STATUS", self.model.status, self.solver_status, "\n\n")

        if SolverStatus.is_solution_found(self.solver_status):
            self.construct_solution()

    def solve_ortools_routing(self):
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )

        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )

        search_parameters.solution_limit = 100
        search_parameters.time_limit.seconds = int(SOLVER_CONFIG.LIMIT_TIME_MINUTES_DETERMINISTIC * 60)
        
        self.solution = self.model.SolveWithParameters(search_parameters)
    
        self.solver_status = SolverStatus.from_ortools_routing_status(self.model.status())
        print("STATUS", self.solver_status)

        if SolverStatus.is_solution_found(self.solver_status):
            self.construct_solution()

    def solve_ortools_cpsat(self):
        if self.model_vars is None:
            print(f"\033[91m\n>>> ERROR while Solving Model : Vars is not setup while building model\n\033[0m")
            self.solver_status = SolverStatus.ERROR
        
        else:
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = SOLVER_CONFIG.LIMIT_TIME_MINUTES_DETERMINISTIC * 60
            solver.parameters.num_search_workers = SOLVER_CONFIG.LIMIT_MULTI_THREAD

            solver.parameters.log_search_progress = SOLVER_CONFIG.MODEL_SOLVER_VERBOSE

            result_status = solver.Solve(self.model)
            self.model_output = solver

            self.solver_status = SolverStatus.from_ortools_cpsat_status(result_status)
            print("STATUS", result_status, self.solver_status)

            if SolverStatus.is_solution_found(self.solver_status):
                self.construct_solution()

    def solve_ortools_scip(self):
        self.model.SetTimeLimit(int(SOLVER_CONFIG.LIMIT_TIME_MINUTES_DETERMINISTIC * 60 * 1000))
        self.model.SetNumThreads(int(SOLVER_CONFIG.LIMIT_MULTI_THREAD))

        params_str = (
            f"limits/gap={SOLVER_CONFIG.LIMIT_OPTIMALITY_GAP_DETERMINISTIC}\n"
            f"limits/memory={SOLVER_CONFIG.LIMIT_MEMORY_MB}\n"
            f"parallel/maxnthreads={int(SOLVER_CONFIG.LIMIT_MULTI_THREAD)}\n"
            f"lp/threads={int(SOLVER_CONFIG.LIMIT_MULTI_THREAD)}\n"
            f"display/verblevel=5\n"
        )

        self.model.SetSolverSpecificParametersAsString(params_str)

        status = self.model.Solve()
        self.solver_status = SolverStatus.from_ortools_scip_status(status)
        print("STATUS", status, self.solver_status, "\n\n")

        if SolverStatus.is_solution_found(self.solver_status):
            self.construct_solution()


class OptimizationModel(Generic[ParamsBaseModel, SolutionBaseModel], ABC, metaclass=ModelMeta):
    id: str
    name: str
    builders_registry: Dict[SolverEngine, Type[ModelBuilder[ParamsBaseModel, SolutionBaseModel]]]
    builder: ModelBuilder[ParamsBaseModel, SolutionBaseModel]

    def __init__(self, params: ParamsBaseModel, solver_engine: Optional[SolverEngine] = None):
        self.id = str(uuid.uuid4())

        if solver_engine is None or solver_engine not in self.builders_registry.keys():
            solver_engine = next(iter(self.builders_registry.keys()))

        self.builder = self.builders_registry[solver_engine](
            params=params,
            solver_engine=solver_engine
        )

    @final
    def execute(self) -> Optional[SolutionBaseModel]:
        start_time = time.time()
        solution = None

        try :
            solution = self.builder.execute()
            self.builder.runtime_message = "Success"

        except Exception as e:
            print(f"\033[91m\n>>> ERROR while Solving Model : {e}\n\033[0m")
            self.builder.runtime_message = f"Error : {str(e)}"

        finally:
            end_time = time.time()
            self.builder.runtime_seconds = end_time - start_time
        
        return solution

    def is_solution_found(self) -> bool:
        return SolverStatus.is_solution_found(self.builder.solver_status)

    def get_solution(self) -> Optional[SolutionBaseModel]:
        return self.builder.solution