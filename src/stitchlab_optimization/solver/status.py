from enum import Enum
from pyscipopt import SCIP_RESULT
from ortools.linear_solver import pywraplp
from ortools.constraint_solver import routing_enums_pb2
from ortools.sat.python import cp_model
import gurobipy as gp


class SolverStatus(str, Enum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    LIMIT = "limit"
    ERROR = "error"
    UNSOLVED = "unsolved"
    SOLVED_INFEASIBLE = "solved_infeasible"

    @classmethod
    def from_pyscipopt_status(cls, status: SCIP_RESULT) -> "SolverStatus":
        if status == "optimal":
            return cls.OPTIMAL
        elif status == "infeasible":
            return cls.INFEASIBLE
        elif status == "unbounded":
            return cls.UNBOUNDED
        elif status in ["timelimit", "nodelimit", "totalnodelimit", "stallnodelimit", "gaplimit", "memlimit"]:
            return cls.LIMIT

        return cls.ERROR
    
    @classmethod
    def from_ortools_scip_status(cls, status: int) -> "SolverStatus":
        if status == pywraplp.Solver.OPTIMAL:
            return cls.OPTIMAL
        elif status == pywraplp.Solver.FEASIBLE:
            return cls.FEASIBLE
        elif status == pywraplp.Solver.INFEASIBLE:
            return cls.INFEASIBLE
        elif status == pywraplp.Solver.UNBOUNDED:
            return cls.UNBOUNDED
        elif status in (pywraplp.Solver.ABNORMAL, pywraplp.Solver.NOT_SOLVED):
            return cls.ERROR
        
        return cls.LIMIT

    @classmethod
    def from_ortools_cpsat_status(cls, status: int) -> "SolverStatus":
        if status == cp_model.OPTIMAL:
            return cls.OPTIMAL
        elif status == cp_model.FEASIBLE:
            return cls.FEASIBLE
        elif status == cp_model.INFEASIBLE:
            return cls.INFEASIBLE
        elif status == cp_model.MODEL_INVALID:
            return cls.ERROR
        elif status == cp_model.UNKNOWN:
            return cls.UNSOLVED  # No solution found
        else:
            return cls.ERROR

    @classmethod
    def from_ortools_routing_status(cls, status: int) -> "SolverStatus":
        if status == routing_enums_pb2.RoutingStatus.ROUTING_SUCCESS:
            return cls.FEASIBLE

        elif status == routing_enums_pb2.RoutingStatus.ROUTING_INFEASIBLE:
            return cls.INFEASIBLE

        elif status == routing_enums_pb2.RoutingStatus.ROUTING_INVALID:
            return cls.ERROR

        elif status == routing_enums_pb2.RoutingStatus.ROUTING_FAIL:
            return cls.UNSOLVED

        elif status == routing_enums_pb2.RoutingStatus.ROUTING_FAIL_TIMEOUT:
            return cls.LIMIT

        return cls.ERROR

    @classmethod
    def from_gurobi_status(cls, status: int) -> "SolverStatus":
        if status == gp.GRB.OPTIMAL:
            return cls.OPTIMAL
        elif status == gp.GRB.SUBOPTIMAL:
            return cls.FEASIBLE
        elif hasattr(gp.GRB, "FEASIBLE") and status == gp.GRB.FEASIBLE:
            # Only present in continuous models
            return cls.FEASIBLE
        elif status == gp.GRB.INFEASIBLE:
            return cls.INFEASIBLE
        elif status == gp.GRB.UNBOUNDED:
            return cls.UNBOUNDED
        elif status == gp.GRB.INF_OR_UNBD:
            return cls.INFEASIBLE
        elif status in (
            gp.GRB.TIME_LIMIT,
            gp.GRB.NODE_LIMIT,
            gp.GRB.SOLUTION_LIMIT,
            gp.GRB.INTERRUPTED,
            gp.GRB.ITERATION_LIMIT,
            gp.GRB.WORK_LIMIT,
            gp.GRB.MEM_LIMIT,
            gp.GRB.USER_OBJ_LIMIT,
        ):
            return cls.LIMIT
        
        return cls.ERROR

    @classmethod
    def is_solution_found(cls, status):
        """
        Check if a solution is found (either optimal or suboptimal).
        Accepts either a SolutionStatus instance or a string.
        """
        if isinstance(status, cls):
            status_value = status
        elif isinstance(status, str):
            try:
                status_value = cls(status)
            except ValueError:
                return False
        else:
            return False

        return status_value in {cls.OPTIMAL, cls.FEASIBLE, cls.LIMIT, cls.SOLVED_INFEASIBLE}
    

