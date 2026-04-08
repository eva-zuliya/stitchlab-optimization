from abc import abstractmethod, ABC
from pydantic import BaseModel
from typing import Optional
import json

from src.stitchlab_optimization.solver.engine import SolverEngine
from src.stitchlab_optimization.solver.status import SolverStatus


class ModelLog(BaseModel):
    solver_engine: SolverEngine
    model_id: str
    model_name: str
    status: SolverStatus
    problem_size_vars: Optional[int]
    problem_size_cons: Optional[int]
    optimality_gap: Optional[float]
    objective_value: Optional[float]
    message: Optional[str]
    runtime_sec: float
    created_timestamp: str

    def to_sql_log(self) -> dict:
        return {
            "id": None,
            "solver_engine": self.solver_engine.value,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "problem_size_vars": self.problem_size_vars,
            "problem_size_cons": self.problem_size_cons,
            "optimality_gap": self.optimality_gap,
            "objective_value": self.objective_value,
            "status": self.status.value,
            "message": self.message,
            "runtime_sec": self.runtime_sec,
            "created_timestamp": self.created_timestamp
        }


class WorkflowLog(BaseModel):
    workflow_id: str
    workflow_name: str
    model_ids_execution: dict
    payload: dict
    solver_parameter: dict
    message: Optional[str]
    start_timestamp: str
    end_timestamp: str
    runtime_sec: float
    created_timestamp: str

    def to_sql_log(self) -> dict:
        model_ids = json.dumps(self.model_ids_execution)
        payload = json.dumps(self.payload)
        solver_parameter = json.dumps(self.solver_parameter)

        return {
            "id": None,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "model_ids": model_ids,
            "payload": payload,
            "solver_parameter": solver_parameter,
            "message": self.message,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "runtime_sec": self.runtime_sec,
            "created_timestamp": self.created_timestamp
        }


class LogManager(ABC):
    is_monitor_optimality: bool = True
    is_monitor_runtime: bool = True
    is_monitor_resource: bool = False

    _dir_model_execution_log: str = "log_execution_model"
    _dir_workflow_execution_log: str = "log_execution_workflow"
    _dir_resource_occupation_log: str = "log_resource_occupation"

    def __init__(self):
        pass

    @abstractmethod
    def put_model_log(self, model_log: ModelLog):
        pass

    @abstractmethod
    def put_workflow_log(self, workflow_log: WorkflowLog):
        pass

    @abstractmethod
    def put_resource_log(self, resource_log: dict):
        pass