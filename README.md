# Stitchlab Optimization Framework

A standardized framework for building optimization models with multi-solver support. This framework allows you to define optimization models once and easily switch between different solvers without rewriting your model logic.

## Overview

The framework is built around two core concepts:

- **Workflow**: Orchestrates one or more optimization models to solve complex problems
- **Model**: Defines the optimization problem with multiple solver implementations (builders)

## Key Features

- **Solver Agnostic**: Write your model once, run it with different solvers (OR-Tools CP-SAT, OR-Tools SCIP, PySCIPOpt, etc.)
- **Type Safety**: Built with Pydantic for robust data validation
- **Logging**: SQLite-based logging for tracking optimization runs
- **Modular Design**: Separate concerns between model definition, solving, and workflow orchestration

## Quick Start

### 1. Define Your Model Parameters and Solution

```python
from pydantic import BaseModel
from src.stitchlab_optimization.builder.model import ModelParams

class SimpleParams(ModelParams):
    pass

class SimpleSolution(BaseModel):
    x: int
    y: int
    objective: float
```

### 2. Create Builders for Different Solvers

```python
from src.stitchlab_optimization.builder.model import ModelBuilder

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
```

### 3. Register Builders in Your Model

```python
from src.stitchlab_optimization.builder.model import OptimizationModel
from src.stitchlab_optimization.solver.engine import SolverEngine

class SimpleModel(OptimizationModel[SimpleParams, SimpleSolution]):
    builders_registry = {
        SolverEngine.ORTOOLS_CPSAT: SimpleCPSATBuilder,
        SolverEngine.ORTOOLS_SCIP: SimpleSCIPBuilder,
        SolverEngine.PYSCIPOPT: SimplePySCIPOPTBuilder
    }
```

### 4. Create a Workflow

```python
from src.stitchlab_optimization.builder.workflow import OptimizationWorkflow

class InputData(BaseModel):
    id: str

class OutputData(SimpleSolution):
    pass

class SimpleWorkflow(OptimizationWorkflow[InputData, OutputData]):
    models_registry = {
        "simple_model": SimpleModel
    }
    
    def execute(self):
        return self.execute_model(
            "simple_model", 
            SimpleParams(), 
            SolverEngine.ORTOOLS_CPSAT
        )
```

### 5. Run Your Workflow

```python
from src.stitchlab_optimization.logger.sqlite_logger import SQLiteLogManager

logger = SQLiteLogManager(db_path="test.db")

payload = InputData(id="1")
workflow = SimpleWorkflow(payload=payload, logger=logger)
output = workflow.invoke()
print(output)
```

## Architecture

```
Workflow
  ├── Model 1
  │   ├── Builder (Solver A)
  │   ├── Builder (Solver B)
  │   └── Builder (Solver C)
  └── Model 2
      ├── Builder (Solver A)
      └── Builder (Solver B)
```

## Benefits

1. **Easy Solver Switching**: Change solvers by modifying a single parameter
2. **Reusability**: Define model logic once, use with multiple solvers
3. **Maintainability**: Clear separation between model definition and solver implementation
4. **Extensibility**: Add new solvers by implementing new builders
5. **Testability**: Test different solvers against the same model to compare performance

## Supported Solvers

- OR-Tools CP-SAT
- OR-Tools SCIP
- PySCIPOpt
- GUROBI