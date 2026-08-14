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

from ..solver.engine import SolverEngine
from ..solver.status import SolverStatus
from ..solver.params import SolverParams
from ..logger.manager import ModelLog, LogManager, ResourceMonitor, NullResourceMonitor


ParamsBaseModel = TypeVar("ParamsBaseModel", bound="ModelParams")
SolutionBaseModel = TypeVar("SolutionBaseModel", bound=BaseModel)

class ModelParams(BaseModel, ABC):
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


class ModelMeta(ABCMeta):
    def __new__(mcls, name, bases, attrs):
        # Skip base class
        if ABC in bases:
            return super().__new__(mcls, name, bases, attrs)

        # Enforce that each subclass defines `builders`
        if "builders_registry" not in attrs:
            raise TypeError(f"{name} must define class-level attribute `builders_registry`.")

        # Enforce correct type
        if not isinstance(attrs["builders_registry"], dict):
            raise TypeError(f"{name}.builders_registry must be a dict[SolverEngine, Type[ModelBuilder].")

        # Set name if not provided
        if "name" not in attrs:
            attrs["name"] = name

        return super().__new__(mcls, name, bases, attrs)


class ModelBuilder(Generic[ParamsBaseModel, SolutionBaseModel], ABC):
    params: ParamsBaseModel
    solution: Optional[SolutionBaseModel] = None
    solver_engine: SolverEngine
    solver_status: SolverStatus
    solver_params: SolverParams
    model: Any = None
    model_output: Any = None
    model_vars: Optional[Dict[str, Any]] = None
    runtime_message: str = ""
    runtime_seconds: float = 0
    
    @final
    def __init__(self, params: ParamsBaseModel, solver_engine: SolverEngine, solver_params: SolverParams):
        self.params = params
        self.solver_engine = solver_engine
        self.solver_status = SolverStatus.UNSOLVED
        self.solver_params = solver_params

    @final
    def _set_model(self, model: Any):
        self.model = model

    @final
    def _set_model_vars(self, model_vars: Dict[str, Any]):
        self.model_vars = model_vars

    @final
    def execute(self) -> Optional[SolutionBaseModel]:
        self.build()

        if self.model is None:
            raise ValueError("Model must be built before execution.")
        
        if self.model_vars is None:    
            raise ValueError("Model variables (model_vars) must be set in the builder before execution.")

        self.solve()
        
        if SolverStatus.is_solution_found(self.solver_status):
            return self.construct_solution()

        return None

    @abstractmethod
    def build(self):
        """
        MUST call:
            self._set_model(...)
            self._set_model_vars(...)
        """
        ...

    @abstractmethod
    def construct_solution(self) -> Optional[SolutionBaseModel]:
        pass

    def solve(self):
        if self.model is None:
            print(f"\033[91m\n>>> ERROR while Solving Model : Vars is not setup while building model\n\033[0m")
            self.solver_status = SolverStatus.ERROR

            raise ValueError(f"ERROR while Solving Model : Model is not saved while building model using solver engine {self.solver_engine}")

        if self.model_vars is None:
            print(f"\033[91m\n>>> ERROR while Solving Model : Vars is not setup while building model\n\033[0m")
            self.solver_status = SolverStatus.ERROR

            raise ValueError(f"ERROR while Solving Model : Vars is not saved while building model using solver engine {self.solver_engine}")

        SOLVER = {
            SolverEngine.PYSCIPOPT: self.solve_pyscipopt,
            SolverEngine.GUROBI: self.solve_gurobi,
            SolverEngine.ORTOOLS_SCIP: self.solve_ortools_scip,
            SolverEngine.ORTOOLS_ROUTING: self.solve_ortools_routing,
            SolverEngine.ORTOOLS_CPSAT: self.solve_ortools_cpsat,
        }

        # with ResourceMonitor() as monitor:
        try:
            SOLVER[self.solver_engine]()
        except KeyError:
            raise ValueError(f"Solver engine {self.solver_engine} not supported")
    
    def solve_pyscipopt(self):
        PARAMS = self.solver_params
        start_sol = None
        
        self.model.setParam("display/verblevel", PARAMS.MODEL_SOLVER_VERBOSE)

        self.model.setIntParam("parallel/maxnthreads", PARAMS.LIMIT_MULTI_THREAD)
        self.model.setIntParam("parallel/minnthreads", PARAMS.LIMIT_MULTI_THREAD)

        if PARAMS.APPLY_HEURISTICS:
            # Phase 1: Heuristics only
            self.model.setHeuristics(SCIP_PARAMSETTING.AGGRESSIVE)

            self.model.setParam("limits/time", PARAMS.LIMIT_TIME_MINUTES_HEURISTICS*60)
            self.model.setParam("limits/gap", PARAMS.LIMIT_OPTIMALITY_GAP_HEURISTICS)
            self.model.setParam("limits/nodes", 500)   # limit nodes so B&B doesn't go far
            self.model.setParam("presolving/maxrounds", 0)  # skip heavy presolve if desired
            self.model.setParam("limits/memory", PARAMS.LIMIT_MEMORY_MB)

            self.model.optimize()

            try:
                sol = self.model.getBestSol()
                start_sol = {v.name: self.model.getSolVal(sol, v) for v in self.model.getVars()}

            except:
                pass

        # Phase 2: Exact MILP solving
        self.model.resetParams()
        self.model.setHeuristics(SCIP_PARAMSETTING.DEFAULT)

        self.model.setParam("limits/time", PARAMS.LIMIT_TIME_MINUTES_DETERMINISTIC*60)
        self.model.setParam("limits/gap", PARAMS.LIMIT_OPTIMALITY_GAP_DETERMINISTIC)
        self.model.setParam("limits/memory", PARAMS.LIMIT_MEMORY_MB)

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
            
    def solve_gurobi(self):
        PARAMS = self.solver_params

        self.model.setParam('OutputFlag', PARAMS.MODEL_SOLVER_VERBOSE)

        start_sol = None
        if PARAMS.APPLY_HEURISTICS:
            # Phase 1: Heuristics only
            self.model.setParam('TimeLimit', PARAMS.LIMIT_TIME_MINUTES_HEURISTICS * 60)
            self.model.setParam('MIPGap', PARAMS.LIMIT_OPTIMALITY_GAP_HEURISTICS)
            self.model.setParam('NodeLimit', 500)  # limit nodes so B&B doesn't go far
            self.model.setParam('Presolve', 0)  # skip heavy presolve if desired
            self.model.setParam('Threads', PARAMS.LIMIT_MULTI_THREAD)

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
        self.model.setParam('TimeLimit', PARAMS.LIMIT_TIME_MINUTES_DETERMINISTIC * 60)
        self.model.setParam('MIPGap', PARAMS.LIMIT_OPTIMALITY_GAP_DETERMINISTIC)
        self.model.setParam('NodeLimit', 1000000)
        self.model.setParam('Presolve', -1)  # Default presolve
        self.model.setParam('Heuristics', 0.05)  # Default heuristics
        self.model.setParam('Threads', PARAMS.LIMIT_MULTI_THREAD)

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

    def solve_ortools_routing(self):
        PARAMS = self.solver_params

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )

        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )

        search_parameters.solution_limit = 100
        search_parameters.time_limit.seconds = int(PARAMS.LIMIT_TIME_MINUTES_DETERMINISTIC * 60)
        
        self.solution = self.model.SolveWithParameters(search_parameters)
    
        self.solver_status = SolverStatus.from_ortools_routing_status(self.model.status())
        print("STATUS", self.solver_status)

    def solve_ortools_cpsat(self):
        PARAMS = self.solver_params

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = PARAMS.LIMIT_TIME_MINUTES_DETERMINISTIC * 60
        solver.parameters.num_search_workers = PARAMS.LIMIT_MULTI_THREAD
        solver.parameters.relative_gap_limit = PARAMS.LIMIT_OPTIMALITY_GAP_DETERMINISTIC

        solver.parameters.log_search_progress = PARAMS.MODEL_SOLVER_VERBOSE

        result_status = solver.Solve(self.model)
        self.model_output = solver

        self.solver_status = SolverStatus.from_ortools_cpsat_status(result_status)
        print("STATUS", result_status, self.solver_status)

    def solve_ortools_scip(self):
        PARAMS = self.solver_params

        self.model.SetTimeLimit(int(PARAMS.LIMIT_TIME_MINUTES_DETERMINISTIC * 60 * 1000))
        self.model.SetNumThreads(int(PARAMS.LIMIT_MULTI_THREAD))

        params_str = (
            f"limits/gap={PARAMS.LIMIT_OPTIMALITY_GAP_DETERMINISTIC}\n"
            f"limits/memory={PARAMS.LIMIT_MEMORY_MB}\n"
            f"parallel/maxnthreads={int(PARAMS.LIMIT_MULTI_THREAD)}\n"
            f"lp/threads={int(PARAMS.LIMIT_MULTI_THREAD)}\n"
        )

        if PARAMS.MODEL_SOLVER_VERBOSE:
            self.model.EnableOutput()
            params_str += "display/verblevel=5\n"

        self.model.SetSolverSpecificParametersAsString(params_str)

        status = self.model.Solve()
        self.solver_status = SolverStatus.from_ortools_scip_status(status)
        print("STATUS", status, self.solver_status, "\n\n")


class OptimizationModel(Generic[ParamsBaseModel, SolutionBaseModel], ABC, metaclass=ModelMeta):
    id: str
    name: str
    builders_registry: Dict[SolverEngine, Type[ModelBuilder[ParamsBaseModel, SolutionBaseModel]]]
    builder: ModelBuilder[ParamsBaseModel, SolutionBaseModel]

    def __init__(self, params: ParamsBaseModel, solver_engine: Optional[SolverEngine] = None, solver_params: Optional[SolverParams] = None):
        self.id = str(uuid.uuid4())

        if solver_engine is None or solver_engine not in self.builders_registry.keys():
            solver_engine = next(iter(self.builders_registry.keys()))

        if solver_params is None:
            solver_params = SolverParams()

        self.builder = self.builders_registry[solver_engine](
            params=params,
            solver_engine=solver_engine,
            solver_params=solver_params
        )

    @final
    def execute(self, logger: Optional[LogManager] = None) -> Optional[SolutionBaseModel]:
        start_time = time.time()
        solution = None

        monitor = (
            ResourceMonitor(
                interval_seconds=logger.monitor_resource_interval_seconds
            )
            if logger and logger.enable_monitor_resource
            else NullResourceMonitor()
        )

        try :
            with monitor:
                solution = self.builder.execute()
                self.builder.runtime_message = "success"

        except Exception as e:
            print(f"\033[91m\n>>> ERROR while Solving Model : {e}\n\033[0m")
            self.builder.runtime_message = f"Error : {str(e)}"

        finally:
            end_time = time.time()
            self.builder.runtime_seconds = end_time - start_time

            if logger is not None and logger.enable_monitor_optimality:
                log = self._model_log
                log.resource_stats = monitor.stats

                logger.put_model_log(model_log=log)
        
        return solution

    def is_solution_found(self) -> bool:
        return SolverStatus.is_solution_found(self.builder.solver_status)

    def get_solution(self) -> Optional[SolutionBaseModel]:
        return self.builder.solution

    @property
    def _model_log(self) -> ModelLog:
        builder = self.builder
        solver_engine = self.builder.solver_engine
        solver_params = self.builder.solver_params

        if solver_engine == SolverEngine.GUROBI:
            # Gurobi Python API
            problem_size_vars = builder.model.NumVars
            problem_size_cons = builder.model.NumConstrs

            if builder.model.NumObj <= 1:
                optimality_gap = builder.model.MIPGap
                objective_value = builder.model.ObjVal

            else:
                objective_value = builder.model.getAttr("ObjNVal")
                optimality_gap   = builder.model.getAttr("ObjNRelTol")

        elif solver_engine == SolverEngine.ORTOOLS_SCIP:
            # OR-Tools CP-SAT solver (pywraplp.Solver)
            problem_size_vars = builder.model.NumVariables()
            problem_size_cons = builder.model.NumConstraints()

            try:
                optimality_gap = builder.model.MipGap()
            except AttributeError:
                optimality_gap = None
                
            objective_value = builder.model.Objective().Value()
            
        elif solver_engine == SolverEngine.ORTOOLS_ROUTING:
            # OR-Tools RoutingModel
            count_nodes = builder.model.Size()
            count_vehicles = builder.model.vehicles()
            problem_size_vars = count_nodes * count_nodes * count_vehicles

            # RoutingModel does not expose number of constraints directly
            problem_size_cons = None
            objective_value = builder.solution.ObjectiveValue()
            optimality_gap = None
        
        elif solver_engine == SolverEngine.ORTOOLS_CPSAT:
            problem_size_vars = len(builder.model.Proto().variables)
            problem_size_cons = len(builder.model.Proto().constraints)

            # Objective value (only available if model solved)
            try:
                objective_value = builder.model_output.ObjectiveValue()
                best_bound = builder.model_output.BestObjectiveBound()
                optimality_gap = abs(objective_value - best_bound) / max(1.0, abs(objective_value))

            except Exception:
                objective_value = None
                optimality_gap = None

        elif solver_engine == SolverEngine.PYSCIPOPT:
            problem_size_vars = builder.model.getNVars()
            problem_size_cons = builder.model.getNConss()
            optimality_gap = builder.model.getGap()

            try:
                objective_value = builder.model.getObjVal()
            except Exception:
                objective_value = None

        elif solver_engine == SolverEngine.SKLEARN:
            # scikit-learn is not an optimization solver, so these are not applicable
            problem_size_vars = None
            problem_size_cons = None
            optimality_gap = None
            objective_value = None

        else:
            raise ValueError(f"Solver engine {solver_engine} not supported")

        return ModelLog(
            solver_engine=solver_engine,
            solver_params=solver_params,
            model_id=self.id,
            model_name=self.name,
            status=builder.solver_status,
            problem_size_vars=problem_size_vars,
            problem_size_cons=problem_size_cons,
            optimality_gap=optimality_gap,
            objective_value=objective_value,
            message=builder.runtime_message,
            runtime_sec=builder.runtime_seconds,
            created_timestamp=datetime.now(timezone.utc).isoformat()
        )