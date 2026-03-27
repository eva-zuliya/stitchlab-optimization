from abc import ABC, ABCMeta, abstractmethod
from typing import Dict, Type, Generic, TypeVar, final, Any, Optional
import uuid
from pydantic import BaseModel
from datetime import datetime, timezone
import time

from src.stitchlab_optimization.logger.manager import LogManager, WorkflowLog
from src.stitchlab_optimization.builder.model import OptimizationModel
from src.stitchlab_optimization.solver.engine import SolverEngine


InputBaseModel = TypeVar("InputBaseModel", bound=BaseModel)
OutputBaseModel = TypeVar("OutputBaseModel", bound=BaseModel)

class WorkflowMeta(ABCMeta):
    def __new__(mcls, name, bases, attrs):
        cls = super().__new__(mcls, name, bases, attrs)

        if "name" not in attrs:
            attrs["name"] = name

        # Skip base class
        if ABC in bases:
            return cls
    
        # Enforce that each subclass defines `models_registry`
        if "models_registry" not in attrs:
            raise TypeError(f"{name} must define class-level attribute `models_registry`.")

        # Enforce correct type
        if not isinstance(attrs["models_registry"], dict):
            raise TypeError(f"{name}.models_registry must be a dict[str, Type[OptimizationModel].")

        # Prevent overriding of execute()
        if "final" in attrs:
            raise TypeError("invoke() is FINAL and cannot be overridden.")

        return cls


class OptimizationWorkflow(Generic[InputBaseModel, OutputBaseModel], ABC, metaclass=WorkflowMeta):
    _input_basemodel: Type[InputBaseModel]
    _output_basemodel: Type[OutputBaseModel]
    _logger: Optional[LogManager] = None

    id: str
    name: str
    models_registry: Dict[str, Type[OptimizationModel]] # {model_name : OptimizationModel}
    payload: InputBaseModel
    
    @final
    def __init__(self, payload: dict, logger: Optional[LogManager] = None):
        self.id = str(uuid.uuid4())
        self.payload = self._input_basemodel(**payload)
        self._logger = logger
        
    @final
    def invoke(self) -> Optional[dict]:
        workflow_log = self._workflow_log
        workflow_log.start_timestamp = datetime.now(timezone.utc).isoformat()
        start_time = time.time()

        try:
            result = self.execute()
            workflow_log.message = "success"

        except Exception as e:
            workflow_log.message = str(e)

        finally:
            runtime_sec = time.time() - start_time
            workflow_log.end_timestamp = datetime.now(timezone.utc).isoformat()
            workflow_log.runtime_sec = runtime_sec

            if self._logger is not None and self._logger.is_monitor_runtime:
                self._logger.put_workflow_log(workflow_log=workflow_log)

        if workflow_log.message == "success":
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

        return output

    @property
    def _workflow_log(self) -> WorkflowLog:
        return WorkflowLog(
            request_id=self.id,
            model_ids=[model_id for model_id in self.models_registry.keys()],
            payload=self.payload.model_dump(),
            solver_parameter={}, # TODO: extract from workflow execution context
            message=None,
            start_timestamp=None,
            end_timestamp=None,
            runtime_sec=None
        )