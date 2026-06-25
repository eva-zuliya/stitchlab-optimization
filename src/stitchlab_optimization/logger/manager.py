from __future__ import annotations
from abc import abstractmethod, ABC
from pydantic import BaseModel
from typing import Optional
import json
import os
import time
import psutil
import threading
from statistics import mean

from ..solver.engine import SolverEngine
from ..solver.status import SolverStatus
from ..solver.params import SolverParams


class ResourceStats(BaseModel):
    peak_cpu_percent: float
    avg_cpu_percent: float
    peak_memory_mb: float
    avg_memory_mb: float
    max_num_threads: int


class ResourceSnapshot(BaseModel):
    timestamp: float
    cpu_percent: float
    memory_mb: float
    num_threads: int


class ModelLog(BaseModel):
    solver_engine: SolverEngine
    solver_params: SolverParams
    model_id: str
    model_name: str
    status: SolverStatus
    problem_size_vars: Optional[int]
    problem_size_cons: Optional[int]
    optimality_gap: Optional[float]
    objective_value: Optional[float]
    message: Optional[str]
    runtime_sec: float
    resource_stats: Optional[ResourceStats] = None
    created_timestamp: str

    def to_sql_log(self) -> dict:
        return {
            "id": None,
            "solver_engine": self.solver_engine.value,
            "solver_params": self.solver_params.model_dump_json(),
            "model_id": self.model_id,
            "model_name": self.model_name,
            "problem_size_vars": self.problem_size_vars,
            "problem_size_cons": self.problem_size_cons,
            "optimality_gap": self.optimality_gap,
            "objective_value": self.objective_value,
            "status": self.status.value,
            "message": self.message,
            "runtime_sec": self.runtime_sec,
            "resource_stats": self.resource_stats.model_dump_json(),
            "created_timestamp": self.created_timestamp
        }


class WorkflowLog(BaseModel):
    workflow_id: str
    workflow_name: str
    model_ids_execution: dict
    payload: dict
    message: Optional[str]
    start_timestamp: str
    end_timestamp: str
    runtime_sec: float
    created_timestamp: str

    def to_sql_log(self) -> dict:
        model_ids = json.dumps(self.model_ids_execution)
        payload = json.dumps(self.payload)

        return {
            "id": None,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "model_ids": model_ids,
            "payload": payload,
            "message": self.message,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "runtime_sec": self.runtime_sec,
            "created_timestamp": self.created_timestamp
        }


class LogManager(ABC):
    enable_monitor_optimality: bool = True
    enable_monitor_runtime: bool = True
    enable_monitor_resource: bool = False
    monitor_resource_interval_seconds: int = 5

    _dir_model_execution_log: str = "log_execution_model"
    _dir_workflow_execution_log: str = "log_execution_workflow"

    def __init__(self):
        pass

    @abstractmethod
    def put_model_log(self, model_log: ModelLog):
        pass

    @abstractmethod
    def put_workflow_log(self, workflow_log: WorkflowLog):
        pass


class BaseResourceMonitor(ABC):
    stats: Optional[ResourceStats] = None

    @abstractmethod
    def __enter__(self):
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class NullResourceMonitor(BaseResourceMonitor):
    stats = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class ResourceMonitor(BaseResourceMonitor):

    def __init__(self, interval_seconds: int = 1):
        self._running = False
        self.interval_seconds = interval_seconds
        self.stats: Optional[ResourceStats] = None
        self._thread: Optional[threading.Thread] = None
        self._snapshots: list[ResourceSnapshot] = []
        self._stop_event = threading.Event()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        if self._running:
            return

        self._running = True
        self._stop_event.clear()

        proc = psutil.Process(os.getpid())
        proc.cpu_percent(interval=None)
        self._take_sample(proc)

        self._thread = threading.Thread(
            target=self._sampling_loop,
            daemon=True
        )

        self._thread.start()

    def stop(self):
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join()

        self.stats = self._aggregate()

    def _take_sample(self, proc: psutil.Process):
        try:
            self._snapshots.append(
                ResourceSnapshot(
                    timestamp=time.time(),
                    cpu_percent=proc.cpu_percent(interval=None),
                    memory_mb=proc.memory_info().rss / 1024 / 1024,
                    num_threads=proc.num_threads()
                )
            )
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
        ):
            pass

    def _sampling_loop(self):
        proc = psutil.Process(os.getpid())

        while not self._stop_event.wait(self.interval_seconds):
            self._take_sample(proc)

    def _aggregate(self) -> Optional[ResourceStats]:
        if not self._snapshots:
            return None

        cpu_values = [x.cpu_percent for x in self._snapshots]
        mem_values = [x.memory_mb for x in self._snapshots]
        thread_values = [x.num_threads for x in self._snapshots]

        return ResourceStats(
            peak_cpu_percent=max(cpu_values),
            avg_cpu_percent=mean(cpu_values),
            peak_memory_mb=max(mem_values),
            avg_memory_mb=mean(mem_values),
            max_num_threads=max(thread_values)
        )