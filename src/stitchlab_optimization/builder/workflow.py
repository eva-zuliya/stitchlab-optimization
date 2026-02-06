from abc import ABC, ABCMeta, abstractmethod
from typing import Dict, Type, Generic, TypeVar, final, Any, Optional
import uuid
from pydantic import BaseModel

from src.stitchlab_optimization.logger.manager import ModelLogManager, ModelLog
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
    _logger: Optional[ModelLogManager] = None

    id: str
    name: str
    models_registry: Dict[str, Type[OptimizationModel]] # {model_name : OptimizationModel}
    payload: InputBaseModel
    
    @final
    def __init__(self, payload: dict, logger: Optional[ModelLogManager] = None):
        self.id = str(uuid.uuid4())
        self.payload = self._input_basemodel(**payload)
        self._logger = logger
        
    @final
    def invoke(self) -> dict:
        result = self.execute()
        return result.model_dump()

    @final
    def execute_model(self, model_name: str, params: Any, solver_engine: Optional[SolverEngine] = None) -> Any:
        if model_name not in self.models_registry:
            raise ValueError(f"Model '{model_name}' not found in models_registry.")
        
        model_cls = self.models_registry[model_name]
        model_instance = model_cls(
            params=params,
            solver_engine=solver_engine
        )

        output = model_instance.execute()

        if self._logger is not None:
            model_log = ModelLog.from_model(model=model_instance)                    
            self._logger.put_model_log(model_log=model_log)

        return output

    @abstractmethod
    def execute(self) -> OutputBaseModel:
        pass