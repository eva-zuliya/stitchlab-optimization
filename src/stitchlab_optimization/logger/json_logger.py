from .manager import LogManager, ModelLog, WorkflowLog
from pathlib import Path


class JSONLogManager(LogManager):
    directory_path: str

    def __init__(
            self, directory_path: str,
            enable_monitor_optimality: bool = True,
            enable_monitor_runtime: bool = True,
            enable_monitor_resource: bool = False
        ):
        self.directory_path = directory_path
        self.enable_monitor_optimality = enable_monitor_optimality
        self.enable_monitor_resource = enable_monitor_resource
        self.enable_monitor_runtime = enable_monitor_runtime
    
        self.init_directory()

    def init_directory(self):
        if self.enable_monitor_optimality:
            Path(
                f"{self.directory_path}/{self._dir_model_execution_log}"
            ).mkdir(parents=True, exist_ok=True)

        if self.enable_monitor_runtime:
            Path(
                f"{self.directory_path}/{self._dir_workflow_execution_log}"
            ).mkdir(parents=True, exist_ok=True)

    def put_model_log(self, model_log: ModelLog):
        file_path = Path(f"{self.directory_path}/{self._dir_model_execution_log}/{model_log.model_id}.json")
        
        file_path.write_text(
            model_log.model_dump_json(indent=2),
            encoding="utf-8"
        )

    def put_workflow_log(self, workflow_log: WorkflowLog):
        file_path = Path(f"{self.directory_path}/{self._dir_workflow_execution_log}/{workflow_log.workflow_id}.json")
        
        file_path.write_text(
            workflow_log.model_dump_json(indent=2),
            encoding="utf-8"
        )