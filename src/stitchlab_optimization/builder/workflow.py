from abc import ABC, ABCMeta, abstractmethod
from typing import Dict, Type, Generic, TypeVar, final, Any, Optional, Union
import uuid
from pydantic import BaseModel
from datetime import datetime, timezone
import time

from src.stitchlab_optimization.logger.manager import LogManager, WorkflowLog
from src.stitchlab_optimization.builder.model import OptimizationModel
from src.stitchlab_optimization.solver.engine import SolverEngine
from src.stitchlab_optimization.solver.config import SolverConfig


InputBaseModel = TypeVar("InputBaseModel", bound=BaseModel)
OutputBaseModel = TypeVar("OutputBaseModel", bound=BaseModel)

class WorkflowMeta(ABCMeta):
    def __new__(mcls, name, bases, attrs):
        # Skip base class
        if ABC in bases:
            return super().__new__(mcls, name, bases, attrs)
        
        if "name" not in attrs:
            attrs["name"] = name
    
        # Enforce that each subclass defines `models_registry`
        if "models_registry" not in attrs:
            raise TypeError(f"{name} must define class-level attribute `models_registry`.")

        # Enforce correct type
        if not isinstance(attrs["models_registry"], dict):
            raise TypeError(f"{name}.models_registry must be a dict[str, Type[OptimizationModel].")

        return super().__new__(mcls, name, bases, attrs)


class OptimizationWorkflow(Generic[InputBaseModel, OutputBaseModel], ABC, metaclass=WorkflowMeta):
    _input_basemodel: Type[InputBaseModel]
    _output_basemodel: Type[OutputBaseModel]
    _logger: Optional[LogManager] = None

    id: str
    name: str
    models_registry: Dict[str, Type[OptimizationModel]] # {model_name : OptimizationModel}
    payload: InputBaseModel

    runtime_message: str = ""
    runtime_seconds: float = 0
    start_timestamp: str = ""
    end_timestamp: str = ""

    model_ids_execution: dict[str, str] = {}  # {model_id: model_name}

    
    @final
    def __init__(self, payload: Union[Dict, InputBaseModel], logger: Optional[LogManager] = None):
        self.id = str(uuid.uuid4())
        self._logger = logger

        if isinstance(payload, dict):
            payload = self._input_basemodel(**payload)

        self.payload = payload
        
    @final
    def invoke(self) -> Optional[dict]:
        self.start_timestamp = datetime.now(timezone.utc).isoformat()
        start_time = time.time()

        try:
            result = self.execute()
            self.runtime_message = "success"

        except Exception as e:
            self.runtime_message = str(e)

        finally:
            self.runtime_seconds = time.time() - start_time
            self.end_timestamp = datetime.now(timezone.utc).isoformat()

            if self._logger is not None and self._logger.is_monitor_runtime:
                self._logger.put_workflow_log(workflow_log=self._workflow_log)

        if self.runtime_message == "success":
            return result.model_dump()
        
        return None

    @abstractmethod
    def execute(self) -> OutputBaseModel:
        pass

    @final
    def execute_model(self, model_name: str, params: Any, solver_engine: Optional[SolverEngine] = None) -> Any:
        if model_name not in self.models_registry:
            raise ValueError(f"Model '{model_name}' not found in models_registry.")
        
        model_cls = self.models_registry[model_name]
        model_instance = model_cls(
            params=params,
            solver_engine=solver_engine
        )

        output = model_instance.execute(logger=self._logger)
        self.model_ids_execution[model_instance.id] = model_name

        return output

    @property
    def _workflow_log(self) -> WorkflowLog:
        return WorkflowLog(
            request_id=self.id,
            model_ids_execution=self.model_ids_execution,
            payload=self.payload.model_dump(),
            solver_parameter=SolverConfig().SOLVER_PARAMETER,
            message=self.runtime_message,
            start_timestamp=self.start_timestamp,
            end_timestamp=self.end_timestamp,
            runtime_sec=self.runtime_seconds,
            created_timestamp=datetime.now(timezone.utc).isoformat()
        )