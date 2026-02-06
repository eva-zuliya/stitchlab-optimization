class ModelLog(BaseModel):
    solver_engine: SolverEngine
    model_id: str
    exec_id: str
    model_name: str
    status: SolverStatus
    problem_size_vars: Optional[int]
    problem_size_cons: Optional[int]
    optimality_gap: Optional[float]
    objective_value: Optional[float]
    message: Optional[str]
    runtime_sec: float
    created_at: str

    @classmethod
    def from_model(cls, model: OptimizationModel, solver_engine: SolverEngine):

        builder = model.builders[solver_engine]

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
                objective_value = builder.solution.ObjectiveValue()
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
            model_id=model.id,
            exec_id=builder.id,
            model_name=model.name,
            status=builder.solver_status,
            problem_size_vars=problem_size_vars,
            problem_size_cons=problem_size_cons,
            optimality_gap=optimality_gap,
            objective_value=objective_value,
            message=builder.runtime_message,
            runtime_sec=builder.runtime_seconds,
            created_at=datetime.now(timezone.utc).isoformat()
        )

    def write_to_db(self):
        log = {
            "id": None,
            "solver_engine": self.solver_engine.value,
            "model_id": self.model_id,
            "exec_id": self.exec_id,
            "model_name": self.model_name,
            "problem_size_vars": self.problem_size_vars,
            "problem_size_cons": self.problem_size_cons,
            "optimality_gap": self.optimality_gap,
            "objective_value": self.objective_value,
            "status": self.status.value,
            "message": self.message,
            "runtime_sec": self.runtime_sec,
            "created_at": self.created_at
        }

        insert_to_sqlite(table_name="execution_log", data=log)
