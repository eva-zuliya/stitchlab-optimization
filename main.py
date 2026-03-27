from src.stitchlab_optimization.builder.model import OptimizationModel, ModelParams, ModelBuilder
from src.stitchlab_optimization.solver.engine import SolverEngine
from src.stitchlab_optimization.logger.sqlite_logger import SQLiteLogManager

from pydantic import BaseModel


class SimpleParams(ModelParams):
    pass


class SimpleSolution(BaseModel):
    x: int
    y: int
    objective: float


class SimpleCPSATBuilder(ModelBuilder[SimpleParams, SimpleSolution]):
    def build(self):
        from ortools.sat.python import cp_model
        model = cp_model.CpModel()

        self.model_vars = {}
        self.model_vars['x'] = model.NewIntVar(0, 5, 'x')
        self.model_vars['y'] = model.NewIntVar(0, 7, 'y')

        model.Add(self.model_vars['x'] + self.model_vars['y'] <= 10)
        model.Maximize(self.model_vars['x'] + self.model_vars['y'])

        self._set_model(model)

    def construct_solution(self):
        if self.model_output:
            return SimpleSolution(
                x=self.model_output.Value(self.model_vars['x']),
                y=self.model_output.Value(self.model_vars['y']),
                objective=self.model_output.ObjectiveValue()
            )
        
        return None
    

class SimplePySCIPOPTBuilder(ModelBuilder[SimpleParams, SimpleSolution]):
    def build(self):
        from pyscipopt import Model
        model = Model("simple")

        # Variables
        self.model_vars = {}
        self.model_vars['x'] = model.addVar(lb=0, ub=5, vtype="I", name="x")
        self.model_vars['y'] = model.addVar(lb=0, ub=7, vtype="I", name="y")

        # Constraint: x + y <= 10
        model.addCons(self.model_vars['x'] + self.model_vars['y'] <= 10)

        # Objective: maximize x + y
        model.setObjective(
            self.model_vars['x'] + self.model_vars['y'],
            sense="maximize"
        )

        self._set_model(model)

    def construct_solution(self):
        return SimpleSolution(
            x=self.model.getVal(self.model_vars['x']),
            y=self.model.getVal(self.model_vars['y']),
            objective=self.model.getObjVal(),
        )


class SimpleSCIPBuilder(ModelBuilder[SimpleParams, SimpleSolution]):
    def build(self):
        from ortools.linear_solver import pywraplp
        model = pywraplp.Solver.CreateSolver('SCIP')

        self.model_vars = {}
        self.model_vars['x'] = model.IntVar(0, 5, 'x')
        self.model_vars['y'] = model.IntVar(0, 7, 'y')

        model.Add(self.model_vars['x'] + self.model_vars['y'] <= 10)
        model.Maximize(self.model_vars['x'] + self.model_vars['y'])

        self._set_model(model)

    def construct_solution(self):
        return SimpleSolution(
            x=self.model.Value(self.model_vars['x']),
            y=self.model.Value(self.model_vars['y']),
            objective=self.model.Objective().Value()
        )


class SimpleModel(OptimizationModel[SimpleParams, SimpleSolution]):
    builders_registry = {
        SolverEngine.ORTOOLS_CPSAT: SimpleCPSATBuilder,
        SolverEngine.ORTOOLS_SCIP: SimpleSCIPBuilder,
        SolverEngine.PYSCIPOPT: SimplePySCIPOPTBuilder
    }


if __name__ == "__main__":

    logger = SQLiteLogManager(db_path="test.db")

    model = SimpleModel(
        params=SimpleParams(),
        solver_engine=SolverEngine.ORTOOLS_CPSAT
    )

    result = model.execute(logger=logger)
    print(result)
