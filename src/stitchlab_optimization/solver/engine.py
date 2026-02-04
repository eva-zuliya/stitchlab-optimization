from enum import Enum


class SolverEngine(str, Enum):
    ORTOOLS_ROUTING = "or-tools-routing"
    ORTOOLS_CPSAT = "or-tools-cpsat"
    ORTOOLS_SCIP = "or-tools-scip"
    CPLEX = "cplex"
    GUROBI = "gurobi"
    PYSCIPOPT = "pyscipopt"
    SKLEARN = "sklearn"
